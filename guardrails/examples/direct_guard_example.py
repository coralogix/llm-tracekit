"""Using the direct guard() API with dict messages."""

import asyncio
from guardrails import (
    Guardrails,
    PII,
    PromptInjection,
    PIICategorie,
    GuardrailsTriggered,
)
from guardrails.models.enums import GuardrailsTarget


async def main():
    guardrails = Guardrails()
    messages = [{"role": "user", "content": "What is the capital of France?"}]
    config = [PII(categories=[PIICategorie.email_address]), PromptInjection()]

    async with guardrails.guarded_session():
        try:
            await guardrails.guard(messages, config, GuardrailsTarget.prompt)
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        llm_response = "The capital of France is Paris."  # Your LLM call here
        messages.append({"role": "assistant", "content": llm_response})

        try:
            await guardrails.guard(messages, config, GuardrailsTarget.response)
            print(f"Assistant: {llm_response}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
