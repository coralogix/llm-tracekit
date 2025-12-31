"""Using Guardrails with Google Gemini."""

import asyncio
from google import genai
from guardrails import Guardrails, PII, PromptInjection, PIICategorie, GuardrailsTriggered, convert_gemini
from guardrails.models.enums import GuardrailsTarget


async def main():
    guardrails = Guardrails()
    client = genai.Client()
    contents = [{"role": "user", "parts": [{"text": "What is the capital of France?"}]}]
    config = [PII(categories=[PIICategorie.email_address]), PromptInjection()]

    async with guardrails.guarded_session():
        try:
            await guardrails.guard(convert_gemini(None, contents), [PromptInjection()], GuardrailsTarget.prompt)
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        response = await client.aio.models.generate_content(model="gemini-2.0-flash", contents=contents)
        messages = convert_gemini(response, contents)

        try:
            await guardrails.guard(messages, config, GuardrailsTarget.response)
            print(f"Assistant: {response.text}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
