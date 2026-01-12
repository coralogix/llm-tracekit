"""Simple interactive chat with guardrails and conversation state."""

import asyncio
from openai import AsyncOpenAI
from cx_guardrails import (
    Guardrails,
    PII,
    PromptInjection,
    GuardrailsTriggered,
    GuardrailsTarget,
    setup_export_to_coralogix,
)

setup_export_to_coralogix(service_name="guardrails-simple-chat-example",
    application_name="my_application",
    subsystem_name="my_subsystem",
    capture_content=True,
)

guardrails = Guardrails(application_name="simple_chat", subsystem_name="conversation")
client = AsyncOpenAI()


async def main():
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. Keep responses concise.",
        }
    ]

    async with guardrails.guarded_session():
        while True:
            user_input = input("\nYou: ").strip()
            if not user_input or user_input.lower() in ("exit", "quit"):
                break

            messages.append({"role": "user", "content": user_input})

            try:
                await guardrails.guard(
                    guardrails=[PromptInjection(), PII()],
                    messages=messages,
                    target=GuardrailsTarget.PROMPT,
                )
            except GuardrailsTriggered as e:
                messages.pop()
                print(f"Prompt blocked: {e}")
                continue

            response = await client.chat.completions.create(
                model="gpt-4o-mini", messages=messages
            )
            assistant_content = response.choices[0].message.content
            messages.append({"role": "assistant", "content": assistant_content})

            try:
                await guardrails.guard(
                    guardrails=[
                        PII(),
                    ],
                    messages=messages,
                    target=GuardrailsTarget.RESPONSE,
                )
                print(f"Assistant: {assistant_content}")
            except GuardrailsTriggered as e:
                messages.pop()
                print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
