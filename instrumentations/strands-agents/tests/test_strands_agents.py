# Copyright Coralogix Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this package except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

import pytest
from strands import Agent, tool
from strands.models.bedrock import BedrockModel
from opentelemetry.trace import SpanKind

from .utils import (
    get_agent_spans,
    get_cycle_spans,
    get_chat_spans,
    get_tool_spans,
    assert_agent_span_attributes,
    assert_chat_span_attributes,
    assert_tool_span_attributes,
    assert_messages_in_span,
    assert_choices_in_span,
)

MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
PROMPT_SIMPLE = "Say 'This is a test.' and nothing else."
PROMPT_WEATHER = "What's the weather in Tel Aviv?"


def _make_agent(system_prompt="Be a helpful assistant. Be concise.", tools=None):
    model = BedrockModel(model_id=MODEL_ID)
    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools or [],
    )


# ── Simple completion ────────────────────────────────────────────────


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_simple_completion(span_exporter, metric_reader, instrument_with_content):
    """Test basic agent invocation produces correct span hierarchy, attributes, and content."""
    agent = _make_agent()
    await agent.invoke_async(PROMPT_SIMPLE)

    # Exact span counts: 1 agent, 1 cycle, 1 chat, 0 tools
    all_spans = span_exporter.get_finished_spans()
    agent_spans = get_agent_spans(span_exporter)
    cycle_spans = get_cycle_spans(span_exporter)
    chat_spans = get_chat_spans(span_exporter)
    tool_spans = get_tool_spans(span_exporter)

    assert len(agent_spans) == 1
    assert len(cycle_spans) == 1
    assert len(chat_spans) == 1
    assert len(tool_spans) == 0
    assert len(all_spans) == 3  # agent + cycle + chat

    # Agent span attributes
    assert_agent_span_attributes(agent_spans[0], agent_name=agent.name, model=MODEL_ID)
    assert agent_spans[0].kind == SpanKind.INTERNAL
    assert agent_spans[0].attributes.get("gen_ai.usage.input_tokens", 0) > 0
    assert agent_spans[0].attributes.get("gen_ai.usage.output_tokens", 0) > 0

    # Chat span structural attributes
    assert_chat_span_attributes(chat_spans[0], request_model=MODEL_ID)
    assert chat_spans[0].kind == SpanKind.CLIENT
    assert chat_spans[0].attributes["gen_ai.response.model"] == MODEL_ID
    assert chat_spans[0].attributes["gen_ai.response.finish_reasons"] == ("end_turn",)

    # Span hierarchy: agent -> cycle -> chat
    assert cycle_spans[0].parent is not None
    assert cycle_spans[0].parent.span_id == agent_spans[0].context.span_id
    assert chat_spans[0].parent is not None
    assert chat_spans[0].parent.span_id == cycle_spans[0].context.span_id

    # Exact prompt content on the chat span
    assert_messages_in_span(
        chat_spans[0],
        expected_messages=[
            {"role": "user", "content": PROMPT_SIMPLE},
        ],
        expect_content=True,
    )

    # Exact completion content
    assert_choices_in_span(
        chat_spans[0],
        expected_choices=[
            {
                "finish_reason": "end_turn",
                "message": {"role": "assistant", "content": "This is a test."},
            },
        ],
        expect_content=True,
    )

    # Metrics
    metrics_data = metric_reader.get_metrics_data()
    metric_names = set()
    for rm in metrics_data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                metric_names.add(m.name)
    assert "gen_ai.client.operation.duration" in metric_names
    assert "gen_ai.client.token.usage" in metric_names


