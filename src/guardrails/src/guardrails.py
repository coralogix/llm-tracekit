import httpx
import json
from typing import List
from .models import BaseGuardrail, GuardrailsRequest, GuardrailsResult, GuardrailsResponse

from .http_utils import _with_retries


class Guardrails:
    def __init__(self, api_key: str, application_name: str, subsystem_name: str, timeout: int = 10, retries: int = 3) -> None:
            self.api_key = api_key
            self.application_name = application_name
            self.subsystem_name = subsystem_name

            #self.base_url = "https://api.guardrails.ai/v1"
            self.base_url = "http://127.0.0.1:8000"
            self.timeout = timeout
            self.retries = retries

            self._client = httpx.AsyncClient(
                    base_url=self.base_url, 
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

    async def run(self, message: str, guardrails_config: List[BaseGuardrail]) -> List[GuardrailsResult]:
        guardrails_request = GuardrailsRequest(
            message=message, 
            guardrails_config=guardrails_config,
            api_key=self.api_key,
            application_name=self.application_name,
            subsystem_name=self.subsystem_name
        )

        async def _run() -> httpx.Response:
            print("running guardrails with request: \n", guardrails_request)
            guardrails_json_request = guardrails_request.model_dump()
            print("json request: \n", guardrails_json_request)
            guardrails_json_request["guardrails_config"] = [g.model_dump() for g in guardrails_request.guardrails_config]
            print("guardrails json request: \n", guardrails_json_request)
            response = await self._client.post(
                "/guardrails/run",
                json=guardrails_json_request
            )
            
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.text}")
            
            return response

        http_response = await _with_retries(_run)
        
        if http_response.status_code >= 400:
            raise Exception(f"HTTP {http_response.status_code}: {http_response.text}")
        
        guardrails_response = GuardrailsResponse.model_validate_json(http_response.text)
        print("response: \n", guardrails_response)
        return guardrails_response.results






#===========#
## Example ##
#===========#

# guardrails = Guardrails(api_key="1234567890", application_name="app-test", subsystem_name="subsystem-test")

# guardrails_config = [
#     PII(name="pii", categories=PIICategories),
#     PromptInjection(name="prompt_injection", categories=PromptInjectionCategories),
#     CustomGuardrail(name="custom", criteria="please evaluate the message and return a boolean value"),
# ]


# guardrails.run(
#     message="Hi, I'm John Doe. My email is john.doe@example.com. My phone number is 123-456-7890.", 
#     guardrails_config=guardrails_config)









