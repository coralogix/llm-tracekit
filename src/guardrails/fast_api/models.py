from pydantic import BaseModel
from typing import List
from guardrails.src.models import BaseGuardrail

class GuardrailsRequest(BaseModel):
    message: str
    guardrails_config: List[BaseGuardrail]
    api_key: str
    application_name: str
    subsystem_name: str

class GuardrailsResult(BaseModel):
    name: str
    detected: bool
    score: float
    explanation: str

class GuardrailsResponse(BaseModel):
    results: List[GuardrailsResult]
    guardrails_config: List[BaseGuardrail]


