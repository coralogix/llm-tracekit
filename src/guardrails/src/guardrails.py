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
        
        return guardrails_response





