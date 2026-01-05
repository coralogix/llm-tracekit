"""
AWS Bedrock Converse API - Guardrails Example
=============================================

Shows how to use Coralogix Guardrails with AWS Bedrock's Converse API.

Features:
    - Bedrock Converse API with guardrails
    - PII detection
    - Prompt injection prevention
    - OpenTelemetry tracing to Coralogix

Prerequisites:
    - pip install boto3 guardrails llm-tracekit-bedrock
    - Configure AWS credentials (aws configure or environment variables)
    - Set CX_TOKEN and CX_ENDPOINT for Coralogix tracing (optional)

Usage:
    python bedrock_example.py
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


async def example_basic():
    guardrails = Guardrails()
    bedrock = boto3.client("bedrock-runtime")
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

        # Call Bedrock (note: Bedrock uses its own message format)
        bedrock_messages = [{"role": "user", "content": [{"text": user_input}]}]
        response = bedrock.converse(modelId=MODEL_ID, messages=bedrock_messages)
        response_content = response["output"]["message"]["content"][0]["text"]

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

        # Call Bedrock (note: Bedrock uses its own message format)
        bedrock_messages = [{"role": "user", "content": [{"text": user_input}]}]
        response = bedrock.converse(modelId=MODEL_ID, messages=bedrock_messages)
        response_content = response["output"]["message"]["content"][0]["text"]

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
    setup_export_to_coralogix(service_name="bedrock-example")
    BedrockInstrumentor().instrument()
    asyncio.run(main())
