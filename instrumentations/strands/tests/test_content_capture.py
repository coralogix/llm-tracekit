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

"""Tests for US2: Content Capture."""

import json
import pytest
from unittest.mock import MagicMock

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import get_tracer
from opentelemetry.metrics import get_meter

from llm_tracekit.strands.hook_provider import StrandsHookProvider
from llm_tracekit.core._metrics import Instruments
from strands.hooks.events import (
    BeforeInvocationEvent,
    AfterInvocationEvent,
    BeforeModelCallEvent,
    AfterModelCallEvent,
    BeforeToolCallEvent,
    AfterToolCallEvent,
)

from utils import find_span_by_name_prefix


@pytest.fixture
def hook_provider_with_content(tracer_provider, meter_provider):
    tracer = get_tracer("test", tracer_provider=tracer_provider)
    meter = get_meter("test", meter_provider=meter_provider)
    instruments = Instruments(meter)
    return StrandsHookProvider(tracer=tracer, instruments=instruments, capture_content=True)


@pytest.fixture
def hook_provider_no_content(tracer_provider, meter_provider):
    tracer = get_tracer("test", tracer_provider=tracer_provider)
    meter = get_meter("test", meter_provider=meter_provider)
    instruments = Instruments(meter)
    return StrandsHookProvider(tracer=tracer, instruments=instruments, capture_content=False)


def _make_agent():
    agent = MagicMock()
    agent.name = "ContentTestAgent"
    agent.model = MagicMock()
    agent.model.model_id = "anthropic.claude-sonnet-4-20250514"
    agent.tool_registry = MagicMock()
    agent.tool_registry.registry = {}
    agent.tool_registry.get_all_tools_config = None
    return agent


def _make_invocation_state(cycle_id="cycle-1", messages=None):
    state = MagicMock()
    state.cycle_id = cycle_id
    state.model_id = "anthropic.claude-sonnet-4-20250514"
    state.messages = messages or [
        {"role": "system", "content": [{"text": "You are a helpful assistant."}]},
        {"role": "user", "content": [{"text": "What is the weather in Paris?"}]},
    ]
    return state


def _make_stop_response_with_text():
    resp = MagicMock()
    resp.metrics = {"usage": {"inputTokens": 100, "outputTokens": 50}}
    resp.stop_reason = "end_turn"
    resp.model = "anthropic.claude-sonnet-4-20250514"
    resp.message = {
        "role": "assistant",
        "content": [{"text": "The weather in Paris is 22°C and sunny."}],
    }
    return resp


def _make_stop_response_with_tool_call():
    resp = MagicMock()
    resp.metrics = {"usage": {"inputTokens": 100, "outputTokens": 50}}
    resp.stop_reason = "tool_use"
    resp.model = "anthropic.claude-sonnet-4-20250514"
    resp.message = {
        "role": "assistant",
        "content": [
            {"toolUse": {"toolUseId": "tu-123", "name": "get_weather", "input": {"city": "Paris"}}},
        ],
    }
    return resp


def _simulate_call(hook_provider, inv_state=None, stop_response=None):
    agent = _make_agent()
    if inv_state is None:
        inv_state = _make_invocation_state()
    if stop_response is None:
        stop_response = _make_stop_response_with_text()

    hook_provider._before_invocation(
        BeforeInvocationEvent(agent=agent, invocation_state=inv_state, messages=[]),
        agent=agent,
    )
    hook_provider._before_model_call(
        BeforeModelCallEvent(agent=agent, invocation_state=inv_state), agent=agent,
    )
    hook_provider._after_model_call(
        AfterModelCallEvent(
            agent=agent, invocation_state=inv_state,
            stop_response=stop_response, exception=None, retry=False,
        ),
        agent=agent,
    )
    result = MagicMock()
    hook_provider._after_invocation(
        AfterInvocationEvent(agent=agent, invocation_state=inv_state, result=result),
        agent=agent,
    )


class TestContentCaptureEnabled:
    def test_prompt_role_and_content(self, hook_provider_with_content, span_exporter: InMemorySpanExporter):
        _simulate_call(hook_provider_with_content)
        span = find_span_by_name_prefix(span_exporter, "chat")
        assert span is not None
        assert span.attributes["gen_ai.prompt.0.role"] == "system"
        assert span.attributes["gen_ai.prompt.0.content"] == "You are a helpful assistant."
        assert span.attributes["gen_ai.prompt.1.role"] == "user"
        assert span.attributes["gen_ai.prompt.1.content"] == "What is the weather in Paris?"

    def test_completion_role_and_content(self, hook_provider_with_content, span_exporter: InMemorySpanExporter):
        _simulate_call(hook_provider_with_content)
        span = find_span_by_name_prefix(span_exporter, "chat")
        assert span is not None
        assert span.attributes["gen_ai.completion.0.role"] == "assistant"
        assert span.attributes["gen_ai.completion.0.content"] == "The weather in Paris is 22°C and sunny."
        assert span.attributes["gen_ai.completion.0.finish_reason"] == "end_turn"

    def test_completion_tool_call_attributes(self, hook_provider_with_content, span_exporter: InMemorySpanExporter):
        stop_resp = _make_stop_response_with_tool_call()
        _simulate_call(hook_provider_with_content, stop_response=stop_resp)
        span = find_span_by_name_prefix(span_exporter, "chat")
        assert span is not None
        assert span.attributes["gen_ai.completion.0.tool_calls.0.id"] == "tu-123"
        assert span.attributes["gen_ai.completion.0.tool_calls.0.type"] == "function"
        assert span.attributes["gen_ai.completion.0.tool_calls.0.function.name"] == "get_weather"
        args = span.attributes["gen_ai.completion.0.tool_calls.0.function.arguments"]
        assert json.loads(args) == {"city": "Paris"}

    def test_prompt_tool_call_attributes(self, hook_provider_with_content, span_exporter: InMemorySpanExporter):
        messages = [
            {"role": "user", "content": [{"text": "What is the weather?"}]},
            {"role": "assistant", "content": [
                {"toolUse": {"toolUseId": "tu-abc", "name": "get_weather", "input": {"city": "Paris"}}},
            ]},
            {"role": "user", "content": [
                {"toolResult": {"toolUseId": "tu-abc", "content": [{"text": "22°C, sunny"}]}},
            ]},
        ]
        inv_state = _make_invocation_state(messages=messages)
        _simulate_call(hook_provider_with_content, inv_state=inv_state)
        span = find_span_by_name_prefix(span_exporter, "chat")
        assert span is not None
        assert span.attributes["gen_ai.prompt.1.tool_calls.0.id"] == "tu-abc"
        assert span.attributes["gen_ai.prompt.1.tool_calls.0.function.name"] == "get_weather"
        assert span.attributes["gen_ai.prompt.2.tool_call_id"] == "tu-abc"
        assert span.attributes["gen_ai.prompt.2.content"] == "22°C, sunny"


