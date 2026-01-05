"""
LangChain - Guardrails Example
==============================

Shows how to use Coralogix Guardrails with LangChain.

Features:
    - LangChain ChatOpenAI with guardrails
    - PII detection
    - Prompt injection prevention
    - OpenTelemetry tracing to Coralogix

Prerequisites:
    - pip install langchain-openai guardrails llm-tracekit-langchain
    - Set OPENAI_API_KEY environment variable
    - Set CX_TOKEN and CX_ENDPOINT for Coralogix tracing (optional)

Usage:
    python langchain_example.py
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

# LangChain
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from llm_tracekit_langchain import LangChainInstrumentor, setup_export_to_coralogix

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
    llm = ChatOpenAI(model=MODEL)
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

        # Call LangChain (note: LangChain uses its own message format)
        langchain_messages = [HumanMessage(content=user_input)]
        response = await llm.ainvoke(langchain_messages)
        response_content = response.content

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": response_content})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {response_content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_pii_blocked():
    guardrails = Guardrails()
    llm = ChatOpenAI(model=MODEL)
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

        # Call LangChain (note: LangChain uses its own message format)
        langchain_messages = [HumanMessage(content=user_input)]
        response = await llm.ainvoke(langchain_messages)
        response_content = response.content

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
    setup_export_to_coralogix(service_name="langchain-example")
    LangChainInstrumentor().instrument()
    asyncio.run(main())
