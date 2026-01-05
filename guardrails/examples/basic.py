"""
Basic Guardrails Usage - Getting Started
========================================

The simplest way to use Coralogix Guardrails with the convenience
methods guard_prompt() and guard_response().

Features:
    - Simple API for prompt and response guarding
    - PII detection
    - Prompt injection prevention

Prerequisites:
    - pip install guardrails
    - Set CX_TOKEN and CX_ENDPOINT for Coralogix (optional)

Usage:
    python basic_example.py
"""

import asyncio
from cx_guardrails import (
    Guardrails,
    GuardrailsTriggered,
    PII,
    PIICategory,
    PromptInjection,
    PIICategory,
    GuardrailsTriggered,
    setup_export_to_coralogix,
)

setup_export_to_coralogix(service_name="guardrails-basic-example")
guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)


async def main():
    user_input = "What is the capital of France?"

    async with guardrails.guarded_session():
        # Guard the user prompt
        try:
            await guardrails.guard_prompt(config, user_input)
        except GuardrailsTriggered as e:
            print(f"Prompt blocked: {e}")
            return

        # Your LLM call goes here
        llm_response = "The capital of France is Paris."

        # Guard the LLM response
        try:
            await guardrails.guard_response(RESPONSE_GUARDRAILS, llm_response, user_input)
            print(f"Response: {llm_response}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_pii_blocked():
    guardrails = Guardrails()
    user_input = "What is the capital of France?"

    async with guardrails.guarded_session():
        # Guard the user prompt
        try:
            await guardrails.guard_prompt(user_input, PROMPT_GUARDRAILS)
        except GuardrailsTriggered as e:
            print(f"Prompt blocked: {e}")
            return

        # Simulated LLM response with PII leaking
        llm_response = "The capital of France is Paris." + TEST_PII

        # Guard the LLM response - should detect PII
        try:
            await guardrails.guard_response(RESPONSE_GUARDRAILS, llm_response, user_input)
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