# ── Tool usage ───────────────────────────────────────────────────────


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_agent_with_tool(span_exporter, instrument_with_content):
    """Test tool call produces correct spans, message history, and tool content."""

    @tool
    def get_weather(city: str) -> str:
        """Get the current weather for a city.

        Args:
            city: The city name.

        Returns:
            Weather description.
        """
        return f"The weather in {city} is 22°C and sunny."

    agent = _make_agent(
        system_prompt="Use the get_weather tool when asked about weather.",
        tools=[get_weather],
    )
    await agent.invoke_async(PROMPT_WEATHER)

    agent_spans = get_agent_spans(span_exporter)
    cycle_spans = get_cycle_spans(span_exporter)
    chat_spans = get_chat_spans(span_exporter)
    tool_spans = get_tool_spans(span_exporter)

    assert len(agent_spans) == 1
    assert len(cycle_spans) == 2  # tool_use cycle + final response cycle
    assert len(chat_spans) == 2  # tool_use request + final response
    assert len(tool_spans) == 1

    # Agent span should list registered tools
    agent_tools_raw = agent_spans[0].attributes.get("gen_ai.agent.tools")
    assert agent_tools_raw is not None
    agent_tools = json.loads(agent_tools_raw)
    assert "get_weather" in agent_tools

    # Tool span attributes
    assert_tool_span_attributes(tool_spans[0], tool_name="get_weather")
    assert tool_spans[0].kind == SpanKind.INTERNAL
    assert tool_spans[0].attributes.get("gen_ai.tool.status") == "success"
    assert tool_spans[0].attributes.get("gen_ai.tool.call.id") is not None

    # Tool input/output content
    tool_input = json.loads(tool_spans[0].attributes["input"])
    assert tool_input["city"] == "Tel Aviv"
    tool_output = json.loads(tool_spans[0].attributes["output"])
    assert any(
        "22" in item.get("text", "") and "sunny" in item.get("text", "")
        for item in tool_output
    )

    # First chat span: tool_use request
    first_chat = chat_spans[0]
    assert first_chat.attributes["gen_ai.response.finish_reasons"] == ("tool_use",)
    assert (
        first_chat.attributes.get("gen_ai.completion.0.tool_calls.0.function.name")
        == "get_weather"
    )
    tool_call_id = first_chat.attributes.get("gen_ai.completion.0.tool_calls.0.id")
    assert tool_call_id is not None

    # First chat prompt should contain only the user message
    assert first_chat.attributes.get("gen_ai.prompt.0.role") == "user"
    assert first_chat.attributes.get("gen_ai.prompt.0.content") == PROMPT_WEATHER

    # Second chat span: final response with full history
    last_chat = chat_spans[1]
    assert last_chat.attributes["gen_ai.response.finish_reasons"] == ("end_turn",)

    assert last_chat.attributes.get("gen_ai.prompt.0.role") == "user"
    assert last_chat.attributes.get("gen_ai.prompt.0.content") == PROMPT_WEATHER

    # History should include: assistant tool_call, then tool result
    assert last_chat.attributes.get("gen_ai.prompt.1.role") == "assistant"
    assert (
        last_chat.attributes.get("gen_ai.prompt.1.tool_calls.0.function.name")
        == "get_weather"
    )
    assert last_chat.attributes.get("gen_ai.prompt.1.tool_calls.0.id") == tool_call_id

    assert last_chat.attributes.get("gen_ai.prompt.2.role") == "user"
    assert last_chat.attributes.get("gen_ai.prompt.2.tool_call_id") == tool_call_id

    # Final completion should be a text response
    assert_choices_in_span(
        last_chat,
        expected_choices=[
            {
                "finish_reason": "end_turn",
                "message": {"role": "assistant"},
            },
        ],
        expect_content=False,
    )
    assert last_chat.attributes.get("gen_ai.completion.0.content") is not None


