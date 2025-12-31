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
    """Message model that accepts both Role enum and string role values.
    
    Examples:
        Message(role=Role.User, content="Hello")
        Message(role="user", content="Hello")  
        {"role": "user", "content": "Hello"}  # via GuardrailRequest
    """
    role: Role
    content: Any

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
        raise ValueError(f"Role must be a string or Role enum, got {type(v)}")


# Type alias for flexible message input (Message object or dict)
MessageInput = Union[Message, Dict[str, Any]]


def normalize_message(msg: MessageInput) -> Message:
    """Convert a dict or Message to a Message object."""
    if isinstance(msg, Message):
        return msg
    if isinstance(msg, dict):
        return Message(**msg)
    raise ValueError(f"Expected Message or dict, got {type(msg)}")


def normalize_messages(messages: Optional[List[MessageInput]]) -> Optional[List[Message]]:
    """Convert a list of dicts/Messages to a list of Message objects."""
    if messages is None:
        return None
    return [normalize_message(msg) for msg in messages]


class GuardrailRequest(BaseModel):
    application: str
    subsystem: str
    messages: Optional[List[Message]] = None
    guardrails_configs: List[GuardrailConfigType]
    target: GuardrailsTarget
    timeout: int

    @field_validator("messages", mode="before")
    @classmethod
    def validate_messages(cls, v: Optional[List[MessageInput]]) -> Optional[List[Message]]:
        return normalize_messages(v)
