from typing import Literal, Any

from pydantic import BaseModel, Field, field_validator

from ._constants import DEFAULT_THRESHOLD
from ._models import GuardrailsTarget, PIICategory, Role


class BaseGuardrailConfig(BaseModel):
    threshold: float = Field(default=DEFAULT_THRESHOLD, ge=0.0, le=1.0)


class PII(BaseGuardrailConfig):
    type: Literal["pii"] = "pii"
    categories: list[PIICategory] = Field(default_factory=lambda: list(PIICategory))


class PromptInjection(BaseGuardrailConfig):
    type: Literal["prompt_injection"] = "prompt_injection"


GuardrailConfigType = PII | PromptInjection


class Message(BaseModel):
    role: Role
    content: Any

    def __init__(self, data: dict[str, Any] | None = None, **kwargs: Any) -> None:
        if data is not None:
            super().__init__(**data)
        else:
            super().__init__(**kwargs)

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: str | Role) -> Role:
        if isinstance(v, Role):
            return v
        if isinstance(v, str):
            role = Role(v.lower())
            return role


class GuardrailRequest(BaseModel):
    application: str
    subsystem: str
    messages: list[Message] | None = None
    guardrails: list[GuardrailConfigType]
    target: GuardrailsTarget
    timeout: int
