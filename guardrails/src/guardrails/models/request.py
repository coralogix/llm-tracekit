from typing import Literal, Union, Any

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


class TestPolicy(BaseGuardrailConfig):
    type: Literal["test_policy"] = "test_policy"

GuardrailConfigType = Union[PII, PromptInjection, TestPolicy]


ROLE_MAP = {
    "user": Role.USER,
    "assistant": Role.ASSISTANT,
    "system": Role.SYSTEM,
    "tool": Role.TOOL,
}


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
    def normalize_role(cls, v: Union[str, Role]) -> Role:
        if isinstance(v, Role):
            return v
        if isinstance(v, str):
            role = ROLE_MAP.get(v.lower())
            if role is None:
                raise ValueError(
                    f"Invalid role '{v}'. Must be one of: {set(ROLE_MAP.keys())}"
                )
            return role


class GuardrailRequest(BaseModel):
    application: str
    subsystem: str
    messages: list[Message] | None = None
    guardrails: list[GuardrailConfigType]
    target: GuardrailsTarget
    timeout: int

