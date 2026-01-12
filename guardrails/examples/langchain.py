"""Using Guardrails with LangChain."""

import asyncio
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
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
    service_name="guardrails-langchain-example",
    application_name="my_application",
    subsystem_name="my_subsystem",
    capture_content=True,
)

TEST_PII = "your email is example@example.com"

guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)
llm = ChatOpenAI(model="gpt-4o-mini")


async def main():
    user_content = "What is the capital of France?"
    history = [HumanMessage(content=user_content)]
    config = [PII(categories=[PIICategory.EMAIL_ADDRESS]), PromptInjection()]

    async with guardrails.guarded_session():
        messages = [{"role": "user", "content": user_content}]
        try:
            await guardrails.guard(
                guardrails=[PromptInjection()],
                messages=messages,
                target=GuardrailsTarget.PROMPT,
            )
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        response = await llm.ainvoke(history)
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


if __name__ == "__main__":
    asyncio.run(main())