class TestContentCaptureDisabled:
    def test_no_content_by_default(self, hook_provider_no_content, span_exporter: InMemorySpanExporter):
        _simulate_call(hook_provider_no_content)
        span = find_span_by_name_prefix(span_exporter, "chat")
        assert span is not None
        assert "gen_ai.prompt.0.content" not in span.attributes
        assert "gen_ai.completion.0.content" not in span.attributes


class TestToolContentCapture:
    def test_tool_input_output_captured(self, hook_provider_with_content, span_exporter: InMemorySpanExporter):
        agent = _make_agent()
        inv_state = _make_invocation_state()

        hook_provider_with_content._before_invocation(
            BeforeInvocationEvent(agent=agent, invocation_state=inv_state, messages=[]),
            agent=agent,
        )
        hook_provider_with_content._before_model_call(
            BeforeModelCallEvent(agent=agent, invocation_state=inv_state), agent=agent,
        )
        hook_provider_with_content._after_model_call(
            AfterModelCallEvent(
                agent=agent, invocation_state=inv_state,
                stop_response=_make_stop_response_with_text(), exception=None, retry=False,
            ),
            agent=agent,
        )

        tool_use = {"name": "get_weather", "toolUseId": "tu-1", "input": {"city": "Paris"}}
        selected_tool = MagicMock()
        selected_tool.is_mcp = False
        hook_provider_with_content._before_tool_call(
            BeforeToolCallEvent(
                agent=agent, selected_tool=selected_tool,
                tool_use=tool_use, invocation_state=inv_state, cancel_tool=False,
            ),
            agent=agent,
        )
        hook_provider_with_content._after_tool_call(
            AfterToolCallEvent(
                agent=agent, selected_tool=selected_tool,
                tool_use=tool_use, invocation_state=inv_state,
                result={"status": "success", "content": [{"text": "22°C, sunny"}]},
                exception=None, cancel_message=None, retry=False,
            ),
            agent=agent,
        )

        result = MagicMock()
        hook_provider_with_content._after_invocation(
            AfterInvocationEvent(agent=agent, invocation_state=inv_state, result=result),
            agent=agent,
        )

        tool_span = find_span_by_name_prefix(span_exporter, "execute_tool")
        assert tool_span is not None
        input_attr = tool_span.attributes.get("input")
        assert input_attr is not None
        assert json.loads(input_attr) == {"city": "Paris"}
        output_attr = tool_span.attributes.get("output")
        assert output_attr is not None

    def test_tool_no_content_when_disabled(self, hook_provider_no_content, span_exporter: InMemorySpanExporter):
        agent = _make_agent()
        inv_state = _make_invocation_state()

        hook_provider_no_content._before_invocation(
            BeforeInvocationEvent(agent=agent, invocation_state=inv_state, messages=[]),
            agent=agent,
        )
        hook_provider_no_content._before_model_call(
            BeforeModelCallEvent(agent=agent, invocation_state=inv_state), agent=agent,
        )
        hook_provider_no_content._after_model_call(
            AfterModelCallEvent(
                agent=agent, invocation_state=inv_state,
                stop_response=_make_stop_response_with_text(), exception=None, retry=False,
            ),
            agent=agent,
        )

        tool_use = {"name": "calc", "toolUseId": "tu-2", "input": {"expr": "1+1"}}
        selected_tool = MagicMock()
        selected_tool.is_mcp = False
        hook_provider_no_content._before_tool_call(
            BeforeToolCallEvent(
                agent=agent, selected_tool=selected_tool,
                tool_use=tool_use, invocation_state=inv_state, cancel_tool=False,
            ),
            agent=agent,
        )
        hook_provider_no_content._after_tool_call(
            AfterToolCallEvent(
                agent=agent, selected_tool=selected_tool,
                tool_use=tool_use, invocation_state=inv_state,
                result={"status": "success", "content": [{"text": "2"}]},
                exception=None, cancel_message=None, retry=False,
            ),
            agent=agent,
        )

        result = MagicMock()
        hook_provider_no_content._after_invocation(
            AfterInvocationEvent(agent=agent, invocation_state=inv_state, result=result),
            agent=agent,
        )

        tool_span = find_span_by_name_prefix(span_exporter, "execute_tool")
        assert tool_span is not None
        assert "input" not in tool_span.attributes
        assert "output" not in tool_span.attributes
