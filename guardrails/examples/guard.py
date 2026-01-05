"""
Guard API Usage - Direct Message-Based API
==========================================

Shows how to use the guard() API directly with message dictionaries,
giving you full control over the conversation format.

Features:
    - Direct guard() API with message list
    - Explicit target specification (PROMPT vs RESPONSE)
    - Compatible with any LLM message format

Prerequisites:
    - pip install guardrails
    - Set CX_TOKEN and CX_ENDPOINT for Coralogix (optional)

Usage:
    python guard_example.py
"""

import asyncio
from cx_guardrails import (
    Guardrails,
    GuardrailsTarget,
    GuardrailsTriggered,
    PII,
    PIICategory,
    PromptInjection,
    PIICategory,
    GuardrailsTriggered,
    GuardrailsTarget,
    setup_export_to_coralogix,
)

setup_export_to_coralogix(service_name="guardrails-guard-example")
guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)


async def main():
    messages = [{"role": "user", "content": "What is the capital of France?"}]
    config = [PII(categories=[PIICategory.EMAIL_ADDRESS]), PromptInjection()]

    # Build messages incrementally
    messages = []

    async with guardrails.guarded_session():
        # Append user input and guard the prompt
        messages.append({"role": "user", "content": user_input})
        try:
            await guardrails.guard(config, messages, GuardrailsTarget.PROMPT)
        except GuardrailsTriggered as e:
            print(f"Prompt blocked: {e}")
            return

        # Your LLM call goes here
        llm_response = "The capital of France is Paris."

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": llm_response})
        try:
            await guardrails.guard(config, messages, GuardrailsTarget.RESPONSE)
            print(f"Assistant: {llm_response}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_pii_blocked():
    guardrails = Guardrails()
    user_input = "What is the capital of France?"

    # Build messages incrementally
    messages = []

    async with guardrails.guarded_session():
        # Append user input and guard the prompt
        messages.append({"role": "user", "content": user_input})
        try:
            await guardrails.guard(messages, PROMPT_GUARDRAILS, GuardrailsTarget.PROMPT)
        except GuardrailsTriggered as e:
            print(f"Prompt blocked: {e}")
            return

        # Simulated LLM response with PII leaking
        llm_response = "The capital of France is Paris." + TEST_PII

        # Append assistant response (with PII) and guard it
        messages.append({"role": "assistant", "content": llm_response})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {llm_response}")
        except GuardrailsTriggered as e:
            print(f"Response blocked (PII detected): {e}")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


async def main():
    await example_basic()
    await example_pii_blocked()


if __name__ == "__main__":
    asyncio.run(main())
