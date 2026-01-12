"""Using Guardrails with LiteLLM and Tool Calls."""

import asyncio
import json
import litellm
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
    service_name="guardrails-litellm-tools-example",
    application_name="my_application",
    subsystem_name="my_subsystem",
    capture_content=True,
)

TEST_PII = "your email is example@example.com"

guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)


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

        response = await litellm.acompletion(
            model="gpt-4o-mini",
            messages=messages,
            tools=_get_tools(),
            tool_choice="auto",
        )
        assistant_message = response.choices[0].message

        if assistant_message.tool_calls:
            messages.append(assistant_message.model_dump())
            for tc in assistant_message.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)
                result = _execute_tool(name, args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )
            response = await litellm.acompletion(model="gpt-4o-mini", messages=messages)
            assistant_message = response.choices[0].message

        response_content = assistant_message.content + TEST_PII
        messages.append({"role": "assistant", "content": response_content})

        try:
            await guardrails.guard(
                guardrails=config,
                messages=messages,
                target=GuardrailsTarget.RESPONSE,
            )
            print(f"Assistant: {assistant_message.content}")
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
