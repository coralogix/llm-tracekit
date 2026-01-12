"""Using Guardrails with Google Gemini and Tool Calls."""

import asyncio
from google import genai
from google.genai import types
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
    service_name="guardrails-gemini-tools-example",
    application_name="my_application",
    subsystem_name="my_subsystem",
    capture_content=True,
)

TEST_PII = "your email is example@example.com"

guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)
client = genai.Client()


async def main():
    user_content = "What's the weather in Paris?"
    contents = [{"role": "user", "parts": [{"text": user_content}]}]
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

        tools = types.Tool(function_declarations=_get_function_declarations())
        gen_config = types.GenerateContentConfig(tools=[tools])
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash", contents=contents, config=gen_config
        )
        candidate = response.candidates[0]

        while (
            candidate.content.parts
            and hasattr(candidate.content.parts[0], "function_call")
            and candidate.content.parts[0].function_call is not None
        ):
            func_call = candidate.content.parts[0].function_call
            args = dict(func_call.args)
            result = _execute_tool(func_call.name, args)
            messages.append(
                {
                    "role": "assistant",
                    "content": f"[tool_call: {func_call.name}({args})]",
                }
            )
            messages.append({"role": "tool", "content": result})
            function_response = types.Part.from_function_response(
                name=func_call.name, response={"result": result}
            )
            contents.append(candidate.content)
            contents.append(types.Content(role="user", parts=[function_response]))
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash", contents=contents, config=gen_config
            )
            candidate = response.candidates[0]

        response_content = str(candidate.content.parts[0].text) + TEST_PII
        messages.append({"role": "assistant", "content": response_content})

        try:
            await guardrails.guard(
                guardrails=config,
                messages=messages,
                target=GuardrailsTarget.RESPONSE,
            )
            print(f"Assistant: {candidate.content.parts[0].text}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


def _get_function_declarations():
    return [
        {
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
