from optparse import Option
from typing import Any, List, Optional, Literal, Union
from pydantic import BaseModel, Field, field_validator
from enum import Enum

GR_THRESHOLD = 0.7


class GuardrailsEndpoint(Enum):
    PROMPT_ENDPOINT = "guard_prompt"
    RESPONSE_ENDPOINT = "guard_response"

class PIICategories(Enum):
    email = "email"
    phone = "phone"
    user_name = "user_name"
    address = "address"
    credit_card = "credit_card"
    social_security_number = "social_security_number"
    passport = "passport"
    driver_license = "driver_license"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]

class GuardrailType(Enum):
    pii =  "pii"
    prompt_injection = "prompt_injection"
    custom = "custom"

class Labels(Enum):
    P1="P1"

class BaseGuardrailConfig(BaseModel):
    threshold: float = Field(default=GR_THRESHOLD, ge=0.0, le=1.0)

class PII(BaseGuardrailConfig):
    type: Literal["pii"] = "pii"
    categories: List[PIICategories] = Field(default_factory=lambda: list(PIICategories))

class PromptInjection(BaseGuardrailConfig):
    type: Literal["prompt_injection"] = "prompt_injection"

class CustomGuardrail(BaseGuardrailConfig):
    type: Literal["custom"] = "custom"
    name: str
    criteria: str

GuardrailConfigType = Union[PII, PromptInjection, CustomGuardrail]

class GuardrailRequest(BaseModel):
    application: str
    subsystem: str
    prompt: Optional[str] = None
    response: Optional[str]
    guardrails_configs: List[GuardrailConfigType]
    timeout: int

class GuardrailsResultBase(BaseModel):
    type: GuardrailType = Field(alias="type")
    label: Optional[Labels] = None
    detected: bool
    threshold: float = Field(default=GR_THRESHOLD, ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=1.0)
    
    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.lower()
        return v

class PIIResult(GuardrailsResultBase):
    detected_categories: Optional[Any] = None
    
class PromptInjectionResult(GuardrailsResultBase):
    pass

class CustomGuardrailResults(GuardrailsResultBase):
    name: Optional[str] = None

GuardrailsResponseType =  Union[PIIResult, PromptInjectionResult, CustomGuardrailResults]
class GuardrailsResponse(BaseModel):
    results: List[GuardrailsResponseType] = Field(default_factory=list)

class GuardrailsTarget(Enum):
    prompt = "prompt"
    response = "response"