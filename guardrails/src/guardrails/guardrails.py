from importlib.resources import contents
from operator import concat
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional, Any, Union

import httpx
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode, Span

from .models.constants import DEFAULT_TIMEOUT, GUARDRAILS_ENDPOINT_URL
from .models.request import (
    GuardrailConfigType,
    GuardrailRequest,
    Message,
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
        messages: list[Union[Message, dict[str, Any]]],
        guardrails_config: list[GuardrailConfigType],
        target: GuardrailsTarget,
    ) -> Optional[GuardrailsResponse]:
        if not messages or not guardrails_config:
            return None
        history: list[Message] = [self._to_messages(msg) for msg in messages]
        if target == GuardrailsTarget.response and history[-1].role is not Role.Assistant:
            raise AttributeError(f"target of {GuardrailsTarget.response} was given but last message is not a response")
        return await self._sender.run(guardrails_config, target, history, self._client)

    def _to_messages(self, msg: Union[Message, dict[str, Any]]):
        return msg if isinstance(msg, Message) else Message(msg)

    async def guard_prompt(
        self,
        prompt: str,
        guardrails_config: list[GuardrailConfigType],
    ) -> Optional[GuardrailsResponse]:
        if not prompt:
            return None
        return await self.guard([Message(role=Role.User, content=prompt)], guardrails_config, GuardrailsTarget.prompt)

    async def guard_response(
        self,
        guardrails_config: list[GuardrailConfigType],
        response: str,
        prompt: Optional[str] = None,
    ) -> Optional[GuardrailsResponse]:
        if not response:
            return None
        messages: list[Message] = []
        if prompt:
            messages.append(Message(role=Role.User, content=prompt))
        messages.append(Message(role=Role.Assistant, content=response))
        return await self.guard(messages, guardrails_config, GuardrailsTarget.response)


class GuardrailRequestSender:
    
    def __init__(self, config: GuardrailsClientConfig) -> None:
        self.config = config

    def _get_headers(self) -> dict[str, str]:
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
        guardrails_configs: list[GuardrailConfigType],
        target: GuardrailsTarget,
        messages: list[Message],
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
                    guardrail_type=res.type.value,
                    name=getattr(res, "name", None),
                    score=res.score,
                    detected_categories=getattr(res, "detected_categories", None),
                )
                for res in result.results if res.detected
            ]
            if violations:
                raise GuardrailsTriggered(violations)
        
        return result
