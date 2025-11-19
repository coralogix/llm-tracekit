from fastapi import APIRouter
from ...src.models import GuardrailsRequest, GuardrailsResponse, GuardrailsResult, BaseGuardrail

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
    "\nwith domain url: \n",
    request.domain_url,
    )

    if request.guardrails_config is None:
        raise ValueError("Guardrails config is required")
    if request.api_key is None:
        raise ValueError("API key is required")
    if request.application_name is None:
        raise ValueError("Application name is required")
    if request.subsystem_name is None:
        raise ValueError("Subsystem name is required")
    if request.domain_url is None:
        raise ValueError("Domain url is required")

    def _build_guardrails_result(guardrail: BaseGuardrail):
        return GuardrailsResult(name=guardrail.name, detected=True, score=0.9, explanation="found trigger to the guardrail")

    if request.guardrails_config:
        results = [
                _build_guardrails_result(guardrail) for guardrail in request.guardrails_config
            ]
    else:
        results = []

    return GuardrailsResponse(results=results, guardrails_config=request.guardrails_config)


