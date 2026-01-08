import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode, Span

from .models._constants import (
    DEFAULT_TIMEOUT,
    GUARDRAILS_ENDPOINT_URL,
    PARENT_SPAN_NAME,
)
from .models.request import (
    GuardrailConfigType,
    GuardrailRequest,
    Message,
)
from .models._models import GuardrailsTarget, Role
from .models.response import GuardrailsResponse
from .span_builder import (
    generate_guardrail_response_attributes,
    generate_base_attributes,
)
from .error import (
    GuardrailsAPIResponseError,
    GuardrailsAPIConnectionError,
    GuardrailsAPITimeoutError,
    GuardrailViolation,
    GuardrailsTriggered,
)


tracer = trace.get_tracer(__name__)


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
        api_key: str | None = None,
        cx_endpoint: str | None = None,
        application_name: str | None = None,
        subsystem_name: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.config = GuardrailsClientConfig(
            api_key=_get_env(api_key, "CX_GUARDRAILS_TOKEN"),
            cx_endpoint=_normalize_endpoint(_get_env(cx_endpoint, "CX_ENDPOINT")),
            application_name=_get_env(
                application_name, "CX_APPLICATION_NAME", "Unknown"
            ),
            subsystem_name=_get_env(subsystem_name, "CX_SUBSYSTEM_NAME", "Unknown"),
            timeout=timeout if timeout is not None else DEFAULT_TIMEOUT,
            suppress_exceptions=os.environ.get(
                "DISABLE_GUARDRAILS_TRIGGERED_EXCEPTION", ""
            ).lower()
            == "true",
        )
        self._sender = GuardrailRequestSender(config=self.config)

    @asynccontextmanager
    async def guarded_session(self):
        """Async context manager that groups guardrail calls under a parent span.

        Example:
            async with guardrails.guarded_session():
                await guardrails.guard_prompt([PII()], prompt)
                await guardrails.guard_response([PII()], response)
        """
        with tracer.start_as_current_span(PARENT_SPAN_NAME):
            yield

    async def guard(
        self,
        guardrails: list[GuardrailConfigType],
        messages: list[Message | dict[str, Any]],
        target: GuardrailsTarget,
    ) -> GuardrailsResponse | None:
        """Check a conversation against configured guardrails.

        Low-level method for guardrail checks. For simpler use cases,
        prefer `guard_prompt` or `guard_response`.

        Args:
            messages: Conversation messages (Message objects or dicts with 'role'/'content').
            guardrails: Guardrail configs to apply (e.g., `PII()`, `PromptInjection()`).
            target: What to check - `GuardrailsTarget.PROMPT` or `GuardrailsTarget.RESPONSE`.

        Returns:
            GuardrailsResponse with results, or None if inputs are empty.

        Raises:
            AttributeError: If target is RESPONSE but last message isn't from assistant.
            GuardrailsTriggered: If any guardrail is violated.
            GuardrailsAPIConnectionError, GuardrailsAPITimeoutError, GuardrailsAPIResponseError.
        """
        if not messages or not guardrails:
            return None
        history: list[Message] = [self._to_messages(msg) for msg in messages]
        if (
            target == GuardrailsTarget.RESPONSE
            and history[-1].role is not Role.ASSISTANT
        ):
            raise AttributeError(
                f"target of {GuardrailsTarget.RESPONSE} was given but last message is not a response"
            )
        return await self._sender.run(guardrails, target, history)

    async def guard_prompt(
        self,
        guardrails: list[GuardrailConfigType],
        prompt: str,
    ) -> GuardrailsResponse | None:
        """Check a user prompt against configured guardrails.

        Validates user input before sending it to an LLM.

        Args:
            prompt: The user's input text to validate.
            guardrails: Guardrail configs to apply (e.g., `PII()`, `PromptInjection()`).

        Returns:
            GuardrailsResponse with results, or None if prompt is empty.

        Raises:
            GuardrailsTriggered: If any guardrail is violated.
            GuardrailsAPIConnectionError, GuardrailsAPITimeoutError, GuardrailsAPIResponseError.
        """
        if not prompt:
            return None
        return await self.guard(
            guardrails,
            [Message(role=Role.USER, content=prompt)],
            GuardrailsTarget.PROMPT,
        )

    async def guard_response(
        self,
        guardrails: list[GuardrailConfigType],
        response: str,
        prompt: str | None = None,
    ) -> GuardrailsResponse | None:
        """Check an LLM response against configured guardrails.

        Validates LLM output before returning it to the user.

        Args:
            guardrails: Guardrail configs to apply (e.g., `PII()`, `PromptInjection()`).
            response: The LLM's response text to validate.
            prompt: Optional original prompt for context-aware detection.

        Returns:
            GuardrailsResponse with results, or None if response is empty.

        Raises:
            GuardrailsTriggered: If any guardrail is violated.
            GuardrailsAPIConnectionError, GuardrailsAPITimeoutError, GuardrailsAPIResponseError.
        """
        if not response:
            return None
        messages: list[Message | dict[str, Any]] = []
        if prompt:
            messages.append(Message(role=Role.USER, content=prompt))
        messages.append(Message(role=Role.ASSISTANT, content=response))
        return await self.guard(guardrails, messages, GuardrailsTarget.RESPONSE)

    def _to_messages(self, msg: Message | dict[str, Any]) -> Message:
        return msg if isinstance(msg, Message) else Message(msg)


