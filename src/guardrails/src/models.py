from typing import List
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
    pass


class PII(BaseGuardrail):
    name: str
    categories: List[str] = Field(default_factory=list)
    threshold: float = GR_THRESHOLD

class PromptInjection(BaseGuardrail):
    name: str
    categories: List[str] = Field(default_factory=list)
    threshold: float = GR_THRESHOLD

class CustomGuardrail(BaseGuardrail):
    name: str
    criteria: str
    threshold: float = GR_THRESHOLD


class GuardrailsResult(BaseModel):
    name: str
    detected: bool
    score: float
    explanation: str
    threshold: float = GR_THRESHOLD



