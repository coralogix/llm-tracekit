"""Using Guardrails with LiteLLM."""

import asyncio
import litellm
from guardrails import Guardrails, PII, PromptInjection, PIICategorie, GuardrailsTriggered
from guardrails.models.enums import GuardrailsTarget

TEST_PII = "your email is example@example.com"


async def main():
    guardrails = Guardrails()
    messages = [{"role": "user", "content": "What is the capital of France?"}]
    config = [PII(categories=[PIICategorie.email_address]), PromptInjection()]

    async with guardrails.guarded_session():
        try:
            await guardrails.guard(messages, [PromptInjection()], GuardrailsTarget.prompt)
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        response = await litellm.acompletion(model="gpt-4o-mini", messages=messages)
        response_content = response.choices[0].message.content + TEST_PII
        messages.append({"role": "assistant", "content": response_content})

        try:
            await guardrails.guard(messages, config, GuardrailsTarget.response)
            print(f"Assistant: {response_content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