class GuardrailRequestSender:
    def __init__(self, config: GuardrailsClientConfig) -> None:
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=self.config.cx_endpoint,
            timeout=httpx.Timeout(self.config.timeout, connect=2.0),
        )

    async def run(
        self,
        guardrails: list[GuardrailConfigType],
        target: GuardrailsTarget,
        messages: list[Message],
    ) -> GuardrailsResponse:
        request = GuardrailRequest(
            application=self.config.application_name,
            subsystem=self.config.subsystem_name,
            messages=messages,
            guardrails=guardrails,
            target=target,
            timeout=self.config.timeout,
        )

        with tracer.start_as_current_span(
            f"guardrails.{target.value}", kind=SpanKind.CLIENT
        ) as span:
            span.set_attributes(
                generate_base_attributes(
                    application_name=request.application,
                    subsystem_name=request.subsystem,
                    prompts=[msg.content for msg in messages if msg.role == Role.USER],
                    responses=[
                        msg.content for msg in messages if msg.role == Role.ASSISTANT
                    ],
                )
            )
            try:
                http_response = await self._send_request(request)
                return self._handle_response(http_response, span, target)
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

    def _get_headers(self) -> dict[str, str]:
        return {
            "X-Coralogix-Auth": self.config.api_key,
            "cx-application-name": self.config.application_name,
            "cx-subsystem-name": self.config.subsystem_name,
        }

    async def _send_request(self, request: GuardrailRequest) -> httpx.Response:
        try:
            response = await self._client.post(
                GUARDRAILS_ENDPOINT_URL,
                json=request.model_dump(mode="json", exclude_none=True),
                headers=self._get_headers(),
            )
        except httpx.TimeoutException as e:
            raise GuardrailsAPITimeoutError(
                f"Request timed out after {self.config.timeout}s"
            ) from e
        except httpx.ConnectError as e:
            raise GuardrailsAPIConnectionError(
                f"Failed to connect to {self.config.cx_endpoint}"
            ) from e
        except httpx.RequestError as e:
            raise GuardrailsAPIConnectionError(f"Request error: {e}") from e
        return response

    def _handle_response(
        self, response: httpx.Response, span: Span, target: GuardrailsTarget
    ) -> GuardrailsResponse:
        if not response.is_success:
            raise GuardrailsAPIResponseError(
                status_code=response.status_code,
                body=response.text,
            )

        if not response.text or not response.text.strip():
            return GuardrailsResponse(results=[])

        try:
            results = GuardrailsResponse.model_validate_json(response.text)
        except Exception as err:
            raise GuardrailsAPIResponseError(
                status_code=response.status_code,
                body=response.text,
                message=f"Got invalid response: {err}",
            ) from err

        span.set_attributes(
            generate_guardrail_response_attributes(results, target.value)
        )
        if not self.config.suppress_exceptions:
            violations = [
                GuardrailViolation(
                    guardrail_type=result.type.value,
                    name=getattr(result, "name", None),
                )
                for result in results.results
                if result.detected
            ]
            if violations:
                raise GuardrailsTriggered(violations)

        return results


def _get_env(value: str | None, env_var: str, default: str = "") -> str:
    return value if value is not None else os.environ.get(env_var, default)


def _normalize_endpoint(endpoint: str) -> str:
    if not endpoint:
        raise ValueError(
            "Endpoint URL is required. "
            "Set CX_ENDPOINT environment variable or pass cx_endpoint parameter."
        )
    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    return urlunparse(parsed._replace(scheme="https"))