# ── Content capture toggle ───────────────────────────────────────────


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_agent_no_content_capture(span_exporter, instrument_no_content):
    """Test that prompt/completion content is stripped when capture is disabled."""
    agent = _make_agent()
    await agent.invoke_async("Say 'Hello world.'")

    chat_spans = get_chat_spans(span_exporter)
    assert len(chat_spans) == 1
    chat = chat_spans[0]

    # Structural attributes still present
    assert_chat_span_attributes(chat, request_model=MODEL_ID)
    assert chat.attributes["gen_ai.response.finish_reasons"] == ("end_turn",)

    # No prompt/completion content attributes should be present
    for key in chat.attributes:
        assert not (key.startswith("gen_ai.prompt.") and key.endswith(".content"))
        assert not (key.startswith("gen_ai.completion.") and key.endswith(".content"))

    # No role/finish_reason on individual choices either (all content capture is off)
    assert "gen_ai.prompt.0.role" not in chat.attributes
    assert "gen_ai.completion.0.role" not in chat.attributes


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_agent_with_tool_no_content(span_exporter, instrument_no_content):
    """Test tool spans omit input/output when content capture is disabled."""

    @tool
    def calculator(expression: str) -> str:
        """Evaluate a math expression.

        Args:
            expression: The math expression to evaluate.

        Returns:
            The result.
        """
        return str(eval(expression))

    agent = _make_agent(
        system_prompt="Use the calculator tool for math.",
        tools=[calculator],
    )
    await agent.invoke_async("What is 2 + 2?")

    tool_spans = get_tool_spans(span_exporter)
    assert len(tool_spans) >= 1

    # Tool structural attributes present
    assert_tool_span_attributes(tool_spans[0], tool_name="calculator")
    assert tool_spans[0].attributes.get("gen_ai.tool.status") == "success"

    # Content must NOT be present
    assert "input" not in tool_spans[0].attributes
    assert "output" not in tool_spans[0].attributes

    # Chat spans should not have prompt/completion content either
    chat_spans = get_chat_spans(span_exporter)
    for chat in chat_spans:
        for key in chat.attributes:
            assert not (key.startswith("gen_ai.prompt.") and key.endswith(".content"))
            assert not (
                key.startswith("gen_ai.completion.") and key.endswith(".content")
            )


# ── Multi-cycle ──────────────────────────────────────────────────────


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_agent_multi_cycle(span_exporter, instrument_with_content):
    """Test agent with tool produces multiple cycles with correct hierarchy and token aggregation."""

    @tool
    def get_capital(country: str) -> str:
        """Get the capital city of a country.

        Args:
            country: The country name.

        Returns:
            The capital city.
        """
        return f"The capital of {country} is Paris."

    agent = _make_agent(
        system_prompt="Use the get_capital tool when asked about capitals. Answer concisely.",
        tools=[get_capital],
    )
    await agent.invoke_async("What is the capital of France?")

    agent_spans = get_agent_spans(span_exporter)
    cycle_spans = get_cycle_spans(span_exporter)
    chat_spans = get_chat_spans(span_exporter)

    assert len(agent_spans) == 1
    assert len(cycle_spans) == 2  # tool_use + final response
    assert len(chat_spans) == 2

    # All cycles are children of the agent span
    for cycle in cycle_spans:
        assert cycle.parent is not None
        assert cycle.parent.span_id == agent_spans[0].context.span_id

    # Each chat span is child of its respective cycle
    for chat, cycle in zip(chat_spans, cycle_spans):
        assert chat.parent is not None
        assert chat.parent.span_id == cycle.context.span_id

    # Token usage aggregated on the agent span
    agent_attrs = agent_spans[0].attributes
    assert agent_attrs.get("gen_ai.usage.input_tokens", 0) > 0
    assert agent_attrs.get("gen_ai.usage.output_tokens", 0) > 0

    # First chat finishes with tool_use, second with end_turn
    assert chat_spans[0].attributes["gen_ai.response.finish_reasons"] == ("tool_use",)
    assert chat_spans[1].attributes["gen_ai.response.finish_reasons"] == ("end_turn",)


