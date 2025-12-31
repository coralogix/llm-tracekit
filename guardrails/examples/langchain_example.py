"""Using Guardrails with LangChain."""

import asyncio
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from guardrails import Guardrails, PII, PromptInjection, PIICategorie, GuardrailsTriggered, convert_langchain
from guardrails.models.enums import GuardrailsTarget


async def main():
    guardrails = Guardrails()
    llm = ChatOpenAI(model="gpt-4o-mini")
    history = [HumanMessage(content="What is the capital of France?")]
    config = [PII(categories=[PIICategorie.email_address]), PromptInjection()]

    async with guardrails.guarded_session():
        try:
            await guardrails.guard([{"role": "user", "content": history[0].content}], [PromptInjection()], GuardrailsTarget.prompt)
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        response = await llm.ainvoke(history)
        messages = convert_langchain(response, history)

        try:
            await guardrails.guard(messages, config, GuardrailsTarget.response)
            print(f"Assistant: {response.content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
