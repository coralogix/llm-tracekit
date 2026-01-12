"""Basic Guardrails usage with guard_prompt and guard_response."""

import asyncio
from cx_guardrails import (
    Guardrails,
    PII,
    PromptInjection,
    PIICategory,
    GuardrailsTriggered,
    setup_export_to_coralogix,
)

setup_export_to_coralogix(service_name="guardrails-basic-example",
    application_name="my_application",
    subsystem_name="my_subsystem",
    capture_content=True,
)

guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)


async def main():
    user_input = "What is the capital of France?"

    async with guardrails.guarded_session():
        try:
            await guardrails.guard_prompt(
                guardrails=[
                    PII(categories=[PIICategory.EMAIL_ADDRESS]),
                    PromptInjection(),
                ],
                prompt=user_input,
            )
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        llm_response = "The capital of France is Paris."  # Your LLM call here

        try:
            await guardrails.guard_response(
                guardrails=[PII(categories=[PIICategory.EMAIL_ADDRESS])],
                response=llm_response,
                prompt=user_input,
            )
            print(f"Assistant: {llm_response}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
