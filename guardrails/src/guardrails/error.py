from __future__ import annotations


class GuardrailsError(Exception):
    """Base exception for all SDK errors."""


class GuardrailsAPIConnectionError(GuardrailsError):
    """Network/transport errors."""


class GuardrailsAPITimeoutError(GuardrailsError):
    """Request timed out."""


class GuardrailsAPIResponseError(GuardrailsError):
    """Non-2xx HTTP response."""

    def __init__(
        self,
        status_code: int,
        body: str | None = None,
        message: str | None = None,
    ):
        self.status_code = status_code
        self.body = body
        if message:
            self.message = message
        elif body:
            self.message = f"HTTP {status_code}: {body}"
        else:
            self.message = f"HTTP {status_code}"
        super().__init__(self.message)


class GuardrailViolation(GuardrailsError):
    """A guardrail detected a violation."""

    def __init__(
        self,
        guardrail_type: str,
        name: str | None = None,
    ):
        self.guardrail_type = guardrail_type
        self.name = name

        parts = [guardrail_type]
        if name:
            parts.append(f"{name=}")
        error_message = " | ".join(parts)

        super().__init__(error_message)


class GuardrailsTriggered(GuardrailsError):
    """Multiple guardrails detected violations."""

    def __init__(self, triggered: list[GuardrailViolation]):
        self.triggered = triggered
        messages = [str(t) for t in triggered]
        super().__init__(
            f"{len(triggered)} guardrails triggered: " + "\n".join(messages)
        )
