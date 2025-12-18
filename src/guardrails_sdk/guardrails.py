from guardrails_sdk.span_builder import (
    generate_guardrail_response_attributes,
    generate_base_attributes,
)
import httpx  # ty: ignore[unresolved-import]
from typing import List, Optional, Annotated
from pydantic import Field, StringConstraints  # ty: ignore[unresolved-import]
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)  # ty: ignore[unresolved-import]
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from contextlib import asynccontextmanager

from .models import (
    GuardrailsEndpoint,
    GuardrailsRequest,
    GuardrailsResult,
    GuardrailsResponse,
    PII,
    PromptInjection,
    CustomGuardrail,
    GuardrailsTarget,
)
from .error import (
    GuardrailsAPIResponseError,
    GuardrailsAPIConnectionError,
    GuardrailsAPITimeoutError,
    GuardrailTriggered,
)


tracer = trace.get_tracer(__name__)
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class GuardrailsRequestConfig(BaseSettings):
    """Configuration settings for Guardrails with automatic environment variable loading."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="forbid"
    )

    api_key: NonEmptyStr = Field(..., description="API key for authentication")
    application_name: NonEmptyStr = Field(..., description="Name of the application")
    subsystem_name: NonEmptyStr = Field(..., description="Name of the subsystem")
    domain_url: NonEmptyStr = Field(..., description="Domain URL for the service")
    timeout: int = Field(default=100, ge=1, description="Request timeout in seconds")


class Guardrails:
    def __init__(
        self,
        api_key: str | None = None,
        application_name: str | None = None,
        subsystem_name: str | None = None,
        domain_url: str | None = None,
        timeout: int | None = None,
    ) -> None:
        local_vars = locals().copy()
        config_kwargs = {k: v for k, v in local_vars.items() if v is not None}
        config_kwargs.pop("self", None)

        self.config = GuardrailsRequestConfig(**config_kwargs)

    @asynccontextmanager
    async def interaction(self):
        self._client = httpx.AsyncClient(
            base_url=self.config.domain_url,
            timeout=httpx.Timeout(self.config.timeout, connect=10.0),
        )

        with tracer.start_as_current_span(__name__):
            try:
                yield
            finally:
                await self._client.aclose()

    async def _send_request(
        self,
        guardrails_request: GuardrailsRequest,
        guardrail_endpoint: GuardrailsEndpoint,
    ) -> httpx.Response:
        guardrails_json_request = guardrails_request.model_dump(
            mode="json", exclude_none=True
        )
        try:
            response = await self._client.post(
                guardrail_endpoint.value,
                json=guardrails_json_request,
                headers={"X-Coralogix-Auth": guardrails_request.api_key},
            )
        except httpx.TimeoutException as e:
            raise GuardrailsAPITimeoutError(
                f"Request to {guardrail_endpoint.value} timed out after {self.config.timeout}s"
            ) from e
        except httpx.ConnectError as e:
            raise GuardrailsAPIConnectionError(
                f"Failed to connect to {self.config.domain_url}"
            ) from e
        except httpx.RequestError as e:
            raise GuardrailsAPIConnectionError(f"Request error: {str(e)}") from e

        if response.status_code >= 400:
            raise GuardrailsAPIResponseError(response.status_code, response.text)

        return response

    async def guard_prompt(
        self,
        prompt: str,
        guardrails_config: List[PII | PromptInjection | CustomGuardrail],
    ) -> Optional[List[GuardrailsResult]]:
        if not all([prompt, guardrails_config]):
            return None
        return await self.run(
            guardrails_configs=guardrails_config,
            guardrail_endpoint=GuardrailsEndpoint.PROMPT_ENDPOINT,
            target=GuardrailsTarget.prompt,
            prompt=prompt,
        )

    async def guard_response(
        self,
        guardrails_config: List[PII | PromptInjection | CustomGuardrail],
        response: str,
        prompt: Optional[str] = None,
    ) -> Optional[List[GuardrailsResult]]:
        if not all([response, guardrails_config]):
            return None
        return await self.run(
            guardrails_configs=guardrails_config,
            guardrail_endpoint=GuardrailsEndpoint.RESPONSE_ENDPOINT,
            target=GuardrailsTarget.response,
            prompt=prompt,
            response=response,
        )

    async def run(
        self,
        guardrails_configs: List[PII | PromptInjection | CustomGuardrail],
        guardrail_endpoint: GuardrailsEndpoint,
        target: GuardrailsTarget,
        prompt: Optional[str] = None,
        response: Optional[str] = None,
    ) -> List[GuardrailsResult]:
        guardrails_request = GuardrailsRequest(
            api_key=self.config.api_key,
            application=self.config.application_name,
            subsystem=self.config.subsystem_name,
            domain_url=self.config.domain_url,
            prompt=prompt,
            response=response,
            guardrails_configs=guardrails_configs,
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
                    guardrails_request, guardrail_endpoint
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
                    if resp.detected:
                        raise GuardrailTriggered(
                            guardrail_type=resp.detection_type.value,
                            name=resp.name,
                            score=resp.score,
                            explanation=resp.explanation,
                        )
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

        return guardrails_response.results
