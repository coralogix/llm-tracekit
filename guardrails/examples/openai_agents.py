"""Using Guardrails with OpenAI Agents SDK."""

import asyncio
from agents import Agent, Runner
from cx_guardrails import (
    Guardrails,
    PII,
    PromptInjection,
    PIICategory,
    GuardrailsTriggered,
    GuardrailsTarget,
)
from llm_tracekit.openai_agents import OpenAIAgentsInstrumentor, setup_export_to_coralogix

setup_export_to_coralogix(service_name="guardrails-openai-agents-example")
OpenAIAgentsInstrumentor().instrument()

TEST_PII = "your email is example@example.com"

guardrails = Guardrails()
agent = Agent(name="Assistant", instructions="You are a helpfull assistant")


async def main():
    user_input = "What is the capital of France?"
    config = [PII(categories=[PIICategory.EMAIL_ADDRESS]), PromptInjection()]

    async with guardrails.guarded_session():
        try:
            await guardrails.guard(
                [PromptInjection()],
                [{"role": "user", "content": user_input}],
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
            await guardrails.guard(config, messages, GuardrailsTarget.RESPONSE)
            print(f"Assistant: {result.final_output}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
