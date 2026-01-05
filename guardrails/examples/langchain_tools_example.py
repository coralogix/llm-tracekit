"""
LangChain with Tool Calls - Guardrails Example
===============================================

Demonstrates how to use Coralogix Guardrails with LangChain's
tool binding and the @tool decorator.

Features:
    - LangChain @tool decorator for function definitions
    - Tool binding with ChatOpenAI
    - Full conversation history scanning (prompts, tool calls, responses)
    - PII detection and prompt injection prevention

Prerequisites:
    - pip install langchain-openai guardrails llm-tracekit-langchain
    - Set OPENAI_API_KEY environment variable
    - Set CX_TOKEN and CX_ENDPOINT for Coralogix tracing (optional)

Usage:
    python langchain_tools_example.py
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
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from llm_tracekit_langchain import LangChainInstrumentor, setup_export_to_coralogix

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

MODEL = os.getenv("MODEL", "gpt-4o-mini")
SYSTEM_PROMPT = "You are a helpful assistant."

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
    llm = ChatOpenAI(model=MODEL, temperature=0)
    llm_with_tools = llm.bind_tools([get_weather])
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

        # Process tool calls with LangChain (also updates messages with tool calls)
        langchain_history = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_input)]
        response_content = await process_tool_calls(llm_with_tools, langchain_history, messages)

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": response_content})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {response_content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_multiple_tools():
    guardrails = Guardrails()
    llm = ChatOpenAI(model=MODEL, temperature=0)
    llm_with_tools = llm.bind_tools([get_weather, get_time])
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

        # Process tool calls with LangChain (also updates messages with tool calls)
        langchain_history = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_input)]
        response_content = await process_tool_calls(llm_with_tools, langchain_history, messages)

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": response_content})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {response_content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_pii_blocked():
    guardrails = Guardrails()
    llm = ChatOpenAI(model=MODEL, temperature=0)
    llm_with_tools = llm.bind_tools([get_weather])
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

        # Process tool calls with LangChain (also updates messages with tool calls)
        langchain_history = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_input)]
        response_content = await process_tool_calls(llm_with_tools, langchain_history, messages)

        # Simulate PII leaking (e.g., from a database lookup)
        response_with_pii = response_content + TEST_PII

        # Append assistant response (with PII) and guard it
        messages.append({"role": "assistant", "content": response_with_pii})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {response_with_pii}")
        except GuardrailsTriggered as e:
            print(f"Response blocked (PII detected): {e}")


# -----------------------------------------------------------------------------
# Tool Definitions (supporting code)
# -----------------------------------------------------------------------------

SIMULATED_WEATHER_DATA = {
    "Tel Aviv": "28°C and sunny",
    "New York": "15°C and cloudy",
    "London": "12°C and rainy",
    "Tokyo": "22°C and clear",
    "Paris": "18°C and partly cloudy",
}

SIMULATED_TIME_DATA = {
    "Tel Aviv": "14:30 (simulated)",
    "New York": "07:30 (simulated)",
    "London": "12:30 (simulated)",
    "Tokyo": "21:30 (simulated)",
    "Paris": "13:30 (simulated)",
}


@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return SIMULATED_WEATHER_DATA.get(city, f"No weather data for {city}")


@tool
def get_time(city: str) -> str:
    """Get the current local time for a city."""
    return SIMULATED_TIME_DATA.get(city, f"No time data for {city}")


TOOL_MAP = {
    "get_weather": get_weather,
    "get_time": get_time,
}


# -----------------------------------------------------------------------------
# Helper Functions (supporting code)
# -----------------------------------------------------------------------------


async def process_tool_calls(llm_with_tools, history: list, messages: list) -> str:
    """Process tool calls in a loop until the model stops using tools.
    
    Updates both `history` (LangChain format) and `messages` (guardrails format).
    """
    response = await llm_with_tools.ainvoke(history)

    while response.tool_calls:
        history.append(response)

        # Execute each tool
        for tc in response.tool_calls:
            name = tc["name"]
            args = tc.get("args", {})
            tool_id = tc.get("id", "tool_call")

            tool_func = TOOL_MAP.get(name)
            result = tool_func.invoke(args) if tool_func else f"Unknown tool: {name}"

            # Update messages for guardrails (tool call and result)
            messages.append({"role": "assistant", "content": f'[tool_call: {name}({args})]'})
            messages.append({"role": "tool", "content": result})

            history.append(ToolMessage(content=result, tool_call_id=tool_id))

        response = await llm_with_tools.ainvoke(history)

    return response.content


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


async def main():
    await example_simple_tool_call()
    await example_multiple_tools()
    await example_pii_blocked()


if __name__ == "__main__":
    setup_export_to_coralogix(service_name="langchain-tools-example")
    LangChainInstrumentor().instrument()
    asyncio.run(main())