# ── Tool error ───────────────────────────────────────────────────────


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_agent_tool_error(span_exporter, instrument_with_content):
    """Test that tool exceptions are captured with OTel error attributes."""

    @tool
    def failing_tool(query: str) -> str:
        """A tool that always fails.

        Args:
            query: Any query.

        Returns:
            Never returns.
        """
        raise ValueError("Tool failed as intended for testing")

    agent = _make_agent(
        system_prompt="Use the failing_tool when asked anything.",
        tools=[failing_tool],
    )
    await agent.invoke_async("Do something.")

    tool_spans = get_tool_spans(span_exporter)
    assert len(tool_spans) >= 1

    failing_span = tool_spans[0]
    assert failing_span.attributes.get("error.type") == "ValueError"
    assert_tool_span_attributes(failing_span, tool_name="failing_tool")

    # Tool should NOT have a success status
    assert failing_span.attributes.get("gen_ai.tool.status") is None

    # The agent should still complete (Strands handles tool errors gracefully)
    agent_spans = get_agent_spans(span_exporter)
    assert len(agent_spans) == 1

    # The second chat span (after the error) should have the tool result in history
    chat_spans = get_chat_spans(span_exporter)
    assert len(chat_spans) >= 2
    last_chat = chat_spans[-1]
    assert last_chat.attributes["gen_ai.response.finish_reasons"] == ("end_turn",)


# ── Multi-turn conversation ─────────────────────────────────────────


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_agent_multi_turn(span_exporter, instrument_with_content):
    """Test that conversation history accumulates across turns."""
    agent = _make_agent()

    await agent.invoke_async("My name is Alice.")
    await agent.invoke_async("What is my name?")

    agent_spans = get_agent_spans(span_exporter)
    assert len(agent_spans) == 2  # one per invocation

    chat_spans = get_chat_spans(span_exporter)
    assert len(chat_spans) == 2

    # First turn: single user message
    first_chat = chat_spans[0]
    assert first_chat.attributes.get("gen_ai.prompt.0.role") == "user"
    assert first_chat.attributes.get("gen_ai.prompt.0.content") == "My name is Alice."
    assert first_chat.attributes.get("gen_ai.completion.0.role") == "assistant"
    assert first_chat.attributes.get("gen_ai.completion.0.finish_reason") == "end_turn"

    # Second turn: should include history (user + assistant + user)
    second_chat = chat_spans[1]
    assert second_chat.attributes.get("gen_ai.prompt.0.role") == "user"
    assert second_chat.attributes.get("gen_ai.prompt.0.content") == "My name is Alice."
    assert second_chat.attributes.get("gen_ai.prompt.1.role") == "assistant"
    assert second_chat.attributes.get("gen_ai.prompt.1.content") is not None
    assert second_chat.attributes.get("gen_ai.prompt.2.role") == "user"
    assert second_chat.attributes.get("gen_ai.prompt.2.content") == "What is my name?"

    # The response should reference "Alice"
    response_content = second_chat.attributes.get("gen_ai.completion.0.content", "")
    assert "Alice" in response_content


# ── Uninstrumentation ────────────────────────────────────────────────


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_uninstrument_no_spans(span_exporter, tracer_provider, meter_provider):
    """Test that after uninstrumenting, no agent/chat/tool spans are emitted."""
    from llm_tracekit.strands_agents import StrandsInstrumentor
    import os
    from llm_tracekit.core import OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT

    os.environ[OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT] = "True"
    instrumentor = StrandsInstrumentor()
    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    agent = _make_agent()
    await agent.invoke_async("Say 'test'.")

    spans_before = list(span_exporter.get_finished_spans())
    assert len(spans_before) >= 3  # at least agent + cycle + chat

    instrumentor.uninstrument()
    span_exporter.clear()

    agent2 = _make_agent()
    await agent2.invoke_async("Say 'test again'.")

    spans_after = span_exporter.get_finished_spans()
    agent_spans_after = [s for s in spans_after if s.name.startswith("invoke_agent")]
    chat_spans_after = [s for s in spans_after if s.name.startswith("chat")]
    assert len(agent_spans_after) == 0
    assert len(chat_spans_after) == 0

    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
