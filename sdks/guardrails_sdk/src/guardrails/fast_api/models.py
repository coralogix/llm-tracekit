from pydantic import BaseModel
from typing import List

# try:
#     # When using uvicorn with PYTHONPATH=./src
#     from guardrails.src.models import BaseGuardrail
# except ImportError:
#     try:
#         # When imported as part of package
#         from ..src.models import BaseGuardrail
#     except ImportError:
#         # When running directly
#         import sys
#         import os
#         current_dir = os.path.dirname(os.path.abspath(__file__))
#         parent_dir = os.path.dirname(current_dir)
#         if parent_dir not in sys.path:
#             sys.path.insert(0, parent_dir)
#         from src.models import BaseGuardrail

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


