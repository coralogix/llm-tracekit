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
from agents import Agent, Runner
from cx_guardrails import (
    Guardrails,
    GuardrailsTarget,
    GuardrailsTriggered,
    PII,
    PIICategory,
    PromptInjection,
)
from llm_tracekit.openai_agents import (
    OpenAIAgentsInstrumentor,
    setup_export_to_coralogix,
)

setup_export_to_coralogix(service_name="guardrails-openai-agents-example")
OpenAIAgentsInstrumentor().instrument()

TEST_PII = "your email is example@example.com"

guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)
agent = Agent(name="Assistant", instructions="You are a helpfull assistant")


async def main():
    user_input = "What is the capital of France?"

    # Build messages incrementally
    messages = []

    async with guardrails.guarded_session():
        # Append user input and guard the prompt
        messages.append({"role": "user", "content": user_input})
        try:
            await guardrails.guard(
                [PromptInjection()],
                [{"role": "user", "content": user_input}],
                GuardrailsTarget.PROMPT,
            )
        except GuardrailsTriggered as e:
            print(f"Prompt blocked: {e}")
            return

        # Run agent
        result = await Runner.run(agent, user_input)

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": result.final_output})
        try:
            await guardrails.guard(config, messages, GuardrailsTarget.RESPONSE)
            print(f"Assistant: {result.final_output}")
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
