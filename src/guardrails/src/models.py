from typing import List, Union, Literal
from pydantic import BaseModel, Field, Discriminator
from typing_extensions import Annotated


GR_THRESHOLD = 0.7

PIICategories = ["email", "phone", "name", "address", "credit_card", "social_security_number", "passport", "driver_license"]

PromptInjectionCategories = [
        "change_personality", 
        "forget_instructions", 
        "illegal_topics", 
        "say_command", 
        "instructions_leakage", 
        "code_execution", 
        "contains_emojis", 
        "contains_encoding", 
        "prompt_repetition", 
        "contains_gibberish"
    ]


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



