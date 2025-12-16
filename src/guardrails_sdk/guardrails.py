import httpx
import logging
from typing import List, Optional, Annotated
from pydantic import Field, StringConstraints
from pydantic_settings import BaseSettings, SettingsConfigDict
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from .models import (
    GuardrailsEndpoint,
    GuardrailsRequest,
    GuardrailsResult,
    GuardrailsResponse,
    PII,
    PromptInjection,
    CustomGuardrail,
)
from .error import GuardrailsAPIResponseError


logger = logging.getLogger(__name__)

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
        retries: int | None = None,
    ) -> None:
        local_vars = locals().copy()
        # Create config kwargs, only including non-None values
        config_kwargs = {k: v for k, v in local_vars.items() if v is not None}
        config_kwargs.pop("self", None)

        # Initialize config with validation
        self.config = GuardrailsRequestConfig(**config_kwargs)

        self._client = httpx.AsyncClient(
            base_url=self.config.domain_url,
            # headers={"Authorization": f"Bearer {self.config.api_key}"}
            timeout=self.config.timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self):
        print("Entering guardrails context")
        return self

    async def __aexit__(self, *_):
        print("Exiting guardrails context")
        await self.aclose()

    async def _run(self, guardrails_request: GuardrailsRequest, guardrail_endpoint: GuardrailsEndpoint) -> httpx.Response:
        tracer = trace.get_tracer(__name__)
        
        span_name = f"guardrails.{guardrail_endpoint.value}"
        span_attributes = {
            "guardrails.endpoint": guardrail_endpoint.value,
            "guardrails.application": guardrails_request.application,
            "guardrails.subsystem": guardrails_request.subsystem,
        }
        
        if guardrails_request.invocation_id:
            span_attributes["invocation_id"] = guardrails_request.invocation_id
        
        with tracer.start_as_current_span(
            name=span_name,
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
        ) as span:
            guardrails_json_request = guardrails_request.model_dump(exclude_none=True)
            guardrails_json_request["guardrails_config"] = [
                g.model_dump(exclude_none=True) for g in guardrails_request.guardrails_configs
            ]

            logger.debug(f"Sending request payload: {guardrails_json_request}")

            print(guardrails_json_request)
            try:
                response = await self._client.post(
                    guardrail_endpoint.value, json=guardrails_json_request, headers={"X-Coralogix-Auth": "CgR1c2VyEgEx"}
                )

                logger.debug(f"Received response with status code:{response.status_code}")
                logger.debug(f"Response text: {response.text}")

                if response.status_code >= 400:
                    logger.error(f"Received error response: {response.text}")
                    if span.is_recording():
                        span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                        span.record_exception(Exception(f"HTTP {response.status_code}: {response.text}"))
                    raise GuardrailsAPIResponseError(response.status_code, response.text)

                if span.is_recording():
                    span.set_attribute("http.status_code", response.status_code)
                    span.set_status(Status(StatusCode.OK))

                return response
            except Exception as e:
                if span.is_recording():
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                raise

    async def run_input(
        self,
        prompt: str,
        guardrails_config: List[PII | PromptInjection | CustomGuardrail],
        invocation_id: str,
    ) -> Optional[List[GuardrailsResult]]:
        return await self.run(
            prompt=prompt,
            guardrails_configs=guardrails_config,
            guardrail_endpoint=GuardrailsEndpoint.PROMPT_ENDPOINT,
            invocation_id=invocation_id,
        )

    async def run_output(
        self,
        prompt: str,
        response: str,
        guardrails_config: List[PII | PromptInjection | CustomGuardrail],
        invocation_id: str
    ) -> Optional[List[GuardrailsResult]]:
        return await self.run(
            prompt=prompt,
            guardrails_configs=guardrails_config,
            guardrail_endpoint=GuardrailsEndpoint.RESPONSE_ENDPOINT,
            response=response,
            invocation_id=invocation_id,
        )

    async def run(
        self,
        prompt: str,
        guardrails_configs: List[PII | PromptInjection | CustomGuardrail],
        guardrail_endpoint: GuardrailsEndpoint,
        invocation_id: str,
        response: Optional[str] = None
    ) -> List[GuardrailsResult]:
        guardrails_request = GuardrailsRequest(
            api_key=self.config.api_key,
            invocation_id=invocation_id,
            application=self.config.application_name,
            subsystem=self.config.subsystem_name,
            domain_url=self.config.domain_url,
            prompt=prompt,
            response=response,
            guardrails_configs=guardrails_configs,
        )

        logger.info(f"Running guardrails for message: {prompt}")
        logger.info(f"Guardrails config: {guardrails_request.guardrails_configs}")

        http_response = await self._run(guardrails_request, guardrail_endpoint)

        guardrails_response = GuardrailsResponse.model_validate_json(http_response.text)

        logger.info(
            f"HTTP response: {http_response.status_code} - {http_response.text}"
        )

        return guardrails_response.results
