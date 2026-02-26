from __future__ import annotations

from typing import Literal, Any, Optional


from pydantic import BaseModel, Field, field_validator

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


class CustomEvaluationExample(BaseModel):
    conversation: str
    score: int = Field(ge=0, le=1)


class Custom(BaseGuardrailConfig):
    type: Literal["custom"] = "custom"
    name: str
    instructions: str
    violates: str
    safe: str
    examples: Optional[list[CustomEvaluationExample]] = None
    should_include_system_prompt: bool = False 

    @field_validator("instructions", mode="after")
    @classmethod
    def validate_magic_word_used(cls, v: str) -> str:
        magic_words = ["{prompt}", "{response}", "{history}"]
        if not any(magic in v for magic in magic_words):
            raise ValueError(
                f"Instructions must contain at least one of: {', '.join(magic_words)}"
            )
        return v


class Toxicity(BaseGuardrailConfig):
    type: Literal["toxicity"] = "toxicity"


GuardrailConfigType = PII | PromptInjection | Custom | Toxicity


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
