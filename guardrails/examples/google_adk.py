"""Using Guardrails with Google ADK (Agent Development Kit)."""

import asyncio
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from cx_guardrails import (
    Guardrails,
    PII,
    PromptInjection,
    PIICategory,
    GuardrailsTriggered,
    GuardrailsTarget,
)
from llm_tracekit.google_adk import GoogleADKInstrumentor, setup_export_to_coralogix

setup_export_to_coralogix(service_name="guardrails-google-adk-example")
GoogleADKInstrumentor().instrument()

TEST_PII = "your email is example@example.com"

guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)
agent = Agent(
    name="Assistant",
    model="gemini-2.0-flash",
    instruction="You are a helpful assistant.",
)
session_service = InMemorySessionService()


async def main():
    runner = Runner(agent=agent, app_name="my_app", session_service=session_service)
    session = await session_service.create_session(app_name="my_app", user_id="user_1")

    user_input = "What is the capital of France?"
    config = [PII(categories=[PIICategory.EMAIL_ADDRESS]), PromptInjection()]

    async with guardrails.guarded_session():
        try:
            await guardrails.guard(
                [PromptInjection()],
                [{"role": "user", "content": user_input}],
                GuardrailsTarget.PROMPT,
            )
        except GuardrailsTriggered as e:
            return print(f"Prompt blocked: {e}")

        response_text = ""
        async for event in runner.run_async(
            user_id="user_1",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=user_input)]),
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text

        response_content = response_text + TEST_PII
        messages = [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": response_content},
        ]

        try:
            await guardrails.guard(config, messages, GuardrailsTarget.RESPONSE)
            print(f"Assistant: {response_text}")
        except GuardrailsTriggered as e:
            print(f"Response blocked: {e}")


if __name__ == "__main__":
    asyncio.run(main())
