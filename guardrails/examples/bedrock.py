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
import boto3
from cx_guardrails import (
    Guardrails,
    GuardrailsTarget,
    GuardrailsTriggered,
    PII,
    PIICategory,
    PromptInjection,
)
from llm_tracekit.bedrock import BedrockInstrumentor, setup_export_to_coralogix

setup_export_to_coralogix(service_name="guardrails-bedrock-example")
BedrockInstrumentor().instrument()

TEST_PII = "your email is example@example.com"

guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)
bedrock = boto3.client("bedrock-runtime")


async def main():
    system = [{"text": "You are a helpful assistant."}]
    user_content = "What is the capital of France?"
    bedrock_messages = [{"role": "user", "content": [{"text": user_content}]}]
    config = [PII(categories=[PIICategory.EMAIL_ADDRESS]), PromptInjection()]

    # Build messages incrementally
    messages = []

    async with guardrails.guarded_session():
        messages = [
            {"role": "system", "content": system[0]["text"]},
            {"role": "user", "content": user_content},
        ]
        try:
            await guardrails.guard(
                [PromptInjection()], messages, GuardrailsTarget.PROMPT
            )
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
            await guardrails.guard(config, messages, GuardrailsTarget.RESPONSE)
            print(f"Assistant: {response_content}")
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
