from typing import List, Union
from pydantic import BaseModel, Field


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

class PII(BaseGuardrail):
    categories: List[str] = Field(default_factory=list)
    threshold: float = GR_THRESHOLD


class PromptInjection(BaseGuardrail):
    categories: List[str] = Field(default_factory=list)
    threshold: float = GR_THRESHOLD


class CustomGuardrail(BaseGuardrail):
    criteria: str
    threshold: float = GR_THRESHOLD


class GuardrailsRequest(BaseModel):
    api_key: str
    application_name: str
    subsystem_name: str
    message: str
    guardrails_config: List[Union[PII, PromptInjection, CustomGuardrail]]


class GuardrailsResult(BaseModel):
    name: str
    detected: bool
    score: float
    explanation: str
    threshold: float = GR_THRESHOLD


class GuardrailsResponse(BaseModel):
    results: List[GuardrailsResult]
    guardrails_config: List[Union[PII, PromptInjection, CustomGuardrail]]



