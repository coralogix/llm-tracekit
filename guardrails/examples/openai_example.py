"""
OpenAI SDK - Guardrails Example
===============================

Shows how to use Coralogix Guardrails with the OpenAI Python SDK.

Features:
    - OpenAI chat completions with guardrails
    - PII detection
    - Prompt injection prevention
    - OpenTelemetry tracing to Coralogix

Prerequisites:
    - pip install openai guardrails llm-tracekit-openai
    - Set OPENAI_API_KEY environment variable
    - Set CX_TOKEN and CX_ENDPOINT for Coralogix tracing (optional)

Usage:
    python openai_example.py
"""

import asyncio
import os

# Guardrails
from guardrails import (
    Guardrails,
    GuardrailsTarget,
    GuardrailsTriggered,
    PII,
    PIICategory,
    PromptInjection,
)

# OpenAI SDK
from openai import AsyncOpenAI
from llm_tracekit_openai import OpenAIInstrumentor, setup_export_to_coralogix

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

MODEL = os.getenv("MODEL", "gpt-4o-mini")

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
    client = AsyncOpenAI()
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

        # Call OpenAI
        response = await client.chat.completions.create(model=MODEL, messages=messages)

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": response.choices[0].message.content})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {response.choices[0].message.content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_pii_blocked():
    guardrails = Guardrails()
    client = AsyncOpenAI()
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

        # Call OpenAI
        response = await client.chat.completions.create(model=MODEL, messages=messages)

        # Simulate PII leaking (e.g., from a database/tool)
        response_with_pii = response.choices[0].message.content + TEST_PII

        # Append assistant response (with PII) and guard it
        messages.append({"role": "assistant", "content": response_with_pii})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {response_with_pii}")
        except GuardrailsTriggered as e:
            print(f"Response blocked (PII detected): {e}")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


async def main():
    await example_basic()
    await example_pii_blocked()


if __name__ == "__main__":
    setup_export_to_coralogix(service_name="openai-example")
    OpenAIInstrumentor().instrument()
    asyncio.run(main())
