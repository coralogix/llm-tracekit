from pydantic import BaseModel
from typing import List
from ..src.models import BaseGuardrail, GuardrailsResult

class GuardrailsRequest(BaseModel):
    message: str
    guardrails_config: List[BaseGuardrail]

class GuardrailsResponse(BaseModel):
    results: List[GuardrailsResult]
    guardrails_config: List[BaseGuardrail]

class GuardrailsResult(BaseModel):
    name: str
    detected: bool
    score: float
    explanation: str
