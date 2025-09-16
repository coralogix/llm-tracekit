from fastapi import APIRouter

# try:
#     # When using uvicorn with PYTHONPATH=./src
#     from guardrails.fast_api.models import GuardrailsRequest, GuardrailsResponse, GuardrailsResult
# except ImportError:
#     try:
#         # When imported as part of package
#         from .models import GuardrailsRequest, GuardrailsResponse, GuardrailsResult
#     except ImportError:
#         # When running directly - need to import from src.models since models.py imports from there
#         import sys
#         import os
#         current_dir = os.path.dirname(os.path.abspath(__file__))
#         parent_dir = os.path.dirname(current_dir)
#         if parent_dir not in sys.path:
#             sys.path.insert(0, parent_dir)
#         from src.models import GuardrailsRequest, GuardrailsResponse, GuardrailsResult

from guardrails.fast_api.models import GuardrailsRequest, GuardrailsResponse, GuardrailsResult

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


