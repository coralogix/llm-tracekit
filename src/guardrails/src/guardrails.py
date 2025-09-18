import httpx
import os
from typing import List, Union
from dotenv import load_dotenv
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential


from .models import GuardrailsRequest, GuardrailsResult, GuardrailsResponse, PII, PromptInjection, CustomGuardrail
from .http_utils import _with_retries

load_dotenv()

class Guardrails:
    def __init__(self, 
        api_key: str = None, 
        application_name: str = None, 
        subsystem_name: str = None, 
        domain_url: str = None,
        timeout: int = 10, 
        retries: int = 3,
    ) -> None:

            # Use environment variables as fallback if parameters not provided
            if api_key is None:
                api_key = os.getenv("API_KEY")
            if application_name is None:
                application_name = os.getenv("APPLICATION_NAME")
            if subsystem_name is None:
                subsystem_name = os.getenv("SUBSYSTEM_NAME")
            if domain_url is None:
                domain_url = os.getenv("DOMAIN_URL")
            
            # Strip whitespace and validate required parameters
            api_key = api_key.strip() if api_key else None
            application_name = application_name.strip() if application_name else None
            subsystem_name = subsystem_name.strip() if subsystem_name else None
            domain_url = domain_url.strip() if domain_url else None

            if not api_key:
                raise ValueError("api_key is required. Provide it as parameter or set API_KEY environment variable.")
            if not application_name:
                raise ValueError("application_name is required. Provide it as parameter or set APPLICATION_NAME environment variable.")
            if not subsystem_name:
                raise ValueError("subsystem_name is required. Provide it as parameter or set SUBSYSTEM_NAME environment variable.")
            if not domain_url:
                raise ValueError("domain_url is required. Provide it as parameter or set DOMAIN_URL environment variable.")
            
            self.api_key = api_key
            self.application_name = application_name
            self.subsystem_name = subsystem_name
            #self.domain_url = "https://api.guardrails.ai/v1"
            self.domain_url = domain_url if domain_url else "http://127.0.0.1:8000"
            self.timeout = timeout
            self.retries = retries

            self._client = httpx.AsyncClient(
                    base_url=self.domain_url, 
                    # headers={"Authorization": f"Bearer {self.api_key}"}
                    timeout=self.timeout,
                )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self): 
        print("Entering guardrails context")
        return self

    async def __aexit__(self, *_): 
        print("Exiting guardrails context")
        await self.aclose()

    async def run(self, message: str, guardrails_config: List[Union[PII, PromptInjection, CustomGuardrail]]) -> List[GuardrailsResult]:
        guardrails_request = GuardrailsRequest(
            message=message, 
            guardrails_config=guardrails_config,
            api_key=self.api_key,
            application_name=self.application_name,
            subsystem_name=self.subsystem_name,
            domain_url=self.domain_url
        )

        async def _run() -> httpx.Response:
            guardrails_json_request = guardrails_request.model_dump()
            guardrails_json_request["guardrails_config"] = [g.model_dump() for g in guardrails_request.guardrails_config]
            response = await self._client.post(
                "/guardrails/run",
                json=guardrails_json_request
            )
            return response

        http_response = await _with_retries(_run)
       
        if http_response.status_code >= 400:
            raise Exception(f"HTTP {http_response.status_code}: {http_response.text}")
        
        guardrails_response = GuardrailsResponse.model_validate_json(http_response.text)
        
        # For debugging
        print("\n\nHTTP response: \n", http_response.status_code, "\nGuardrails response: \n", guardrails_response, "\n\n")
        
        return guardrails_response.results
