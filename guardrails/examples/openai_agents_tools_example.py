"""Using Guardrails with OpenAI Agents SDK and Tool Calls."""

import asyncio
from agents import Agent, Runner, function_tool
from cx_guardrails import (
    Guardrails,
    PII,
    PromptInjection,
    PIICategory,
    GuardrailsTriggered,
    GuardrailsTarget,
)
from llm_tracekit.openai_agents import OpenAIAgentsInstrumentor, setup_export_to_coralogix

setup_export_to_coralogix(
    service_name="guardrails-openai-agents-tools-example",
    application_name="my_application",
    subsystem_name="my_subsystem",
    capture_content=True,
)
OpenAIAgentsInstrumentor().instrument()

TEST_PII = "your email is example@example.com"

guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)


async def main():
    user_content = "What's the weather in Paris?"
    messages = [{"role": "user", "content": user_content}]
    config = [PII(categories=[PIICategory.EMAIL_ADDRESS]), PromptInjection()]

    async with guardrails.guarded_session():
        try:
            await guardrails.guard(
                guardrails=[PromptInjection()],
                messages=messages,
                target=GuardrailsTarget.PROMPT,
            )
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        result = await Runner.run(_get_agent(), user_content)
        response_content = result.final_output + TEST_PII
        messages.append({"role": "assistant", "content": response_content})

        try:
            await guardrails.guard(
                guardrails=config,
                messages=messages,
                target=GuardrailsTarget.RESPONSE,
            )
            print(f"Assistant: {result.final_output}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


def _get_weather_data():
    return {
        "Paris": "18°C and partly cloudy",
        "London": "12°C and rainy",
    }


@function_tool
async def _get_weather(city: str) -> str:
    """Get current weather for a city."""
    return _get_weather_data().get(city, f"Weather data not available for {city}")


def _get_agent():
    return Agent(
        name="WeatherAssistant",
        model="gpt-4o-mini",
        instructions="You are a weather assistant. Provide weather information when asked.",
        tools=[_get_weather],
    )


if __name__ == "__main__":
    asyncio.run(main())
