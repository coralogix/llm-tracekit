import os
from guardrails_sdk.span_builder import (
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
    GuardrailsConfig,
    GuardrailsEndpoint,
    GuardrailsRequest,
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

DEFAULT_TIMEOUT = 10
GUARDRAILS_ENDPOINT_PREFIX = "/api/v1/guardrails/"

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
        api_key: str | None = None,
        cx_endpoint: str | None = None,
        application_name: str | None = None,
        subsystem_name: str | None = None,
        timeout: int | None = None,
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
        guardrails_config: GuardrailsConfig,
    ) -> Optional[GuardrailsResponse]:
        if not all([prompt, guardrails_config]):
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
        guardrails_config: GuardrailsConfig,
        response: str,
        prompt: Optional[str] = None,
    ) -> Optional[GuardrailsResponse]:
        if not all([response, guardrails_config]):
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
        guardrails_request: GuardrailsRequest,
        guardrail_endpoint: GuardrailsEndpoint,
        client: httpx.AsyncClient,
    ) -> httpx.Response:
        guardrails_json_request = guardrails_request.model_dump(
            mode="json", exclude_none=True
        )
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
            raise GuardrailsAPIResponseError(response.status_code, response.text)

        return response

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-Coralogix-Auth": f"{self.config.api_key}",
            "cx-application-name": self.config.application_name,
            "cx-subsystem-name": self.config.subsystem_name,
        }

    async def run(
        self,
        guardrails_configs: GuardrailsConfig,
        guardrail_endpoint: GuardrailsEndpoint,
        target: GuardrailsTarget,
        client: httpx.AsyncClient,
        prompt: Optional[str] = None,
        response: Optional[str] = None,
    ) -> GuardrailsResponse:
        guardrails_request = GuardrailsRequest(
            application=self.config.application_name,
            subsystem=self.config.subsystem_name,
            prompt=prompt,
            response=response,
            guardrails_configs=guardrails_configs.to_list(),
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
                        http_response.status_code,
                        http_response.text,
                        f"Failed to parse response as JSON: {str(json_error)}",
                    ) from json_error
                span.set_attributes(
                    generate_guardrail_response_attributes(
                        guardrail_response=guardrails_response, target=target.value
                    )
                )
                for resp in guardrails_response.results:
                    if resp.detected and not self.config.suppress_guardrails_triggered_exception:
                        raise GuardrailTriggered(
                            guardrail_type=resp.detection_type.value,
                            name=resp.name,
                            score=resp.score,
                            explanation=resp.explanation,
                            detected_categories=resp.detected_categories,
                        )
                return GuardrailsResponse(results=guardrails_response.results)
            except GuardrailTriggered:
                raise
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
