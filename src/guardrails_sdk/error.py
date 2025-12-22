from __future__ import annotations

class GuardrailsError(Exception):
    """Base exception for all SDK errors."""

class GuardrailsAPIConnectionError(GuardrailsError):
    """Network/transport errors."""

class GuardrailsAPITimeoutError(GuardrailsError):
    """Request timed out."""

class GuardrailsAPIResponseError(GuardrailsError):
    """Non-2xx HTTP response."""

class GuardrailTriggered(GuardrailsError):
    """A guardrail detected a violation."""
    
    def __init__(
        self,
        guardrail_type: str,
        name: str | None = None,
        score: float | None = None,
        explanation: str | None = None,
        detected_categories: str | None = None,
        message: str | None = None,
    ):
        self.guardrail_type = guardrail_type
        self.name = name
        self.score = score
        self.explanation = explanation
        self.detected_categories = detected_categories
        if message:
            error_message = message
        else:
            parts = [f"Guardrail triggered: {guardrail_type}"]
            if name:
                parts.append(f"{name=}")
            if score is not None:
                parts.append(f"score={score:.3f}")
            if explanation:
                parts.append(f"{explanation=}")
            if detected_categories:
                parts.append(f"{detected_categories=}")
            error_message = " | ".join(parts)
        
        super().__init__(error_message)
