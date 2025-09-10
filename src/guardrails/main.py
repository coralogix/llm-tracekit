import asyncio
from guardrails.src.guardrails import Guardrails
from guardrails.src.models import PII, PromptInjection, CustomGuardrail, PIICategories, PromptInjectionCategories
from guardrails.src.error import APIConnectionError, APITimeoutError, APIResponseError


async def main():
    guardrails = Guardrails(api_key="1234567890", application_name="app-test", subsystem_name="subsystem-test")

    guardrails_config = [
        PII(name="pii", categories=PIICategories),
        PromptInjection(name="prompt_injection", categories=PromptInjectionCategories),
        CustomGuardrail(name="custom", criteria="please evaluate the message and return a boolean value"),
    ]


    results = await guardrails.run(
        message="Hi, I'm John Doe. My email is john.doe@example.com. My phone number is 123-456-7890.", 
        guardrails_config=guardrails_config)
    print("results: \n", results)


if __name__ == "__main__":
    asyncio.run(main())