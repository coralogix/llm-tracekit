"""
AWS Bedrock Converse API with Tool Calls - Guardrails Example
==============================================================

Demonstrates how to use Coralogix Guardrails with AWS Bedrock's Converse API
and function tools.

Features:
    - Tool definitions in Bedrock's toolSpec format
    - Multi-turn tool call conversations
    - Full conversation history scanning (prompts, tool calls, responses)
    - PII detection and prompt injection prevention

Prerequisites:
    - pip install boto3 guardrails llm-tracekit-bedrock
    - Configure AWS credentials (aws configure or environment variables)
    - Set CX_TOKEN and CX_ENDPOINT for Coralogix tracing (optional)

Usage:
    python bedrock_tools_example.py
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

# AWS Bedrock
import boto3
from llm_tracekit_bedrock import BedrockInstrumentor, setup_export_to_coralogix

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

MODEL_ID = os.getenv("MODEL", "anthropic.claude-3-sonnet-20240229-v1:0")

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
    bedrock = boto3.client("bedrock-runtime")
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

        # Process tool calls with Bedrock (also updates messages with tool calls)
        bedrock_messages = [{"role": "user", "content": [{"text": user_input}]}]
        response_content = process_tool_use(bedrock, bedrock_messages, [TOOLS[0]], messages)

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": response_content})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {response_content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_multiple_tools():
    guardrails = Guardrails()
    bedrock = boto3.client("bedrock-runtime")
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

        # Process tool calls with Bedrock (also updates messages with tool calls)
        bedrock_messages = [{"role": "user", "content": [{"text": user_input}]}]
        response_content = process_tool_use(bedrock, bedrock_messages, TOOLS, messages)

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": response_content})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {response_content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_pii_blocked():
    guardrails = Guardrails()
    bedrock = boto3.client("bedrock-runtime")
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

        # Process tool calls with Bedrock (also updates messages with tool calls)
        bedrock_messages = [{"role": "user", "content": [{"text": user_input}]}]
        response_content = process_tool_use(bedrock, bedrock_messages, [TOOLS[0]], messages)

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
        "toolSpec": {
            "name": "get_weather",
            "description": "Get the current weather for a city",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name (e.g., Tokyo)"},
                    },
                    "required": ["city"],
                },
            },
        },
    },
    {
        "toolSpec": {
            "name": "get_time",
            "description": "Get the current local time for a city",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name (e.g., Tokyo)"},
                    },
                    "required": ["city"],
                },
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


def process_tool_use(bedrock, bedrock_messages: list, tools: list, messages: list) -> str:
    """Process tool use responses in a loop until the model stops using tools.
    
    Updates both `bedrock_messages` (Bedrock format) and `messages` (guardrails format).
    """
    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=bedrock_messages,
        toolConfig={"tools": tools},
    )

    while response["stopReason"] == "tool_use":
        assistant_message = response["output"]["message"]
        bedrock_messages.append(assistant_message)

        # Process all tool calls
        tool_results = []
        for block in assistant_message["content"]:
            if "toolUse" in block:
                tool = block["toolUse"]
                args = tool["input"]
                result = execute_tool(tool["name"], args)

                # Update messages for guardrails (tool call and result)
                messages.append({"role": "assistant", "content": f'[tool_call: {tool["name"]}({args})]'})
                messages.append({"role": "tool", "content": result})

                tool_results.append({
                    "toolResult": {
                        "toolUseId": tool["toolUseId"],
                        "content": [{"text": result}],
                    }
                })

        bedrock_messages.append({"role": "user", "content": tool_results})
        response = bedrock.converse(
            modelId=MODEL_ID,
            messages=bedrock_messages,
            toolConfig={"tools": tools},
        )

    return response["output"]["message"]["content"][0]["text"]


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


async def main():
    await example_simple_tool_call()
    await example_multiple_tools()
    await example_pii_blocked()


if __name__ == "__main__":
    setup_export_to_coralogix(service_name="bedrock-tools-example")
    BedrockInstrumentor().instrument()
    asyncio.run(main())
