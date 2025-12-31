"""Using Guardrails with LiteLLM."""

import asyncio
import litellm
from guardrails import Guardrails, PII, PromptInjection, PIICategorie, GuardrailsTriggered, convert_litellm
from guardrails.models.enums import GuardrailsTarget


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
        guard_messages = convert_litellm(response.model_dump(), messages)

        try:
            await guardrails.guard(guard_messages, config, GuardrailsTarget.response)
            print(f"Assistant: {response.choices[0].message.content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
