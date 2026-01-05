"""Using Guardrails with OpenAI Agents SDK."""

import asyncio
from agents import Agent, Runner
from guardrails import (
    Guardrails,
    PII,
    PromptInjection,
    PIICategory,
    GuardrailsTriggered,
    GuardrailsTarget,
)

TEST_PII = "your email is example@example.com"


async def main():
    guardrails = Guardrails()
    agent = Agent(name="Assistant", instructions="Be helpful")
    user_input = "What is the capital of France?"
    config = [PII(categories=[PIICategory.EMAIL_ADDRESS]), PromptInjection()]

    async with guardrails.guarded_session():
        try:
            await guardrails.guard(
                [{"role": "user", "content": user_input}],
                [PromptInjection()],
                GuardrailsTarget.PROMPT,
            )
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        result = await Runner.run(agent, input=user_input)
        response_content = result.final_output + TEST_PII
        messages = [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": response_content},
        ]

        try:
            await guardrails.guard(messages, config, GuardrailsTarget.RESPONSE)
            print(f"Assistant: {result.final_output}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
