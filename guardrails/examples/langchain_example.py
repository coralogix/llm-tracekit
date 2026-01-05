"""Using Guardrails with LangChain."""

import asyncio
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
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
    llm = ChatOpenAI(model="gpt-4o-mini")
    user_content = "What is the capital of France?"
    history = [HumanMessage(content=user_content)]
    config = [PII(categories=[PIICategory.EMAIL_ADDRESS]), PromptInjection()]

    async with guardrails.guarded_session():
        # Guard prompt
        messages = [{"role": "user", "content": user_content}]
        try:
            await guardrails.guard(
                messages, [PromptInjection()], GuardrailsTarget.PROMPT
            )
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        response = await llm.ainvoke(history)
        response_content = response.content + TEST_PII
        messages.append({"role": "assistant", "content": response_content})

        try:
            await guardrails.guard(messages, config, GuardrailsTarget.RESPONSE)
            print(f"Assistant: {response.content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
