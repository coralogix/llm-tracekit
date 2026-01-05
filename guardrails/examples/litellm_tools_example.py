"""
LiteLLM with Tool Calls - Guardrails Example
=============================================

Demonstrates how to use Coralogix Guardrails with LiteLLM's
unified API for multiple LLM providers.

Features:
    - OpenAI-compatible tool definitions
    - Multi-turn tool call conversations
    - Full conversation history scanning (prompts, tool calls, responses)
    - PII detection and prompt injection prevention

Prerequisites:
    - pip install litellm guardrails llm-tracekit-litellm
    - Set OPENAI_API_KEY (or other provider keys)
    - Set CX_TOKEN and CX_ENDPOINT for Coralogix tracing (optional)

Usage:
    python litellm_tools_example.py
"""

import asyncio
import json
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

# LiteLLM
import litellm
from llm_tracekit_litellm import LiteLLMInstrumentor, setup_export_to_coralogix

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

        # Process tool calls with LiteLLM (also updates messages with tool calls)
        litellm_messages = [{"role": "user", "content": user_input}]
        response_content = await process_tool_calls(litellm_messages, [TOOLS[0]], messages)

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": response_content})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {response_content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_multiple_tools():
    guardrails = Guardrails()
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

        # Process tool calls with LiteLLM (also updates messages with tool calls)
        litellm_messages = [{"role": "user", "content": user_input}]
        response_content = await process_tool_calls(litellm_messages, TOOLS, messages)

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": response_content})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {response_content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_pii_blocked():
    guardrails = Guardrails()
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

        # Process tool calls with LiteLLM (also updates messages with tool calls)
        litellm_messages = [{"role": "user", "content": user_input}]
        response_content = await process_tool_calls(litellm_messages, [TOOLS[0]], messages)

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

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name (e.g., Tokyo)"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current local time for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name (e.g., Tokyo)"},
                },
                "required": ["city"],
            },
        },
    },
]

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


def execute_tool(name: str, args: dict) -> str:
    """Execute a tool and return the result."""
    if name == "get_weather":
        city = args.get("city", "Unknown")
        return SIMULATED_WEATHER_DATA.get(city, f"No weather data for {city}")
    elif name == "get_time":
        city = args.get("city", "Unknown")
        return SIMULATED_TIME_DATA.get(city, f"No time data for {city}")
    return f"Unknown tool: {name}"


# -----------------------------------------------------------------------------
# Helper Functions (supporting code)
# -----------------------------------------------------------------------------


async def process_tool_calls(litellm_messages: list, tools: list, messages: list) -> str:
    """Process tool calls in a loop until the model stops using tools.
    
    Updates both `litellm_messages` (LiteLLM format) and `messages` (guardrails format).
    """
    response = await litellm.acompletion(
        model=MODEL,
        messages=litellm_messages,
        tools=tools,
        tool_choice="auto",
    )
    assistant_message = response.choices[0].message

    while assistant_message.tool_calls:
        litellm_messages.append(assistant_message.model_dump())

        # Execute each tool
        for tc in assistant_message.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            result = execute_tool(name, args)

            # Update messages for guardrails (tool call and result)
            messages.append({"role": "assistant", "content": f'[tool_call: {name}({args})]'})
            messages.append({"role": "tool", "content": result})

            litellm_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

        response = await litellm.acompletion(model=MODEL, messages=litellm_messages)
        assistant_message = response.choices[0].message

    return assistant_message.content


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


async def main():
    await example_simple_tool_call()
    await example_multiple_tools()
    await example_pii_blocked()


if __name__ == "__main__":
    setup_export_to_coralogix(service_name="litellm-tools-example")
    LiteLLMInstrumentor().instrument()
    asyncio.run(main())
