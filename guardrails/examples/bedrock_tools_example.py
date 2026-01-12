"""Using Guardrails with AWS Bedrock Converse API and Tool Calls."""

import asyncio
import boto3
from cx_guardrails import (
    Guardrails,
    PII,
    PromptInjection,
    PIICategory,
    GuardrailsTriggered,
    GuardrailsTarget,
)
from llm_tracekit.bedrock import BedrockInstrumentor, setup_export_to_coralogix

setup_export_to_coralogix(
    service_name="guardrails-bedrock-tools-example",
    application_name="my_application",
    subsystem_name="my_subsystem",
    capture_content=True,
)
BedrockInstrumentor().instrument()

TEST_PII = "your email is example@example.com"

guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)
bedrock = boto3.client("bedrock-runtime")


async def main():
    system = [{"text": "You are a helpful assistant."}]
    user_content = "What's the weather in Paris?"
    bedrock_messages = [{"role": "user", "content": [{"text": user_content}]}]
    # Guardrails format
    messages = [
        {"role": "system", "content": system[0]["text"]},
        {"role": "user", "content": user_content},
    ]
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

        response = bedrock.converse(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            messages=bedrock_messages,
            system=system,
            toolConfig={"tools": _get_tools()},
        )

        # Handle tool use
        while response["stopReason"] == "tool_use":
            assistant_message = response["output"]["message"]
            bedrock_messages.append(assistant_message)
            tool_results = []
            for block in assistant_message["content"]:
                if "toolUse" in block:
                    tool = block["toolUse"]
                    args = tool["input"]
                    result = _execute_tool(tool["name"], args)
                    messages.append({
                        "role": "assistant",
                        "content": f"[tool_call: {tool['name']}({args})]",
                    })
                    messages.append({"role": "tool", "content": result})
                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool["toolUseId"],
                            "content": [{"text": result}],
                        }
                    })
            bedrock_messages.append({"role": "user", "content": tool_results})
            response = bedrock.converse(
                modelId="anthropic.claude-3-sonnet-20240229-v1:0",
                messages=bedrock_messages,
                system=system,
                toolConfig={"tools": _get_tools()},
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
            print(f"Assistant: {response['output']['message']['content'][0]['text']}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


def _get_tools():
    return [
        {
            "toolSpec": {
                "name": "get_weather",
                "description": "Get the current weather for a city",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "City name"},
                        },
                        "required": ["city"],
                    },
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
