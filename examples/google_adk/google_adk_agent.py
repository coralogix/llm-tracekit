"""
Google ADK Agent Example with Tools and Multi-turn Conversation

This example demonstrates the LLM Tracekit instrumentation for Google ADK,
showcasing:
- Basic agent with tools
- Multi-turn conversation
- Tool execution
- Semantic convention attributes on spans

Usage:
    uv run python examples/google_adk/google_adk_agent.py
"""

import asyncio
import os

# Set API key before importing google.adk
os.environ["GOOGLE_API_KEY"] = "AIzaSyA8NSbmQxtnNum5WyqHFozLVDZpC9X7v7A"

from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

from llm_tracekit import GoogleADKInstrumentor, setup_export_to_coralogix


def get_current_weather(city: str, unit: str = "celsius") -> dict:
    """Get the current weather in a given city.

    Args:
        city: The city name to get weather for
        unit: Temperature unit, either 'celsius' or 'fahrenheit'

    Returns:
        Weather information for the city
    """
    # Mock weather data
    weather_data = {
        "Tokyo": {"temp": 22, "condition": "Sunny", "humidity": 45},
        "Paris": {"temp": 18, "condition": "Cloudy", "humidity": 65},
        "New York": {"temp": 25, "condition": "Partly Cloudy", "humidity": 55},
        "London": {"temp": 15, "condition": "Rainy", "humidity": 80},
    }

    data = weather_data.get(city, {"temp": 20, "condition": "Unknown", "humidity": 50})

    if unit == "fahrenheit":
        data["temp"] = int(data["temp"] * 9 / 5 + 32)

    return {
        "city": city,
        "temperature": data["temp"],
        "unit": unit,
        "condition": data["condition"],
        "humidity": data["humidity"],
    }


def calculate(expression: str) -> dict:
    """Evaluate a mathematical expression.

    Args:
        expression: A mathematical expression to evaluate (e.g., "2 + 2", "10 * 5")

    Returns:
        The result of the calculation
    """
    try:
        # Only allow safe mathematical operations
        allowed_chars = set("0123456789+-*/(). ")
        if not all(c in allowed_chars for c in expression):
            return {"error": "Invalid characters in expression"}

        result = eval(expression)  # noqa: S307
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": str(e)}


async def run_multi_turn_conversation():
    """Run a multi-turn conversation with the agent."""
    print("\n" + "=" * 60)
    print("Google ADK Multi-Turn Conversation with Tools")
    print("=" * 60 + "\n")

    # Create the agent with tools
    agent = Agent(
        name="weather_assistant",
        model="gemini-2.0-flash",
        instruction="""You are a helpful weather assistant. You can:
1. Get current weather for cities using the get_current_weather tool
2. Perform calculations using the calculate tool

Always be friendly and provide detailed responses. When asked about weather,
use the get_current_weather tool. When asked to calculate something, use
the calculate tool.""",
        tools=[get_current_weather, calculate],
    )

    # Create session service and runner
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="weather_app",
        session_service=session_service,
    )

    # Create a session
    session = await session_service.create_session(
        app_name="weather_app",
        user_id="user_123",
    )

    print(f"Session created: {session.id}\n")

    # Multi-turn conversation
    messages = [
        "What's the weather like in Tokyo?",
        "How about Paris? Is it warmer or colder than Tokyo?",
        "Can you calculate the temperature difference between them in Fahrenheit?",
        "Thanks! What was my first question?",
    ]

    for i, user_message in enumerate(messages, 1):
        print(f"\n--- Turn {i} ---")
        print(f"User: {user_message}")

        # Run the agent
        response_text = ""
        async for event in runner.run_async(
            user_id="user_123",
            session_id=session.id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=user_message)],
            ),
        ):
            # Collect text from model responses
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_text += part.text

        print(f"Assistant: {response_text.strip()}")

    # Cleanup
    await runner.close()
    print("\n" + "=" * 60)
    print("Conversation complete!")
    print("=" * 60 + "\n")


async def run_simple_example():
    """Run a simple single-turn example."""
    print("\n" + "=" * 60)
    print("Google ADK Simple Example")
    print("=" * 60 + "\n")

    agent = Agent(
        name="simple_assistant",
        model="gemini-2.0-flash",
        instruction="You are a helpful assistant. Be concise.",
    )

    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="simple_app",
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name="simple_app",
        user_id="user_456",
    )

    print("User: What is the capital of France?")

    response_text = ""
    async for event in runner.run_async(
        user_id="user_456",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text="What is the capital of France?")],
        ),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    response_text += part.text

    print(f"Assistant: {response_text.strip()}")

    await runner.close()
    print("\n" + "=" * 60 + "\n")


async def main():
    """Main function to run all examples."""
    # Setup tracing with console exporter for debugging
    setup_export_to_coralogix(
        service_name="google-adk-example",
        application_name="llm-tracekit",
        subsystem_name="examples",
        coralogix_token="cxtp_fnjoa0nW9Hscj5g0mV7KAFWkFp2Mtj",
        coralogix_endpoint="https://ingress.eu2.coralogix.com",
        capture_content=True,
        processors=[SimpleSpanProcessor(ConsoleSpanExporter())],
    )

    # Instrument Google ADK
    GoogleADKInstrumentor().instrument()

    print("\nGoogle ADK Instrumentation Example")
    print("=" * 60)
    print("This example demonstrates the LLM Tracekit instrumentation")
    print("for Google ADK with semantic convention attributes.")
    print("=" * 60)

    # Run examples
    await run_simple_example()
    await run_multi_turn_conversation()


if __name__ == "__main__":
    asyncio.run(main())

