# Copyright Coralogix Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from tests_google_adk.utils import assert_base_attributes, get_call_llm_spans


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_google_adk_simple_completion(span_exporter, instrument):
    """Test basic completion without tools."""
    agent = Agent(
        name="test_agent",
        model="gemini-2.0-flash",
        instruction="You are a helpful assistant. Be concise.",
    )

    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="test_app",
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name="test_app",
        user_id="test_user",
    )

    async for _ in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text="Say hello in exactly 3 words.")],
        ),
    ):
        pass

    await runner.close()

    spans = span_exporter.get_finished_spans()
    call_llm_spans = get_call_llm_spans(spans)
    assert len(call_llm_spans) == 1
    span = call_llm_spans[0]

    assert_base_attributes(
        span,
        system="gcp.vertex.agent",
        request_model="gemini-2.0-flash",
    )

    # Check system instruction is first message
    assert span.attributes is not None
    assert span.attributes.get("gen_ai.prompt.0.role") == "system"
    assert "You are a helpful assistant" in str(
        span.attributes.get("gen_ai.prompt.0.content")
    )

    # Check user message is second
    assert span.attributes.get("gen_ai.prompt.1.role") == "user"
    assert (
        span.attributes.get("gen_ai.prompt.1.content")
        == "Say hello in exactly 3 words."
    )

    # Check completion has role and finish_reason
    assert span.attributes.get("gen_ai.completion.0.role") == "assistant"
    assert span.attributes.get("gen_ai.completion.0.finish_reason") == "stop"
    # Check content exists (value depends on LLM response)
    assert "gen_ai.completion.0.content" in span.attributes


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_google_adk_with_tool_call(span_exporter, instrument):
    """Test completion with tool calls."""

    def get_weather(city: str) -> dict:
        """Get the weather for a city.

        Args:
            city: The city name

        Returns:
            Weather data
        """
        return {"city": city, "temperature": 22, "condition": "Sunny"}

    agent = Agent(
        name="weather_agent",
        model="gemini-2.0-flash",
        instruction="Use the get_weather tool when asked about weather.",
        tools=[get_weather],
    )

    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="test_app",
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name="test_app",
        user_id="test_user",
    )

    async for _ in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text="What's the weather in Tokyo?")],
        ),
    ):
        pass

    await runner.close()

    spans = span_exporter.get_finished_spans()
    call_llm_spans = get_call_llm_spans(spans)

    # Should have 2 call_llm spans: one for tool call, one for final response
    assert len(call_llm_spans) == 2

    # First span: tool call request
    first_span = call_llm_spans[0]
    assert first_span.attributes is not None
    # System instruction is first
    assert first_span.attributes.get("gen_ai.prompt.0.role") == "system"
    # User message is second
    assert first_span.attributes.get("gen_ai.prompt.1.role") == "user"
    assert (
        first_span.attributes.get("gen_ai.prompt.1.content")
        == "What's the weather in Tokyo?"
    )
    # Tool call in completion
    assert (
        first_span.attributes.get("gen_ai.completion.0.tool_calls.0.type") == "function"
    )
    assert (
        first_span.attributes.get("gen_ai.completion.0.tool_calls.0.function.name")
        == "get_weather"
    )
    # Tool definition in request
    assert first_span.attributes.get("gen_ai.request.tools.0.type") == "function"
    assert (
        first_span.attributes.get("gen_ai.request.tools.0.function.name")
        == "get_weather"
    )

    # Second span: final response with tool result in history
    second_span = call_llm_spans[1]
    assert second_span.attributes is not None
    # Should have full history: system, user message, assistant tool call, tool response
    assert second_span.attributes.get("gen_ai.prompt.0.role") == "system"
    assert second_span.attributes.get("gen_ai.prompt.1.role") == "user"
    assert second_span.attributes.get("gen_ai.prompt.2.role") == "assistant"
    assert second_span.attributes.get("gen_ai.prompt.3.role") == "tool"
    # Final response
    assert second_span.attributes.get("gen_ai.completion.0.role") == "assistant"
    assert second_span.attributes.get("gen_ai.completion.0.finish_reason") == "stop"


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_google_adk_multi_turn(span_exporter, instrument):
    """Test multi-turn conversation preserves history."""
    agent = Agent(
        name="test_agent",
        model="gemini-2.0-flash",
        instruction="You are a helpful assistant. Be concise.",
    )

    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="test_app",
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name="test_app",
        user_id="test_user",
    )

    # First turn
    async for _ in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text="My name is Alice.")],
        ),
    ):
        pass

    # Second turn
    async for _ in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text="What is my name?")],
        ),
    ):
        pass

    await runner.close()

    spans = span_exporter.get_finished_spans()
    call_llm_spans = get_call_llm_spans(spans)

    # Should have 2 call_llm spans for 2 turns
    assert len(call_llm_spans) == 2

    # First span: system instruction + first message
    first_span = call_llm_spans[0]
    assert first_span.attributes is not None
    assert first_span.attributes.get("gen_ai.prompt.0.role") == "system"
    assert first_span.attributes.get("gen_ai.prompt.1.role") == "user"
    assert first_span.attributes.get("gen_ai.prompt.1.content") == "My name is Alice."

    # Second span: should have full history
    second_span = call_llm_spans[1]
    assert second_span.attributes is not None
    # History: system, user (Alice), assistant response, user (what's my name?)
    assert second_span.attributes.get("gen_ai.prompt.0.role") == "system"
    assert second_span.attributes.get("gen_ai.prompt.1.role") == "user"
    assert second_span.attributes.get("gen_ai.prompt.1.content") == "My name is Alice."
    assert second_span.attributes.get("gen_ai.prompt.2.role") == "assistant"
    assert second_span.attributes.get("gen_ai.prompt.3.role") == "user"
    assert second_span.attributes.get("gen_ai.prompt.3.content") == "What is my name?"
