import asyncio
import sys
import os
from fastapi import FastAPI
    
try:
    # When using uvicorn with PYTHONPATH=./src
    from guardrails.src.guardrails import Guardrails
    from guardrails.src.models import PII, PromptInjection, CustomGuardrail, PIICategories, PromptInjectionCategories
    from guardrails.fast_api.routes import router as guardrails_router
except ImportError:
    try:
        # When imported as src.guardrails.main
        from .src.guardrails import Guardrails
        from .src.models import PII, PromptInjection, CustomGuardrail, PIICategories, PromptInjectionCategories
        from .fast_api.routes import router as guardrails_router
    except ImportError:
        # When running directly
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        from src.guardrails import Guardrails
        from src.models import PII, PromptInjection, CustomGuardrail, PIICategories, PromptInjectionCategories
        from fast_api.routes import router as guardrails_router


#############################
# !! For testing purpose !! #
#############################

# Create FastAPI app
app = FastAPI(title="Guardrails API")
app.include_router(guardrails_router)

async def main():
    print("Starting main")

    print("Guardrails config")
    guardrails_config = [
        PII(name="pii", categories=PIICategories),
        PromptInjection(name="prompt_injection", categories=PromptInjectionCategories),
        CustomGuardrail(name="custom", criteria="please evaluate the message and return a boolean value"),
    ]
    print("Guardrails instance")
    guardrails = Guardrails(api_key="1234567890", application_name="app-test", subsystem_name="subsystem-test")
    
    print("Running guardrails")
    results = await guardrails.run("This is a test message", guardrails_config)
    
    print("Results: \n", results) 


if __name__ == "__main__":
    asyncio.run(main())