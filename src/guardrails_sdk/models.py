from typing import Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field, ConfigDict
from typing_extensions import Annotated
from enum import Enum, StrEnum, auto

GR_THRESHOLD = 0.7


class GuardrailsEndpoint(Enum):
    PROMPT_ENDPOINT = "guard_prompt"
    RESPONSE_ENDPOINT = "guard_response"

class PIICategories(StrEnum):
    email = auto()
    phone = auto()
    user_name = auto()
    address = auto()
    credit_card = auto()
    social_security_number = auto()
    passport = auto()
    driver_license = auto()

    @classmethod
    def values(cls):
        return [category.value for category in cls.__members__.values()]

class PromptInjectionCategories(StrEnum):
    change_personality = auto()
    forget_instructions = auto()
    illegal_topics = auto()
    say_command = auto()
    instructions_leakage = auto()
    code_execution = auto()
    contains_emojis = auto()
    contains_encoding = auto()
    prompt_repetition = auto()
    contains_gibberish = auto()

    @classmethod
    def values(cls):
        return [category.value for category in cls.__members__.values()]

class GuardrailType(StrEnum):
    pii =  auto()
    prompt_injection = auto()
    custom = auto()

class Labes(StrEnum):
    P1="P1"

class PII(BaseModel):
    type: Literal["pii"] = "pii"
    categories: List[str] = Field(default_factory=list)
    threshold: float = Field(default=GR_THRESHOLD, ge=0.0, le=1.0)


class PromptInjection(BaseModel):
    type: Literal["prompt_injection"] = "prompt_injection"
    threshold: float = Field(default=GR_THRESHOLD, ge=0.0, le=1.0)

class CustomGuardrail(BaseModel):
    type: Literal["custom"] = "custom"
    name: str
    criteria: str
    threshold: float = Field(default=GR_THRESHOLD, ge=0.0, le=1.0)


class GuardrailsRequest(BaseModel):
    api_key: str
    invocation_id: str
    application: str
    subsystem: str
    domain_url: str
    prompt: str
    response: Optional[str]
    guardrails_configs: List[Annotated[Union[PII, PromptInjection, CustomGuardrail], Field(discriminator="type")]]


class GuardrailsResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)  # Allow both 'type' and 'detection_type'
    
    detection_type: GuardrailType = Field(alias="type")
    detected_categories: Optional[Any] = None
    label: Optional[Labes] = None
    name: Optional[str] = None
    detected: bool
    score: float = Field(ge=0.0, le=1.0)
    explanation: Optional[str] = None
    config: Optional[Any] = None
    threshold: float = Field(default=GR_THRESHOLD, ge=0.0, le=1.0)


class GuardrailsResponse(BaseModel):
    results: List[GuardrailsResult]
    invocation_id: str