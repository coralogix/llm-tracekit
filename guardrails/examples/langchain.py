"""
LangChain - Guardrails Example
==============================

Shows how to use Coralogix Guardrails with LangChain.

Features:
    - LangChain ChatOpenAI with guardrails
    - PII detection
    - Prompt injection prevention
    - OpenTelemetry tracing to Coralogix

Prerequisites:
    - pip install langchain-openai guardrails llm-tracekit-langchain
    - Set OPENAI_API_KEY environment variable
    - Set CX_TOKEN and CX_ENDPOINT for Coralogix tracing (optional)

Usage:
    python langchain_example.py
"""

import asyncio
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from cx_guardrails import (
    Guardrails,
    GuardrailsTarget,
    GuardrailsTriggered,
    PII,
    PIICategory,
    PromptInjection,
)
from llm_tracekit.langchain import LangChainInstrumentor, setup_export_to_coralogix

setup_export_to_coralogix(service_name="guardrails-langchain-example")
LangChainInstrumentor().instrument()

TEST_PII = "your email is example@example.com"

guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)
llm = ChatOpenAI(model="gpt-4o-mini")


async def main():
    user_content = "What is the capital of France?"
    history = [HumanMessage(content=user_content)]
    config = [PII(categories=[PIICategory.EMAIL_ADDRESS]), PromptInjection()]

    # Build messages incrementally
    messages = []

    async with guardrails.guarded_session():
        messages = [{"role": "user", "content": user_content}]
        try:
            await guardrails.guard(
                [PromptInjection()], messages, GuardrailsTarget.PROMPT
            )
        except GuardrailsTriggered as e:
            print(f"Prompt blocked: {e}")
            return

        # Call LangChain (note: LangChain uses its own message format)
        langchain_messages = [HumanMessage(content=user_input)]
        response = await llm.ainvoke(langchain_messages)
        response_content = response.content

        # Append assistant response and guard it
        messages.append({"role": "assistant", "content": response_content})
        try:
            await guardrails.guard(config, messages, GuardrailsTarget.RESPONSE)
            print(f"Assistant: {response.content}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


async def example_pii_blocked():
    guardrails = Guardrails()
    llm = ChatOpenAI(model=MODEL)
    user_input = "What is the capital of France?"

    # Build messages incrementally
    messages = []

    async with guardrails.guarded_session():
        # Append user input and guard the prompt
        messages.append({"role": "user", "content": user_input})
        try:
            await guardrails.guard(messages, PROMPT_GUARDRAILS, GuardrailsTarget.PROMPT)
        except GuardrailsTriggered as e:
            print(f"Prompt blocked: {e}")
            return

        # Call LangChain (note: LangChain uses its own message format)
        langchain_messages = [HumanMessage(content=user_input)]
        response = await llm.ainvoke(langchain_messages)
        response_content = response.content

        # Simulate PII leaking (e.g., from a database/tool)
        response_with_pii = response_content + TEST_PII

        # Append assistant response (with PII) and guard it
        messages.append({"role": "assistant", "content": response_with_pii})
        try:
            await guardrails.guard(messages, RESPONSE_GUARDRAILS, GuardrailsTarget.RESPONSE)
            print(f"Response: {response_with_pii}")
        except GuardrailsTriggered as e:
            print(f"Response blocked (PII detected): {e}")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


async def main():
    await example_basic()
    await example_pii_blocked()


if __name__ == "__main__":
    setup_export_to_coralogix(service_name="langchain-example")
    LangChainInstrumentor().instrument()
    asyncio.run(main())
