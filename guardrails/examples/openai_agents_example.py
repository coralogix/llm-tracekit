"""Using Guardrails with OpenAI Agents SDK."""

import asyncio
from agents import Agent, Runner
from guardrails import Guardrails, PII, PromptInjection, PIICategorie, GuardrailsTriggered, convert_openai_agents
from guardrails.models.enums import GuardrailsTarget


async def main():
    guardrails = Guardrails()
    agent = Agent(name="Assistant", instructions="Be helpful")
    user_input = "What is the capital of France?"
    config = [PII(categories=[PIICategorie.email_address]), PromptInjection()]

    async with guardrails.guarded_session():
        try:
            await guardrails.guard([{"role": "user", "content": user_input}], [PromptInjection()], GuardrailsTarget.prompt)
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        result = await Runner.run(agent, input=user_input)
        messages = convert_openai_agents(result.final_output, result.to_input_list())

        try:
            await guardrails.guard(messages, config, GuardrailsTarget.response)
            print(f"Assistant: {result.final_output}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
