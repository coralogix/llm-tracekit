"""Basic Guardrails usage with guard_prompt and guard_response."""

import asyncio
from guardrails import (
    Guardrails,
    PII,
    PromptInjection,
    PIICategorie,
    GuardrailsTriggered,
)


async def main():
    guardrails = Guardrails()
    user_input = "What is the capital of France?"
    config = [PII(categories=[PIICategorie.email_address]), PromptInjection()]

    async with guardrails.guarded_session():
        try:
            await guardrails.guard_prompt(user_input, config)
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        llm_response = "The capital of France is Paris."  # Your LLM call here

        try:
            await guardrails.guard_response(config, llm_response, user_input)
            print(f"Assistant: {llm_response}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
