from fastapi import APIRouter
from guardrails.src.guardrails import Guardrails
from guardrails.src.models import GuardrailsRequest, GuardrailsResponse, GuardrailsResult, BaseGuardrail

router = APIRouter()

############################
# !! This is a mock API !! #
############################

@router.get("/guardrails/health")
async def health() -> str:
    return "OK"


@router.post("/guardrails/run")
async def guardrails(request: GuardrailsRequest) -> GuardrailsResponse:
    print("Running guardrails on message: \n",
    request.message,
    "\nwith guardrails config: \n",
    request.guardrails_config,
    "\nwith api key: \n",
    request.api_key,
    "\nwith application name: \n",
    request.application_name,
    "\nwith subsystem name: \n",
    request.subsystem_name,
    )

    results = GuardrailsResult(name="PII-email", detected=True, score=0.9, explanation="found email address")
    
    return GuardrailsResponse(results=[results], guardrails_config=request.guardrails_config)


