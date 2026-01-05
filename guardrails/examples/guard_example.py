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

# Guardrails
from guardrails import (
    Guardrails,
    GuardrailsTarget,
    GuardrailsTriggered,
    PII,
    PIICategory,
    PromptInjection,
)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# Test PII data to simulate leakage (note: leading space is intentional for concatenation)
TEST_PII = " Contact: john.smith@company.com, +1-555-123-4567"

# Guardrail configurations
PROMPT_GUARDRAILS = [PromptInjection()]
RESPONSE_GUARDRAILS = [PII(categories=[PIICategory.EMAIL_ADDRESS, PIICategory.PHONE_NUMBER])]


# -----------------------------------------------------------------------------
# Examples
# -----------------------------------------------------------------------------


async def example_basic():
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

        # Your LLM call goes here
        llm_response = "The capital of France is Paris."

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": llm_response})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {llm_response}")
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
