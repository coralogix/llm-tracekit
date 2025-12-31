import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import List, Optional, Dict

import httpx
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode, Span

from .models.constants import DEFAULT_TIMEOUT, GUARDRAILS_ENDPOINT_URL
from .models.request import (
    GuardrailConfigType,
    GuardrailRequest,
    Message,
    MessageInput,
    normalize_messages,
)
from .models.enums import GuardrailsTarget, Role
from .models.response import GuardrailsResponse
from .span_builder import generate_guardrail_response_attributes, generate_base_attributes
from .error import (
    GuardrailsAPIResponseError,
    GuardrailsAPIConnectionError,
    GuardrailsAPITimeoutError,
    GuardrailViolation,
    GuardrailsTriggered,
)


tracer = trace.get_tracer(__name__)


def _get_env(value: Optional[str], env_var: str, default: str = "") -> str:
    """Get value from argument, environment variable, or default."""
    return value if value is not None else os.environ.get(env_var, default)


@dataclass
class GuardrailsClientConfig:
    api_key: str
    application_name: str
    subsystem_name: str
    cx_endpoint: str
    timeout: int
    suppress_exceptions: bool


class Guardrails:
    """Guardrails client for protecting LLM conversations.

    Configuration via constructor arguments or environment variables:
        - CX_GUARDRAILS_TOKEN: API token for authentication
        - CX_ENDPOINT: Coralogix guardrails endpoint URL
        - CX_APPLICATION_NAME: Application name (default: "Unknown")
        - CX_SUBSYSTEM_NAME: Subsystem name (default: "Unknown")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        cx_endpoint: Optional[str] = None,
        application_name: Optional[str] = None,
        subsystem_name: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        endpoint = _get_env(cx_endpoint, "CX_ENDPOINT")
        if "http://" in endpoint:
            endpoint = endpoint.replace("http://", "https://")
        if not endpoint.startswith("https://"):
            endpoint = "https://" + endpoint

        self.config = GuardrailsClientConfig(
            api_key=_get_env(api_key, "CX_GUARDRAILS_TOKEN"),
            cx_endpoint=endpoint,
            application_name=_get_env(application_name, "CX_APPLICATION_NAME", "Unknown"),
            subsystem_name=_get_env(subsystem_name, "CX_SUBSYSTEM_NAME", "Unknown"),
            timeout=timeout if timeout is not None else DEFAULT_TIMEOUT,
            suppress_exceptions=os.environ.get("DISABLE_GUARDRAIL_TRIGGERED_EXCEPTIONS", "").lower() == "true",
        )
        self._sender = GuardrailRequestSender(config=self.config)

    @asynccontextmanager
    async def guarded_session(self):
        """Context manager for guardrail calls. Required for all guard operations."""
        self._client = httpx.AsyncClient(
            base_url=self.config.cx_endpoint,
            timeout=httpx.Timeout(self.config.timeout, connect=10.0),
        )
        with tracer.start_as_current_span("Guarded session"):
            try:
                yield
            finally:
                await self._client.aclose()

    async def guard(
        self,
        messages: List[MessageInput],
        guardrails_config: List[GuardrailConfigType],
        target: GuardrailsTarget,
    ) -> Optional[GuardrailsResponse]:
        """Guard messages against configured guardrails.
        
        Args:
            messages: List of messages (Message objects or {"role": "...", "content": "..."} dicts)
            guardrails_config: List of guardrail configurations (PII, PromptInjection)
            target: Whether guarding prompt or response
            
        Returns:
            GuardrailsResponse with results, or None if messages/config empty
        """
        if not messages or not guardrails_config:
            return None
        normalized = normalize_messages(messages)
        if not normalized:
            return None
        return await self._sender.run(guardrails_config, target, normalized, self._client)

    async def guard_prompt(
        self,
        prompt: str,
        guardrails_config: List[GuardrailConfigType],
    ) -> Optional[GuardrailsResponse]:
        """Guard a user prompt against configured guardrails."""
        if not prompt:
            return None
        return await self.guard([{"role": "user", "content": prompt}], guardrails_config, GuardrailsTarget.prompt)

    async def guard_response(
        self,
        guardrails_config: List[GuardrailConfigType],
        response: str,
        prompt: Optional[str] = None,
    ) -> Optional[GuardrailsResponse]:
        """Guard an LLM response against configured guardrails."""
        if not response:
            return None
        messages: List[MessageInput] = []
        if prompt:
            messages.append({"role": "user", "content": prompt})
        messages.append({"role": "assistant", "content": response})
        return await self.guard(messages, guardrails_config, GuardrailsTarget.response)


class GuardrailRequestSender:
    """Internal class for sending guardrail requests."""
    
    def __init__(self, config: GuardrailsClientConfig) -> None:
        self.config = config

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-Coralogix-Auth": self.config.api_key,
            "cx-application-name": self.config.application_name,
            "cx-subsystem-name": self.config.subsystem_name,
        }

    async def _send_request(self, request: GuardrailRequest, client: httpx.AsyncClient) -> httpx.Response:
        try:
            response = await client.post(
                GUARDRAILS_ENDPOINT_URL,
                json=request.model_dump(mode="json", exclude_none=True),
                headers=self._get_headers(),
            )
        except httpx.TimeoutException as e:
            raise GuardrailsAPITimeoutError(f"Request timed out after {self.config.timeout}s") from e
        except httpx.ConnectError as e:
            raise GuardrailsAPIConnectionError(f"Failed to connect to {self.config.cx_endpoint}") from e
        except httpx.RequestError as e:
            raise GuardrailsAPIConnectionError(f"Request error: {e}") from e

        if response.status_code >= 400:
            raise GuardrailsAPIResponseError(status_code=response.status_code, body=response.text)
        return response

    async def run(
        self,
        guardrails_configs: List[GuardrailConfigType],
        target: GuardrailsTarget,
        messages: List[Message],
        client: httpx.AsyncClient,
    ) -> GuardrailsResponse:
        request = GuardrailRequest(
            application=self.config.application_name,
            subsystem=self.config.subsystem_name,
            messages=messages,
            guardrails_configs=guardrails_configs,
            target=target,
            timeout=self.config.timeout,
        )

        with tracer.start_as_current_span(f"guardrails.{target.value}", kind=SpanKind.CLIENT) as span:
            span.set_attributes(generate_base_attributes(
                application_name=request.application,
                subsystem_name=request.subsystem,
                prompts=[m.content for m in messages if m.role == Role.User],
                responses=[m.content for m in messages if m.role == Role.Assistant],
            ))
            try:
                http_response = await self._send_request(request, client)
                return self._handle_response(http_response, span, target)
            except GuardrailsTriggered:
                raise
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

    def _handle_response(self, response: httpx.Response, span: Span, target: GuardrailsTarget) -> GuardrailsResponse:
        if not response.text or not response.text.strip():
            return GuardrailsResponse(results=[])
        
        try:
            result = GuardrailsResponse.model_validate_json(response.text)
        except Exception as e:
            raise GuardrailsAPIResponseError(
                status_code=response.status_code,
                body=response.text,
                message=f"Failed to parse response: {e}",
            ) from e

        span.set_attributes(generate_guardrail_response_attributes(result, target.value))
        
        if not self.config.suppress_exceptions:
            violations = [
                GuardrailViolation(
                    guardrail_type=r.type.value,
                    name=getattr(r, "name", None),
                    score=r.score,
                    detected_categories=getattr(r, "detected_categories", None),
                )
                for r in result.results if r.detected
            ]
            if violations:
                raise GuardrailsTriggered(violations)
        
        return result
