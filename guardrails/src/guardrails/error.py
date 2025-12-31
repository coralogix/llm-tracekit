from __future__ import annotations
from typing import List, Optional


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
        body: Optional[str] = None,
        message: Optional[str] = None,
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
        name: Optional[str] = None,
        score: Optional[float] = None,
        detected_categories: Optional[List[str]] = None,
        message: Optional[str] = None,
    ):
        self.guardrail_type = guardrail_type
        self.name = name
        self.score = score
        self.detected_categories = detected_categories
        if message:
            error_message = message
        else:
            parts = [f"Guardrail triggered: {guardrail_type}"]
            if name:
                parts.append(f"{name=}")
            if score is not None:
                parts.append(f"score={score:.3f}")
            if detected_categories:
                parts.append(f"{detected_categories=}")
            error_message = " | ".join(parts)

        super().__init__(error_message)


class GuardrailsTriggered(GuardrailsError):
    """Multiple guardrails detected violations."""

    def __init__(self, triggered: List[GuardrailViolation]):
        self.triggered = triggered
        messages = [str(t) for t in triggered]
        super().__init__(
            f"{len(triggered)} guardrails triggered:\n" + "\n".join(messages)
        )
