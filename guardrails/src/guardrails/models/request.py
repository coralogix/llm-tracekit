from typing import List, Literal, Optional, Union, Any, Dict

from pydantic import BaseModel, Field, field_validator

from .constants import DEFAULT_THRESHOLD
from .enums import GuardrailsTarget, PIICategorie, Role


class BaseGuardrailConfig(BaseModel):
    threshold: float = Field(default=DEFAULT_THRESHOLD, ge=0.0, le=1.0)


class PII(BaseGuardrailConfig):
    type: Literal["pii"] = "pii"
    categories: List[PIICategorie] = Field(default_factory=lambda: list(PIICategorie))


class PromptInjection(BaseGuardrailConfig):
    type: Literal["prompt_injection"] = "prompt_injection"


GuardrailConfigType = Union[PII, PromptInjection]


# Role string to enum mapping
ROLE_MAP = {
    "user": Role.User,
    "assistant": Role.Assistant,
    "system": Role.System,
    "tool": Role.Tool,
}


class Message(BaseModel):
    role: Role
    content: Any

    def __init__(self, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
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
                raise ValueError(f"Invalid role '{v}'. Must be one of: {set(ROLE_MAP.keys())}")
            return role

class GuardrailRequest(BaseModel):
    application: str
    subsystem: str
    messages: Optional[List[Message]] = None
    guardrails_configs: List[GuardrailConfigType]
    target: GuardrailsTarget
    timeout: int
