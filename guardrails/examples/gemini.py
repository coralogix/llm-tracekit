"""Using Guardrails with Google Gemini."""

import asyncio
from google import genai
from cx_guardrails import (
    Guardrails,
    PII,
    PromptInjection,
    PIICategory,
    GuardrailsTriggered,
    GuardrailsTarget,
    setup_export_to_coralogix,
)

setup_export_to_coralogix(
    service_name="guardrails-gemini-example",
    application_name="my_application",
    subsystem_name="my_subsystem",
    capture_content=True,
)

TEST_PII = "your email is example@example.com"

guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)
client = genai.Client()


async def main():
    user_content = "What is the capital of France?"
    contents = [{"role": "user", "parts": [{"text": user_content}]}]
    config = [PII(categories=[PIICategory.EMAIL_ADDRESS]), PromptInjection()]

    async with guardrails.guarded_session():
        messages = [{"role": "user", "content": user_content}]
        try:
            await guardrails.guard(
                guardrails=[PromptInjection()],
                messages=messages,
                target=GuardrailsTarget.PROMPT,
            )
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash", contents=contents
        )
        response_content = str(response.text) + TEST_PII
        messages.append({"role": "assistant", "content": response_content})

        try:
            await guardrails.guard(
                guardrails=config,
                messages=messages,
                target=GuardrailsTarget.RESPONSE,
            )
            print(f"Assistant: {response.text}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
