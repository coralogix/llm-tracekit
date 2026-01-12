"""Using Guardrails with OpenAI SDK and Tool Calls."""

import asyncio
import json
from openai import AsyncOpenAI
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
    service_name="guardrails-openai-tools-example",
    application_name="my_application",
    subsystem_name="my_subsystem",
    capture_content=True,
)

TEST_PII = "your email is example@example.com"

guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)
client = AsyncOpenAI()


async def main():
    messages = [{"role": "user", "content": "What's the weather in Paris?"}]
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

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=_get_tools(),
            tool_choice="auto",
        )

        assistant_message = response.choices[0].message
        if assistant_message.tool_calls:
            messages.append(assistant_message.model_dump())
            for tool_call in assistant_message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                result = _execute_tool(name, args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )
            response = await client.chat.completions.create(
                model="gpt-4o-mini", messages=messages
            )

        response_content = response.choices[0].message.content + TEST_PII
        messages.append({"role": "assistant", "content": response_content})

        try:
            await guardrails.guard(
                guardrails=config,
                messages=messages,
                target=GuardrailsTarget.RESPONSE,
            )
            print(f"Assistant: {response.choices[0].message.content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


def _get_tools():
    return [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a city",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name"},
                    },
                    "required": ["city"],
                },
            },
        },
    ]


def _get_weather_data():
    return {
        "Paris": "18°C and partly cloudy",
        "London": "12°C and rainy",
    }


def _execute_tool(name: str, args: dict) -> str:
    if name == "get_weather":
        city = args.get("city", "Unknown")
        return _get_weather_data().get(city, f"No weather data for {city}")
    return f"Unknown tool: {name}"


if __name__ == "__main__":
    asyncio.run(main())
