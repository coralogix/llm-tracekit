"""Using Guardrails with AWS Bedrock Converse API."""

import asyncio
import boto3
from guardrails import Guardrails, PII, PromptInjection, PIICategorie, GuardrailsTriggered, convert_bedrock_converse
from guardrails.models.enums import GuardrailsTarget


async def main():
    guardrails = Guardrails()
    bedrock = boto3.client("bedrock-runtime")
    system = [{"text": "You are a helpful assistant."}]
    messages = [{"role": "user", "content": [{"text": "What is the capital of France?"}]}]
    config = [PII(categories=[PIICategorie.email_address]), PromptInjection()]

    async with guardrails.guarded_session():
        try:
            await guardrails.guard(convert_bedrock_converse({}, messages, system), [PromptInjection()], GuardrailsTarget.prompt)
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        response = bedrock.converse(modelId="anthropic.claude-3-sonnet-20240229-v1:0", messages=messages, system=system)
        guard_messages = convert_bedrock_converse(response, messages, system)

        try:
            await guardrails.guard(guard_messages, config, GuardrailsTarget.response)
            print(f"Assistant: {response['output']['message']['content'][0]['text']}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
