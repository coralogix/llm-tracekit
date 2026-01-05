"""
OpenAI Agents SDK with Tool Calls - Guardrails Example
=======================================================

Demonstrates how to use Coralogix Guardrails with the OpenAI Agents SDK,
including function tools and the orchestrator pattern with nested agents.

Features:
    - Function tools with the @function_tool decorator
    - Orchestrator pattern delegating to specialized agents
    - Guardrails protection for prompts and responses
    - Multi-turn messages handling

Prerequisites:
    - pip install openai-agents guardrails llm-tracekit-openai-agents
    - Set OPENAI_API_KEY environment variable
    - Set CX_TOKEN and CX_ENDPOINT for Coralogix tracing (optional)

Usage:
    python openai_agents_tools_example.py
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
from agents import Agent, Runner, function_tool
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


async def example_simple_tool_call():
    guardrails = Guardrails()
    weather_agent = make_weather_agent()
    user_input = "What's the weather in Tel Aviv?"

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
        result = await Runner.run(weather_agent, user_input)

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": result.final_output})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {result.final_output}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_orchestrator_pattern():
    guardrails = Guardrails()
    orchestrator = make_orchestrator(make_weather_agent(), make_time_agent())
    user_input = "What's the weather in Tokyo and what time is it there?"

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

        # Run orchestrator (delegates to weather + time agents)
        result = await Runner.run(orchestrator, user_input)

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": result.final_output})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {result.final_output}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_pii_blocked():
    guardrails = Guardrails()
    weather_agent = make_weather_agent()
    user_input = "What's the weather in London?"

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
        result = await Runner.run(weather_agent, user_input)

        # Simulate PII leaking (e.g., from a tool/database)
        response_with_pii = result.final_output + TEST_PII

        # Append assistant response (with PII) and guard it
        messages.append({"role": "assistant", "content": response_with_pii})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {response_with_pii}")
        except GuardrailsTriggered as e:
            print(f"Response blocked (PII detected): {e}")


async def example_multi_turn():
    guardrails = Guardrails()
    orchestrator = make_orchestrator(make_weather_agent(), make_time_agent())

    # Build messages incrementally across turns
    messages = []
    prompts = [
        "What's the weather in London?",
        "How about New York?",
        "What time is it in Tokyo?",
    ]

    async with guardrails.guarded_session():
        for user_input in prompts:
            # Append user input and guard the prompt
            messages.append({"role": "user", "content": user_input})
            try:
                await guardrails.guard(messages, PROMPT_GUARDRAILS, GuardrailsTarget.PROMPT)
            except GuardrailsTriggered as e:
                print(f"Prompt blocked: {e}")
                messages.pop()  # Remove the blocked message
                continue

            # Run orchestrator with messages context
            result = await Runner.run(orchestrator, messages)

            # Append assistant response and guard it
            messages.append({"role": "assistant", "content": result.final_output})
            try:
                await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
                print(f"User: {user_input}")
                print(f"Assistant: {result.final_output}")
            except GuardrailsTriggered as e:
                print(f"Response blocked: {e}")
                messages.pop()  # Remove the blocked response


# -----------------------------------------------------------------------------
# Tool Definitions (supporting code)
# -----------------------------------------------------------------------------

SIMULATED_WEATHER_DATA = {
    "Tel Aviv": "28°C and sunny",
    "New York": "15°C and cloudy",
    "London": "12°C and rainy",
    "Tokyo": "22°C and clear",
    "Paris": "18°C and partly cloudy",
    "Berlin": "14°C and windy",
}

SIMULATED_TIME_DATA = {
    "Tel Aviv": "14:30 (simulated)",
    "New York": "07:30 (simulated)",
    "London": "12:30 (simulated)",
    "Tokyo": "21:30 (simulated)",
    "Paris": "13:30 (simulated)",
    "Berlin": "13:30 (simulated)",
}


@function_tool
async def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return SIMULATED_WEATHER_DATA.get(city, f"Weather data not available for {city}")


@function_tool
async def get_time(city: str) -> str:
    """Get current local time for a city."""
    return SIMULATED_TIME_DATA.get(city, f"Time data not available for {city}")


# -----------------------------------------------------------------------------
# Agent Factories (supporting code)
# -----------------------------------------------------------------------------


def make_weather_agent() -> Agent:
    return Agent(
        name="WeatherAssistant",
        model=MODEL,
        instructions="You are a weather assistant. Provide weather information when asked.",
        tools=[get_weather],
    )


def make_time_agent() -> Agent:
    return Agent(
        name="TimeAssistant",
        model=MODEL,
        instructions="You are a time zone assistant. Provide local time for cities when asked.",
        tools=[get_time],
    )


def make_orchestrator(weather_agent: Agent, time_agent: Agent) -> Agent:
    @function_tool
    async def ask_weather(question: str) -> str:
        """Delegate weather-related questions to the weather specialist."""
        result = await Runner.run(weather_agent, question)
        return result.final_output

    @function_tool
    async def ask_time(question: str) -> str:
        """Delegate time-related questions to the time specialist."""
        result = await Runner.run(time_agent, question)
        return result.final_output

    return Agent(
        name="Orchestrator",
        model=MODEL,
        instructions="""You are a helpful orchestrator that delegates tasks to specialists.
Route weather questions to the weather specialist, time questions to the time specialist.""",
        tools=[ask_weather, ask_time],
    )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


async def main():
    await example_simple_tool_call()
    await example_orchestrator_pattern()
    await example_pii_blocked()
    await example_multi_turn()


if __name__ == "__main__":
    setup_export_to_coralogix(service_name="openai-agents-tools-example")
    OpenAIAgentsInstrumentor().instrument()
    asyncio.run(main())
