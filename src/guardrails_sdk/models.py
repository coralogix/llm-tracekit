from typing import Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator# ty: ignore[unresolved-import]
from typing_extensions import Annotated
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
    def values(cls):
        return [category.value for category in cls.__members__.values()]

class PromptInjectionCategories(Enum):
    change_personality = "change_personality"
    forget_instructions = "forget_instructions"
    illegal_topics = "illegal_topics"
    say_command = "say_command"
    instructions_leakage = "instructions_leakage"
    code_execution = "code_execution"
    contains_emojis = "contains_emojis"
    contains_encoding = "contains_encoding"
    prompt_repetition = "prompt_repetition"
    contains_gibberish = "contains_gibberish"

    @classmethod
    def values(cls):
        return [category.value for category in cls.__members__.values()]

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
    categories: List[PIICategories]


class PromptInjection(BaseGuardrailConfig):
    type: Literal["prompt_injection"] = "prompt_injection"

class CustomGuardrail(BaseGuardrailConfig):
    type: Literal["custom"] = "custom"
    name: str
    criteria: str


class GuardrailsRequest(BaseModel):
    api_key: str
    application: str
    subsystem: str
    domain_url: str
    prompt: Optional[str] = None
    response: Optional[str]
    guardrails_configs: List[Annotated[Union[PII, PromptInjection, CustomGuardrail], Field(discriminator="type")]]


class GuardrailsResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)  # Allow both 'type' and 'detection_type'
    detection_type: GuardrailType = Field(alias="type")
    detected_categories: Optional[Any] = None
    label: Optional[Labels] = None
    name: Optional[str] = None
    detected: bool
    score: float = Field(ge=0.0, le=1.0)
    explanation: Optional[str] = None
    config: Optional[Any] = None
    threshold: float = Field(default=GR_THRESHOLD, ge=0.0, le=1.0)
    
    @field_validator("detection_type", mode="before")
    @classmethod
    def normalize_type(cls, v: Any) -> Any:
        if isinstance(v, str):
            # Convert to lowercase to handle case variations from API
            return v.lower()
        return v


class GuardrailsResponse(BaseModel):
    results: List[GuardrailsResult] = Field(default_factory=list)

class GuardrailsTarget(Enum):
    prompt = "prompt"
    response = "response"