"""
Google Gemini with Tool Calls - Guardrails Example
===================================================

Demonstrates how to use Coralogix Guardrails with Google's Gemini API
and function calling.

Features:
    - Function declarations for Gemini tools
    - Multi-turn tool call conversations
    - Full conversation history scanning (prompts, tool calls, responses)
    - PII detection and prompt injection prevention

Prerequisites:
    - pip install google-genai guardrails llm-tracekit-gemini
    - Set GOOGLE_API_KEY environment variable
    - Set CX_TOKEN and CX_ENDPOINT for Coralogix tracing (optional)

Usage:
    python gemini_tools_example.py
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
from google.genai import types
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


async def example_simple_tool_call():
    guardrails = Guardrails()
    client = genai.Client()
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

        # Process function calls with Gemini (also updates messages with tool calls)
        contents = [{"role": "user", "parts": [{"text": user_input}]}]
        tools = types.Tool(function_declarations=[FUNCTION_DECLARATIONS[0]])
        config = types.GenerateContentConfig(tools=[tools])
        response_content = await process_function_calls(client, contents, config, messages)

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": response_content})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {response_content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_multiple_tools():
    guardrails = Guardrails()
    client = genai.Client()
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

        # Process function calls with Gemini (also updates messages with tool calls)
        contents = [{"role": "user", "parts": [{"text": user_input}]}]
        tools = types.Tool(function_declarations=FUNCTION_DECLARATIONS)
        config = types.GenerateContentConfig(tools=[tools])
        response_content = await process_function_calls(client, contents, config, messages)

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

        # Process function calls with Gemini (also updates messages with tool calls)
        contents = [{"role": "user", "parts": [{"text": user_input}]}]
        tools = types.Tool(function_declarations=[FUNCTION_DECLARATIONS[0]])
        config = types.GenerateContentConfig(tools=[tools])
        response_content = await process_function_calls(client, contents, config, messages)

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

FUNCTION_DECLARATIONS = [
    {
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
    {
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


def has_function_call(candidate) -> bool:
    """Check if the response contains a function call."""
    return (
        candidate.content.parts
        and hasattr(candidate.content.parts[0], "function_call")
        and candidate.content.parts[0].function_call is not None
    )


async def process_function_calls(client, contents: list, config, messages: list) -> str:
    """Process function calls in a loop until the model stops calling functions.
    
    Updates both `contents` (Gemini format) and `messages` (guardrails format).
    """
    response = await client.aio.models.generate_content(
        model=MODEL,
        contents=contents,
        config=config,
    )
    candidate = response.candidates[0]

    while has_function_call(candidate):
        func_call = candidate.content.parts[0].function_call
        args = dict(func_call.args)

        # Execute the tool
        result = execute_tool(func_call.name, args)

        # Update messages for guardrails (tool call and result)
        messages.append({"role": "assistant", "content": f'[tool_call: {func_call.name}({args})]'})
        messages.append({"role": "tool", "content": result})

        # Build function response and continue conversation (Gemini format)
        function_response = types.Part.from_function_response(
            name=func_call.name,
            response={"result": result},
        )
        contents.append(candidate.content)
        contents.append(types.Content(role="user", parts=[function_response]))

        response = await client.aio.models.generate_content(
            model=MODEL,
            contents=contents,
            config=config,
        )
        candidate = response.candidates[0]

    return candidate.content.parts[0].text


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


async def main():
    await example_simple_tool_call()
    await example_multiple_tools()
    await example_pii_blocked()


if __name__ == "__main__":
    setup_export_to_coralogix(service_name="gemini-tools-example")
    GeminiInstrumentor().instrument()
    asyncio.run(main())
