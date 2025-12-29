import os
from guardrails.guardrails.constants import DEFAULT_TIMEOUT, GUARDRAILS_ENDPOINT_PREFIX
from guardrails.span_builder import (
    generate_guardrail_response_attributes,
    generate_base_attributes,
)
import httpx
from typing import List, Optional, Dict
from dataclasses import dataclass
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from contextlib import asynccontextmanager

from .models import (
    GuardrailConfigType,
    GuardrailsEndpoint,
    GuardrailRequest,
    GuardrailsResponse,
    GuardrailsTarget,
)
from .error import (
    GuardrailsAPIResponseError,
    GuardrailsAPIConnectionError,
    GuardrailsAPITimeoutError,
    GuardrailTriggered,
)


tracer = trace.get_tracer(__name__)


def _get_env_or_default(value: Optional[str], env_var: str, default: str = "") -> str:
    if value is not None:
        return value
    return os.environ.get(env_var, default)


@dataclass
class GuardrailsClientConfig:
    api_key: str
    application_name: str
    subsystem_name: str
    cx_endpoint: str
    timeout: int
    suppress_guardrails_triggered_exception: bool


class Guardrails:
    """Guardrails client for protecting LLM conversations.

    Configuration can be provided via constructor arguments or environment variables:
        - CX_GUARDRAILS_TOKEN: API token for Coralogix authentication
        - CX_ENDPOINT: Coralogix guardrails endpoint URL
        - CX_APPLICATION_NAME: Application name for tracing (default: "Unknown")
        - CX_SUBSYSTEM_NAME: Subsystem name for tracing (default: "Unknown")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        cx_endpoint: Optional[str] = None,
        application_name: Optional[str] = None,
        subsystem_name: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.config = GuardrailsClientConfig(
            api_key=_get_env_or_default(api_key, "CX_GUARDRAILS_TOKEN"),
            cx_endpoint=_get_env_or_default(cx_endpoint, "CX_ENDPOINT"),
            application_name=_get_env_or_default(
                application_name, "CX_APPLICATION_NAME", "Unknown"
            ),
            subsystem_name=_get_env_or_default(
                subsystem_name, "CX_SUBSYSTEM_NAME", "Unknown"
            ),
            timeout=timeout if timeout is not None else DEFAULT_TIMEOUT,
            suppress_guardrails_triggered_exception=os.environ.get("DISABLE_GUARDRAIL_TRIGGERED_EXCEPTIONS", "").lower() == "true"
        )
        if "https://" not in self.config.cx_endpoint:
            self.config.cx_endpoint = "https://" + self.config.cx_endpoint
        self._sender = GuardrailRequestSender(config=self.config)

    @asynccontextmanager
    async def guarded_session(self):
        self._client = httpx.AsyncClient(
            base_url=self.config.cx_endpoint,
            timeout=httpx.Timeout(self.config.timeout, connect=10.0),
        )
        with tracer.start_as_current_span("Guarded session"):
            try:
                yield
            finally:
                await self._client.aclose()

    async def guard_prompt(
        self,
        prompt: str,
        guardrails_config: List[GuardrailConfigType],
    ) -> Optional[GuardrailsResponse]:
        if not prompt or not guardrails_config:
            return None
        return await self._sender.run(
            guardrails_configs=guardrails_config,
            guardrail_endpoint=GuardrailsEndpoint.PROMPT_ENDPOINT,
            target=GuardrailsTarget.prompt,
            prompt=prompt,
            client=self._client,
        )

    async def guard_response(
        self,
        guardrails_config: list[GuardrailConfigType],
        response: str,
        prompt: Optional[str] = None,
    ) -> Optional[GuardrailsResponse]:
        if not response or not guardrails_config:
            return None
        return await self._sender.run(
            guardrails_configs=guardrails_config,
            guardrail_endpoint=GuardrailsEndpoint.RESPONSE_ENDPOINT,
            target=GuardrailsTarget.response,
            prompt=prompt,
            response=response,
            client=self._client,
        )


class GuardrailRequestSender:
    def __init__(self, config: GuardrailsClientConfig) -> None:
        self.config = config
    async def _send_request(
        self,
        guardrails_request: GuardrailRequest,
        guardrail_endpoint: GuardrailsEndpoint,
        client: httpx.AsyncClient,
    ) -> httpx.Response:
        guardrails_json_request = guardrails_request.model_dump(
            mode="json", exclude_none=True
        )
        # print(guardrails_json_request)
        # exit()
        try:
            response = await client.post(
                GUARDRAILS_ENDPOINT_PREFIX + guardrail_endpoint.value,
                json=guardrails_json_request,
                headers=self._get_headers(),
            )
        except httpx.TimeoutException as e:
            raise GuardrailsAPITimeoutError(
                f"Request to {guardrail_endpoint.value} timed out after {self.config.timeout}s"
            ) from e
        except httpx.ConnectError as e:
            raise GuardrailsAPIConnectionError(
                f"Failed to connect to {self.config.cx_endpoint}"
            ) from e
        except httpx.RequestError as e:
            raise GuardrailsAPIConnectionError(f"Request error: {str(e)}") from e

        if response.status_code >= 400:
            raise GuardrailsAPIResponseError(status_code=response.status_code, body=response.text)

        return response

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-Coralogix-Auth": f"{self.config.api_key}",
            "cx-application-name": self.config.application_name,
            "cx-subsystem-name": self.config.subsystem_name,
        }

    async def run(
        self,
        guardrails_configs: List[GuardrailConfigType],
        guardrail_endpoint: GuardrailsEndpoint,
        target: GuardrailsTarget,
        client: httpx.AsyncClient,
        prompt: Optional[str] = None,
        response: Optional[str] = None,
    ) -> GuardrailsResponse:
        guardrails_request = GuardrailRequest(
            application=self.config.application_name,
            subsystem=self.config.subsystem_name,
            prompt=prompt,
            response=response,
            guardrails_configs=guardrails_configs,
            timeout=self.config.timeout
        )
        span_name = f"guardrails.{guardrail_endpoint.value}"

        with tracer.start_as_current_span(
            name=span_name,
            kind=SpanKind.CLIENT,
        ) as span:
            span.set_attributes(
                generate_base_attributes(
                    application_name=guardrails_request.application,
                    subsystem_name=guardrails_request.subsystem,
                    prompt=guardrails_request.prompt,
                    response=guardrails_request.response,
                )
            )
            try:
                http_response = await self._send_request(
                    guardrails_request, guardrail_endpoint, client=client
                )
                if not http_response.text or http_response.text.strip() == "":
                    return GuardrailsResponse(results=[])
                try:
                    guardrails_response: GuardrailsResponse = (
                        GuardrailsResponse.model_validate_json(http_response.text)
                    )
                except Exception as json_error:
                    raise GuardrailsAPIResponseError(
                        status_code=http_response.status_code,
                        body=http_response.text,
                        message=f"Failed to parse response as JSON: {str(json_error)}",
                    ) from json_error
                span.set_attributes(
                    generate_guardrail_response_attributes(
                        guardrail_response=guardrails_response, target=target.value
                    )
                )
                for resp in guardrails_response.results:
                    if resp.detected and not self.config.suppress_guardrails_triggered_exception:
                        raise GuardrailTriggered(
                            guardrail_type=resp.type.value,
                            name=getattr(resp, 'name', None),
                            score=resp.score,
                            explanation=getattr(resp, 'explanation', None),
                            detected_categories=getattr(resp, 'detected_categories', None),
                        )
                return GuardrailsResponse(results=guardrails_response.results)
            except GuardrailTriggered:
                raise
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
