from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field

from .constants import DEFAULT_THRESHOLD
from .enums import PIICategorie


class BaseGuardrailConfig(BaseModel):
    threshold: float = Field(default=DEFAULT_THRESHOLD, ge=0.0, le=1.0)


class PII(BaseGuardrailConfig):
    type: Literal["pii"] = "pii"
    categories: List[PIICategorie] = Field(default_factory=lambda: list(PIICategorie))


class PromptInjection(BaseGuardrailConfig):
    type: Literal["prompt_injection"] = "prompt_injection"


GuardrailConfigType = Union[PII, PromptInjection]


class GuardrailRequest(BaseModel):
    application: str
    subsystem: str
    prompt: Optional[str] = None
    response: Optional[str]
    guardrails_configs: List[GuardrailConfigType]
    timeout: int

