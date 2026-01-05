"""Using Guardrails with OpenAI SDK."""

import asyncio
from openai import AsyncOpenAI
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
    client = AsyncOpenAI()
    messages = [{"role": "user", "content": "What is the capital of France?"}]
    config = [PII(categories=[PIICategory.EMAIL_ADDRESS]), PromptInjection()]

    async with guardrails.guarded_session():
        try:
            await guardrails.guard(
                messages, [PromptInjection()], GuardrailsTarget.PROMPT
            )
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        response = await client.chat.completions.create(
            model="gpt-4o-mini", messages=messages
        )
        response_content = response.choices[0].message.content + TEST_PII
        messages.append({"role": "assistant", "content": response_content})

        try:
            await guardrails.guard(messages, config, GuardrailsTarget.RESPONSE)
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
