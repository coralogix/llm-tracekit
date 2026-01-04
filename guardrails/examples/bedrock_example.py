"""Using Guardrails with AWS Bedrock Converse API."""

import asyncio
import boto3
from guardrails import Guardrails, PII, PromptInjection, PIICategorie, GuardrailsTriggered
from guardrails.models.enums import GuardrailsTarget

TEST_PII = "your email is example@example.com"


async def main():
    guardrails = Guardrails()
    bedrock = boto3.client("bedrock-runtime")
    system = [{"text": "You are a helpful assistant."}]
    user_content = "What is the capital of France?"
    bedrock_messages = [{"role": "user", "content": [{"text": user_content}]}]
    config = [PII(categories=[PIICategorie.email_address]), PromptInjection()]

    async with guardrails.guarded_session():
        # Guard prompt
        messages = [
            {"role": "system", "content": system[0]["text"]},
            {"role": "user", "content": user_content},
        ]
        try:
            await guardrails.guard(messages, [PromptInjection()], GuardrailsTarget.prompt)
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        response = bedrock.converse(modelId="anthropic.claude-3-sonnet-20240229-v1:0", messages=bedrock_messages, system=system)
        response_content = response["output"]["message"]["content"][0]["text"] + TEST_PII
        messages.append({"role": "assistant", "content": response_content})

        try:
            await guardrails.guard(messages, config, GuardrailsTarget.response)
            print(f"Assistant: {response_content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
