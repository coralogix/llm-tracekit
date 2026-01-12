from __future__ import annotations

from typing import Literal, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._constants import DEFAULT_THRESHOLD
from ._models import GuardrailsTarget, PIICategory, Role


class GuardrailRequest(BaseModel):
    application: str
    subsystem: str
    messages: list[Message] | None = None
    guardrails: list[GuardrailConfigType]
    target: GuardrailsTarget
    timeout: int

class BaseGuardrailConfig(BaseModel):
    threshold: float = Field(default=DEFAULT_THRESHOLD, ge=0.0, le=1.0)


class PII(BaseGuardrailConfig):
    type: Literal["pii"] = "pii"
    categories: list[PIICategory] = Field(default_factory=lambda: list(PIICategory))


class PromptInjection(BaseGuardrailConfig):
    type: Literal["prompt_injection"] = "prompt_injection"

class TestPolicy(BaseGuardrailConfig):
    type: Literal["test_policy"] = "test_policy"


GuardrailConfigType = PII | PromptInjection | TestPolicy

class Message(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: Role
    content: Any

    def __init__(self, data: dict[str, Any] | None = None, **kwargs: Any) -> None:
        if data is not None:
            super().__init__(**data)
        else:
            super().__init__(**kwargs)

    @model_validator(mode="before")
    @classmethod
    def handle_tool_calls(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        content = data.get("content")
        tool_calls = data.get("tool_calls")
        if not content and tool_calls:
            data["content"] = _format_tool_calls(tool_calls)
        elif content is None:
            data["content"] = ""
        return data

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: str | Role) -> Role:
        if isinstance(v, Role):
            return v
        if isinstance(v, str):
            role = Role(v.lower())
            return role

def _format_tool_calls(tool_calls: list[Any]) -> str:
    """Convert OpenAI tool_calls to a readable string for guardrails."""
    parts = []
    for tc in tool_calls:
        if hasattr(tc, "function"):
            # OpenAI object
            parts.append(f"[tool_call: {tc.function.name}({tc.function.arguments})]")
        elif isinstance(tc, dict) and "function" in tc:
            # Dict format
            func = tc["function"]
            parts.append(f"[tool_call: {func.get('name', 'unknown')}({func.get('arguments', '{}')})]")
    return " ".join(parts) if parts else ""

