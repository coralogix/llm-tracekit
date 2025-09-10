import httpx
from typing import List
from .models import BaseGuardrail, GuardrailsResult

from .http_utils import _with_retries


class Guardrails:
    def __init__(self, api_key: str, application_name: str, subsystem_name: str, timeout: int = 10, retries: int = 3) -> None:
            self.api_key = api_key
            self.application_name = application_name
            self.subsystem_name = subsystem_name

            self.base_url = "https://api.guardrails.ai/v1"
            self.timeout = timeout
            self.retries = retries

            self._client = httpx.AsyncClient(
                    base_url=self.base_url, 
                    # headers={"Authorization": f"Bearer {self.api_key}"}
                    timeout=self.timeout,
                )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def run(self, message: str, guardrails_config: List[BaseGuardrail]) -> List[GuardrailsResult]:
        print("Running guardrails on message: \n",
        message,
        "\nwith guardrails config: \n",
        guardrails_config)
        return []

        # async def _run(message: str, guardrails_config: List[BaseGuardrail]) -> List[GuardrailsResult]:
        #     return await self._client.post(
        #         "/v1/guardrails",
        #         json={"message": message, "guardrails_config": guardrails_config}
        #     )

        # response = await _with_retries(_run(message, guardrails_config))
        # return response.json()






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









