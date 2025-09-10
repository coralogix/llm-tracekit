from fastapi import APIRouter
from .models import GuardrailsRequest, GuardrailsResponse

router = APIRouter()

@router.post("/guardrails")
async def guardrails(request: GuardrailsRequest) -> GuardrailsResponse:
    return GuardrailsResponse(results=request.guardrails_config)