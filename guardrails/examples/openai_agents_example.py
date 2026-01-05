"""
OpenAI Agents SDK - Guardrails Example
======================================

Shows how to use Coralogix Guardrails with the OpenAI Agents SDK.

Features:
    - OpenAI Agents with guardrails
    - PII detection
    - Prompt injection prevention
    - OpenTelemetry tracing to Coralogix

Prerequisites:
    - pip install openai-agents guardrails llm-tracekit-openai-agents
    - Set OPENAI_API_KEY environment variable
    - Set CX_TOKEN and CX_ENDPOINT for Coralogix tracing (optional)

Usage:
    python openai_agents_example.py
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

# OpenAI Agents SDK
from agents import Agent, Runner
from llm_tracekit_openai_agents import OpenAIAgentsInstrumentor, setup_export_to_coralogix

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
    agent = make_agent()
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

        # Run agent
        result = await Runner.run(agent, user_input)

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": result.final_output})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {result.final_output}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_pii_blocked():
    guardrails = Guardrails()
    agent = make_agent()
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

        # Run agent
        result = await Runner.run(agent, user_input)

        # Simulate PII leaking (e.g., from a database/tool)
        response_with_pii = result.final_output + TEST_PII

        # Append assistant response (with PII) and guard it
        messages.append({"role": "assistant", "content": response_with_pii})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {response_with_pii}")
        except GuardrailsTriggered as e:
            print(f"Response blocked (PII detected): {e}")


# -----------------------------------------------------------------------------
# Agent Factory (supporting code)
# -----------------------------------------------------------------------------


def make_agent() -> Agent:
    return Agent(
        name="Assistant",
        model=MODEL,
        instructions="You are a helpful assistant.",
    )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


async def main():
    await example_basic()
    await example_pii_blocked()


if __name__ == "__main__":
    setup_export_to_coralogix(service_name="openai-agents-example")
    OpenAIAgentsInstrumentor().instrument()
    asyncio.run(main())
