from __future__ import annotations

class GuardrailsError(Exception):
    """Base exception for all SDK errors."""

class APIConnectionError(GuardrailsError):
    """Network/transport errors."""

class APITimeoutError(GuardrailsError):
    """Request timed out."""

class APIResponseError(GuardrailsError):
    """Non-2xx HTTP response."""
    def __init__(self, status_code: int, body: str | None = None, message: str | None = None):
        self.status_code = status_code
        self.body = body
        self.message = message or f"HTTP {status_code}"
        super().__init__(self.message)
