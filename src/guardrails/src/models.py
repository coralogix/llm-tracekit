from typing import List, Union, Literal
from pydantic import BaseModel, Field
from typing_extensions import Annotated
from enum import Enum

GR_THRESHOLD = 0.7

class PIICategories(Enum):
    email = "email"
    phone = "phone"
    name = "name"
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


class BaseGuardrail(BaseModel):
    name: str
    type: str

class PII(BaseGuardrail):
    type: Literal["pii"] = "pii"
    categories: List[str] = Field(default_factory=list)
    threshold: float = GR_THRESHOLD


class PromptInjection(BaseGuardrail):
    type: Literal["prompt_injection"] = "prompt_injection"
    categories: List[str] = Field(default_factory=list)
    threshold: float = GR_THRESHOLD


class CustomGuardrail(BaseGuardrail):
    type: Literal["custom"] = "custom"
    criteria: str
    threshold: float = GR_THRESHOLD


class GuardrailsRequest(BaseModel):
    api_key: str
    application_name: str
    subsystem_name: str
    message: str
    guardrails_config: List[Annotated[Union[PII, PromptInjection, CustomGuardrail], Field(discriminator="type")]]


class GuardrailsResult(BaseModel):
    name: str
    detected: bool
    score: float
    explanation: str
    threshold: float = GR_THRESHOLD


class GuardrailsResponse(BaseModel):
    results: List[GuardrailsResult]
    guardrails_config: List[Annotated[Union[PII, PromptInjection, CustomGuardrail], Field(discriminator="type")]]



