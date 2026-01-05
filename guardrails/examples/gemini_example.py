"""Using Guardrails with Google Gemini."""

import asyncio
from google import genai
from guardrails import (
    Guardrails,
    PII,
    PromptInjection,
    PIICategory,
    GuardrailsTriggered,
    GuardrailsTarget,
)

TEST_PII = "your email is example@example.com"


async def main():
    guardrails = Guardrails()
    client = genai.Client()
    user_content = "What is the capital of France?"
    contents = [{"role": "user", "parts": [{"text": user_content}]}]
    config = [PII(categories=[PIICategory.EMAIL_ADDRESS]), PromptInjection()]

    async with guardrails.guarded_session():
        # Guard prompt
        messages = [{"role": "user", "content": user_content}]
        try:
            await guardrails.guard(
                messages, [PromptInjection()], GuardrailsTarget.PROMPT
            )
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash", contents=contents
        )
        response_content = str(response.text) + TEST_PII
        messages.append({"role": "assistant", "content": response_content})

        try:
            await guardrails.guard(messages, config, GuardrailsTarget.RESPONSE)
            print(f"Assistant: {response.text}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
