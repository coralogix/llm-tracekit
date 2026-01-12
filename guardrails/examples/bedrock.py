"""Using Guardrails with AWS Bedrock Converse API."""

import asyncio
import boto3
from cx_guardrails import (
    Guardrails,
    PII,
    PromptInjection,
    PIICategory,
    GuardrailsTriggered,
    GuardrailsTarget,
    setup_export_to_coralogix,
)

setup_export_to_coralogix(
    service_name="guardrails-bedrock-example",
    application_name="my_application",
    subsystem_name="my_subsystem",
    capture_content=True,
)

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

    async with guardrails.guarded_session():
        messages = [
            {"role": "system", "content": system[0]["text"]},
            {"role": "user", "content": user_content},
        ]
        try:
            await guardrails.guard(
                guardrails=[PromptInjection()],
                messages=messages,
                target=GuardrailsTarget.PROMPT,
            )
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        response = bedrock.converse(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            messages=bedrock_messages,
            system=system,
        )
        response_content = (
            response["output"]["message"]["content"][0]["text"] + TEST_PII
        )
        messages.append({"role": "assistant", "content": response_content})

        try:
            await guardrails.guard(
                guardrails=config,
                messages=messages,
                target=GuardrailsTarget.RESPONSE,
            )
            print(f"Assistant: {response_content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
