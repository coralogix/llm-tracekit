"""
Google Gemini - Guardrails Example
==================================

Shows how to use Coralogix Guardrails with Google's Gemini API.

Features:
    - Gemini generate_content with guardrails
    - PII detection
    - Prompt injection prevention
    - OpenTelemetry tracing to Coralogix

Prerequisites:
    - pip install google-genai guardrails llm-tracekit-gemini
    - Set GOOGLE_API_KEY environment variable
    - Set CX_TOKEN and CX_ENDPOINT for Coralogix tracing (optional)

Usage:
    python gemini_example.py
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

# Google Gemini
from google import genai
from llm_tracekit_gemini import GeminiInstrumentor, setup_export_to_coralogix

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

MODEL = os.getenv("MODEL", "gemini-2.0-flash")

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
    client = genai.Client()
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

        contents = [{"role": "user", "parts": [{"text": user_input}]}]
        response = await client.aio.models.generate_content(model=MODEL, contents=contents)
        response_content = str(response.text)

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": response_content})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {response_content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_pii_blocked():
    guardrails = Guardrails()
    client = genai.Client()
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

        contents = [{"role": "user", "parts": [{"text": user_input}]}]
        response = await client.aio.models.generate_content(model=MODEL, contents=contents)
        response_content = str(response.text)

        # Simulate PII leaking (e.g., from a database/tool)
        response_with_pii = response_content + TEST_PII

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
    setup_export_to_coralogix(service_name="gemini-example")
    GeminiInstrumentor().instrument()
    asyncio.run(main())
