"""
LiteLLM - Guardrails Example
============================

Shows how to use Coralogix Guardrails with LiteLLM's unified API.

Features:
    - LiteLLM acompletion with guardrails
    - PII detection
    - Prompt injection prevention
    - OpenTelemetry tracing to Coralogix

Prerequisites:
    - pip install litellm guardrails llm-tracekit-litellm
    - Set OPENAI_API_KEY (or other provider keys)
    - Set CX_TOKEN and CX_ENDPOINT for Coralogix tracing (optional)

Usage:
    python litellm_example.py
"""

import asyncio
import litellm
from cx_guardrails import (
    Guardrails,
    GuardrailsTarget,
    GuardrailsTriggered,
    PII,
    PIICategory,
    PromptInjection,
)
from llm_tracekit.litellm import LiteLLMInstrumentor, setup_export_to_coralogix

setup_export_to_coralogix(service_name="guardrails-litellm-example")
LiteLLMInstrumentor().instrument()

TEST_PII = "your email is example@example.com"

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
            await guardrails.guard(
                [PromptInjection()], messages, GuardrailsTarget.PROMPT
            )
        except GuardrailsTriggered as e:
            print(f"Prompt blocked: {e}")
            return

        # Call LiteLLM
        response = await litellm.acompletion(model=MODEL, messages=messages)
        response_content = response.choices[0].message.content

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": response_content})
        try:
            await guardrails.guard(config, messages, GuardrailsTarget.RESPONSE)
            print(f"Assistant: {response_content}")
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

        # Call LiteLLM
        response = await litellm.acompletion(model=MODEL, messages=messages)
        response_content = response.choices[0].message.content

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
    setup_export_to_coralogix(service_name="litellm-example")
    LiteLLMInstrumentor().instrument()
    asyncio.run(main())
