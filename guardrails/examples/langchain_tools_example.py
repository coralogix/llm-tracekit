"""Using Guardrails with LangChain and Tool Calls."""

import asyncio
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from cx_guardrails import (
    Guardrails,
    PII,
    PromptInjection,
    PIICategory,
    GuardrailsTriggered,
    GuardrailsTarget,
)
from llm_tracekit.langchain import LangChainInstrumentor, setup_export_to_coralogix

setup_export_to_coralogix(
    service_name="guardrails-langchain-tools-example",
    application_name="my_application",
    subsystem_name="my_subsystem",
    capture_content=True,
)
LangChainInstrumentor().instrument()

TEST_PII = "your email is example@example.com"

guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)
llm = ChatOpenAI(model="gpt-4o-mini")


async def main():
    user_content = "What's the weather in Paris?"
    # LangChain format for API
    history = [HumanMessage(content=user_content)]
    # Guardrails format
    messages = [{"role": "user", "content": user_content}]
    config = [PII(categories=[PIICategory.EMAIL_ADDRESS]), PromptInjection()]

    llm_with_tools = llm.bind_tools([_get_weather])

    async with guardrails.guarded_session():
        try:
            await guardrails.guard(
                guardrails=[PromptInjection()],
                messages=messages,
                target=GuardrailsTarget.PROMPT,
            )
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        response = await llm_with_tools.ainvoke(history)

        # Handle tool calls
        while response.tool_calls:
            history.append(response)
            for tc in response.tool_calls:
                tool_func = _get_tool_map().get(tc["name"])
                args = tc.get("args", {})
                result = tool_func.invoke(args) if tool_func else "Unknown"
                messages.append({
                    "role": "assistant",
                    "content": f"[tool_call: {tc['name']}({args})]",
                })
                messages.append({"role": "tool", "content": result})
                history.append(ToolMessage(content=result, tool_call_id=tc.get("id")))
            response = await llm_with_tools.ainvoke(history)

        response_content = response.content + TEST_PII
        messages.append({"role": "assistant", "content": response_content})

        try:
            await guardrails.guard(
                guardrails=config,
                messages=messages,
                target=GuardrailsTarget.RESPONSE,
            )
            print(f"Assistant: {response.content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


def _get_weather_data():
    return {
        "Paris": "18°C and partly cloudy",
        "London": "12°C and rainy",
    }


@tool
def _get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return _get_weather_data().get(city, f"No weather data for {city}")


def _get_tool_map():
    return {"_get_weather": _get_weather}


if __name__ == "__main__":
    asyncio.run(main())
