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

"""Tests for US1: Basic Agent Tracing."""

import pytest
from unittest.mock import MagicMock, patch

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.trace import SpanKind, StatusCode
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

from llm_tracekit.strands_agents.hook_provider import StrandsHookProvider
from strands.hooks.events import (
    BeforeInvocationEvent,
    AfterInvocationEvent,
    BeforeModelCallEvent,
    AfterModelCallEvent,
    BeforeToolCallEvent,
    AfterToolCallEvent,
)

from utils import (
    find_span_by_name_prefix,
    find_spans_by_name_prefix,
    get_child_spans,
    assert_span_attributes,
)


@pytest.fixture
def hook_provider(tracer_provider, meter_provider):
    from opentelemetry.trace import get_tracer
    from opentelemetry.metrics import get_meter
    from llm_tracekit.core._metrics import Instruments

    tracer = get_tracer("test", tracer_provider=tracer_provider)
    meter = get_meter("test", meter_provider=meter_provider)
    instruments = Instruments(meter)
    return StrandsHookProvider(tracer=tracer, instruments=instruments, capture_content=False)


def _make_mock_agent(name="TestAgent", model_id="anthropic.claude-sonnet-4-20250514", tools=None):
    agent = MagicMock()
    agent.name = name
    agent.model = MagicMock()
    agent.model.model_id = model_id
    agent.tool_registry = MagicMock()
    if tools:
        agent.tool_registry.registry = {t: MagicMock() for t in tools}
    else:
        agent.tool_registry.registry = {}
    agent.tool_registry.get_all_tools_config = None
    return agent


def _make_invocation_state(cycle_id="cycle-1", model_id="anthropic.claude-sonnet-4-20250514"):
    state = MagicMock()
    state.cycle_id = cycle_id
    state.model_id = model_id
    state.messages = []
    return state


def _make_stop_response(
    input_tokens=100,
    output_tokens=50,
    stop_reason="end_turn",
    model=None,
    cache_read=None,
    cache_write=None,
):
    resp = MagicMock()
    usage = {"inputTokens": input_tokens, "outputTokens": output_tokens}
    if cache_read is not None:
        usage["cacheReadInputTokens"] = cache_read
    if cache_write is not None:
        usage["cacheWriteInputTokens"] = cache_write
    resp.metrics = {"usage": usage}
    resp.stop_reason = stop_reason
    resp.model = model
    resp.message = {"role": "assistant", "content": [{"text": "Hello!"}]}
    return resp


def _simulate_simple_agent_call(hook_provider, agent=None, tools=None):
    """Simulate: agent invocation → 1 cycle → 1 model call → optional tool calls."""
    if agent is None:
        agent = _make_mock_agent(tools=list(tools.keys()) if tools else None)

    inv_state = _make_invocation_state()

    hook_provider._before_invocation(
        BeforeInvocationEvent(agent=agent, invocation_state=inv_state, messages=[]),
        agent=agent,
    )
    hook_provider._before_model_call(
        BeforeModelCallEvent(agent=agent, invocation_state=inv_state),
        agent=agent,
    )
    stop_resp = _make_stop_response()
    hook_provider._after_model_call(
        AfterModelCallEvent(
            agent=agent, invocation_state=inv_state,
            stop_response=stop_resp, exception=None, retry=False,
        ),
        agent=agent,
    )

    if tools:
        for tool_name, tool_result in tools.items():
            tool_use = {"name": tool_name, "toolUseId": f"tu-{tool_name}", "input": {"query": "test"}}
            selected_tool = MagicMock()
            selected_tool.is_mcp = False
            hook_provider._before_tool_call(
                BeforeToolCallEvent(
                    agent=agent, selected_tool=selected_tool,
                    tool_use=tool_use, invocation_state=inv_state, cancel_tool=False,
                ),
                agent=agent,
            )
            hook_provider._after_tool_call(
                AfterToolCallEvent(
                    agent=agent, selected_tool=selected_tool,
                    tool_use=tool_use, invocation_state=inv_state,
                    result=tool_result, exception=None,
                    cancel_message=None, retry=False,
                ),
                agent=agent,
            )

    result = MagicMock()
    hook_provider._after_invocation(
        AfterInvocationEvent(agent=agent, invocation_state=inv_state, result=result),
        agent=agent,
    )


class TestAgentSpan:
    def test_agent_span_created(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        span = find_span_by_name_prefix(span_exporter, "invoke_agent")
        assert span is not None
        assert span.name == "invoke_agent TestAgent"

    def test_agent_span_attributes(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        span = find_span_by_name_prefix(span_exporter, "invoke_agent")
        assert span is not None
        assert span.attributes[GenAIAttributes.GEN_AI_SYSTEM] == "strands"
        assert span.attributes[GenAIAttributes.GEN_AI_OPERATION_NAME] == "invoke_agent"
        assert span.attributes[GenAIAttributes.GEN_AI_AGENT_NAME] == "TestAgent"

    def test_agent_span_kind_internal(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        span = find_span_by_name_prefix(span_exporter, "invoke_agent")
        assert span is not None
        assert span.kind == SpanKind.INTERNAL

    def test_agent_span_aggregated_tokens(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        span = find_span_by_name_prefix(span_exporter, "invoke_agent")
        assert span is not None
        assert span.attributes[GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS] == 100
        assert span.attributes[GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS] == 50

    def test_agent_span_tools_list(self, hook_provider, span_exporter: InMemorySpanExporter):
        agent = _make_mock_agent(tools=["get_weather", "calculator"])
        _simulate_simple_agent_call(hook_provider, agent=agent)
        span = find_span_by_name_prefix(span_exporter, "invoke_agent")
        assert span is not None
        tools_attr = span.attributes.get("gen_ai.agent.tools")
        assert tools_attr is not None
        assert "get_weather" in tools_attr
        assert "calculator" in tools_attr


class TestCycleSpan:
    def test_cycle_span_created(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        span = find_span_by_name_prefix(span_exporter, "cycle")
        assert span is not None
        assert span.name == "cycle cycle-1"

    def test_cycle_span_attributes(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        span = find_span_by_name_prefix(span_exporter, "cycle")
        assert span is not None
        assert span.attributes["strands.agent.cycle.id"] == "cycle-1"

    def test_cycle_span_kind_internal(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        span = find_span_by_name_prefix(span_exporter, "cycle")
        assert span is not None
        assert span.kind == SpanKind.INTERNAL

    def test_cycle_is_child_of_agent(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        agent_span = find_span_by_name_prefix(span_exporter, "invoke_agent")
        cycle_span = find_span_by_name_prefix(span_exporter, "cycle")
        assert agent_span is not None
        assert cycle_span is not None
        assert cycle_span.parent is not None
        assert cycle_span.parent.span_id == agent_span.context.span_id


class TestModelSpan:
    def test_model_span_created(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        span = find_span_by_name_prefix(span_exporter, "chat")
        assert span is not None

    def test_model_span_attributes(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        span = find_span_by_name_prefix(span_exporter, "chat")
        assert span is not None
        assert_span_attributes(span, system="strands", operation_name="chat")
        assert span.attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL] == "anthropic.claude-sonnet-4-20250514"

    def test_model_span_kind_client(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        span = find_span_by_name_prefix(span_exporter, "chat")
        assert span is not None
        assert span.kind == SpanKind.CLIENT

    def test_model_span_token_usage(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        span = find_span_by_name_prefix(span_exporter, "chat")
        assert span is not None
        assert span.attributes[GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS] == 100
        assert span.attributes[GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS] == 50

    def test_model_span_finish_reason(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        span = find_span_by_name_prefix(span_exporter, "chat")
        assert span is not None
        assert span.attributes[GenAIAttributes.GEN_AI_RESPONSE_FINISH_REASONS] == ("end_turn",)

    def test_model_span_cache_tokens(self, hook_provider, span_exporter: InMemorySpanExporter):
        agent = _make_mock_agent()
        inv_state = _make_invocation_state()

        hook_provider._before_invocation(
            BeforeInvocationEvent(agent=agent, invocation_state=inv_state, messages=[]),
            agent=agent,
        )
        hook_provider._before_model_call(
            BeforeModelCallEvent(agent=agent, invocation_state=inv_state), agent=agent,
        )
        stop_resp = _make_stop_response(cache_read=200, cache_write=50)
        hook_provider._after_model_call(
            AfterModelCallEvent(
                agent=agent, invocation_state=inv_state,
                stop_response=stop_resp, exception=None, retry=False,
            ),
            agent=agent,
        )
        result = MagicMock()
        hook_provider._after_invocation(
            AfterInvocationEvent(agent=agent, invocation_state=inv_state, result=result),
            agent=agent,
        )

        span = find_span_by_name_prefix(span_exporter, "chat")
        assert span is not None
        assert span.attributes["gen_ai.usage.cache_read_input_tokens"] == 200
        assert span.attributes["gen_ai.usage.cache_write_input_tokens"] == 50

    def test_model_span_is_child_of_cycle(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        cycle_span = find_span_by_name_prefix(span_exporter, "cycle")
        model_span = find_span_by_name_prefix(span_exporter, "chat")
        assert cycle_span is not None
        assert model_span is not None
        assert model_span.parent is not None
        assert model_span.parent.span_id == cycle_span.context.span_id


class TestToolSpan:
    def test_tool_span_created(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(
            hook_provider, tools={"get_weather": {"status": "success", "content": [{"text": "sunny"}]}}
        )
        span = find_span_by_name_prefix(span_exporter, "execute_tool")
        assert span is not None
        assert span.name == "execute_tool get_weather"

    def test_tool_span_attributes(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(
            hook_provider, tools={"get_weather": {"status": "success", "content": []}}
        )
        span = find_span_by_name_prefix(span_exporter, "execute_tool")
        assert span is not None
        assert span.attributes[GenAIAttributes.GEN_AI_SYSTEM] == "strands"
        assert span.attributes[GenAIAttributes.GEN_AI_OPERATION_NAME] == "execute_tool"
        assert span.attributes["name"] == "get_weather"
        assert span.attributes["type"] == "function"
        assert span.attributes["gen_ai.tool.call.id"] == "tu-get_weather"
        assert span.attributes["gen_ai.tool.status"] == "success"

    def test_tool_span_kind_internal(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(
            hook_provider, tools={"get_weather": {"status": "success", "content": []}}
        )
        span = find_span_by_name_prefix(span_exporter, "execute_tool")
        assert span is not None
        assert span.kind == SpanKind.INTERNAL

    def test_tool_span_is_child_of_cycle(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(
            hook_provider, tools={"get_weather": {"status": "success", "content": []}}
        )
        cycle_span = find_span_by_name_prefix(span_exporter, "cycle")
        tool_span = find_span_by_name_prefix(span_exporter, "execute_tool")
        assert cycle_span is not None
        assert tool_span is not None
        assert tool_span.parent is not None
        assert tool_span.parent.span_id == cycle_span.context.span_id


class TestAgentNoTools:
    def test_no_tool_spans_when_no_tools(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        tool_spans = find_spans_by_name_prefix(span_exporter, "execute_tool")
        assert len(tool_spans) == 0

    def test_agent_and_model_spans_exist(self, hook_provider, span_exporter: InMemorySpanExporter):
        _simulate_simple_agent_call(hook_provider)
        assert find_span_by_name_prefix(span_exporter, "invoke_agent") is not None
        assert find_span_by_name_prefix(span_exporter, "cycle") is not None
        assert find_span_by_name_prefix(span_exporter, "chat") is not None


class TestMultiCycle:
    def test_multiple_cycles_create_separate_spans(self, hook_provider, span_exporter: InMemorySpanExporter):
        agent = _make_mock_agent()

        inv_state_c1 = _make_invocation_state(cycle_id="cycle-1")
        inv_state_c2 = _make_invocation_state(cycle_id="cycle-2")

        hook_provider._before_invocation(
            BeforeInvocationEvent(agent=agent, invocation_state=inv_state_c1, messages=[]),
            agent=agent,
        )

        # Cycle 1
        hook_provider._before_model_call(
            BeforeModelCallEvent(agent=agent, invocation_state=inv_state_c1), agent=agent,
        )
        hook_provider._after_model_call(
            AfterModelCallEvent(
                agent=agent, invocation_state=inv_state_c1,
                stop_response=_make_stop_response(), exception=None, retry=False,
            ),
            agent=agent,
        )

        # Cycle 2 (different cycle_id triggers new cycle span)
        hook_provider._before_model_call(
            BeforeModelCallEvent(agent=agent, invocation_state=inv_state_c2), agent=agent,
        )
        hook_provider._after_model_call(
            AfterModelCallEvent(
                agent=agent, invocation_state=inv_state_c2,
                stop_response=_make_stop_response(input_tokens=50, output_tokens=25),
                exception=None, retry=False,
            ),
            agent=agent,
        )

        result = MagicMock()
        hook_provider._after_invocation(
            AfterInvocationEvent(agent=agent, invocation_state=inv_state_c2, result=result),
            agent=agent,
        )

        cycle_spans = find_spans_by_name_prefix(span_exporter, "cycle")
        assert len(cycle_spans) == 2
        cycle_ids = {s.attributes["strands.agent.cycle.id"] for s in cycle_spans}
        assert cycle_ids == {"cycle-1", "cycle-2"}

    def test_multi_cycle_aggregated_tokens(self, hook_provider, span_exporter: InMemorySpanExporter):
        agent = _make_mock_agent()
        inv_state_c1 = _make_invocation_state(cycle_id="cycle-1")
        inv_state_c2 = _make_invocation_state(cycle_id="cycle-2")

        hook_provider._before_invocation(
            BeforeInvocationEvent(agent=agent, invocation_state=inv_state_c1, messages=[]),
            agent=agent,
        )
        hook_provider._before_model_call(
            BeforeModelCallEvent(agent=agent, invocation_state=inv_state_c1), agent=agent,
        )
        hook_provider._after_model_call(
            AfterModelCallEvent(
                agent=agent, invocation_state=inv_state_c1,
                stop_response=_make_stop_response(input_tokens=100, output_tokens=50),
                exception=None, retry=False,
            ),
            agent=agent,
        )
        hook_provider._before_model_call(
            BeforeModelCallEvent(agent=agent, invocation_state=inv_state_c2), agent=agent,
        )
        hook_provider._after_model_call(
            AfterModelCallEvent(
                agent=agent, invocation_state=inv_state_c2,
                stop_response=_make_stop_response(input_tokens=200, output_tokens=100),
                exception=None, retry=False,
            ),
            agent=agent,
        )
        result = MagicMock()
        hook_provider._after_invocation(
            AfterInvocationEvent(agent=agent, invocation_state=inv_state_c2, result=result),
            agent=agent,
        )

        agent_span = find_span_by_name_prefix(span_exporter, "invoke_agent")
        assert agent_span is not None
        assert agent_span.attributes[GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS] == 300
        assert agent_span.attributes[GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS] == 150


class TestErrorHandling:
    def test_model_error_sets_span_status(self, hook_provider, span_exporter: InMemorySpanExporter):
        agent = _make_mock_agent()
        inv_state = _make_invocation_state()

        hook_provider._before_invocation(
            BeforeInvocationEvent(agent=agent, invocation_state=inv_state, messages=[]),
            agent=agent,
        )
        hook_provider._before_model_call(
            BeforeModelCallEvent(agent=agent, invocation_state=inv_state), agent=agent,
        )

        error = RuntimeError("Model rate limit exceeded")
        hook_provider._after_model_call(
            AfterModelCallEvent(
                agent=agent, invocation_state=inv_state,
                stop_response=None, exception=error, retry=False,
            ),
            agent=agent,
        )

        result = MagicMock()
        hook_provider._after_invocation(
            AfterInvocationEvent(agent=agent, invocation_state=inv_state, result=result),
            agent=agent,
        )

        model_span = find_span_by_name_prefix(span_exporter, "chat")
        assert model_span is not None
        assert model_span.status.status_code == StatusCode.ERROR

    def test_tool_error_sets_span_status(self, hook_provider, span_exporter: InMemorySpanExporter):
        agent = _make_mock_agent()
        inv_state = _make_invocation_state()

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
                stop_response=_make_stop_response(), exception=None, retry=False,
            ),
            agent=agent,
        )

        tool_use = {"name": "failing_tool", "toolUseId": "tu-fail", "input": {}}
        selected_tool = MagicMock()
        selected_tool.is_mcp = False
        hook_provider._before_tool_call(
            BeforeToolCallEvent(
                agent=agent, selected_tool=selected_tool,
                tool_use=tool_use, invocation_state=inv_state, cancel_tool=False,
            ),
            agent=agent,
        )

        error = ValueError("Tool execution failed")
        hook_provider._after_tool_call(
            AfterToolCallEvent(
                agent=agent, selected_tool=selected_tool,
                tool_use=tool_use, invocation_state=inv_state,
                result=None, exception=error,
                cancel_message=None, retry=False,
            ),
            agent=agent,
        )

        result = MagicMock()
        hook_provider._after_invocation(
            AfterInvocationEvent(agent=agent, invocation_state=inv_state, result=result),
            agent=agent,
        )

        tool_span = find_span_by_name_prefix(span_exporter, "execute_tool")
        assert tool_span is not None
        assert tool_span.status.status_code == StatusCode.ERROR


class TestMetrics:
    def test_operation_duration_recorded(self, hook_provider, metric_reader: InMemoryMetricReader):
        _simulate_simple_agent_call(hook_provider)
        metrics_data = metric_reader.get_metrics_data()
        duration_found = False
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name == "gen_ai.client.operation.duration":
                        duration_found = True
        assert duration_found, "gen_ai.client.operation.duration metric not found"

    def test_token_usage_recorded(self, hook_provider, metric_reader: InMemoryMetricReader):
        _simulate_simple_agent_call(hook_provider)
        metrics_data = metric_reader.get_metrics_data()
        token_found = False
        for resource_metrics in metrics_data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name == "gen_ai.client.token.usage":
                        token_found = True
        assert token_found, "gen_ai.client.token.usage metric not found"
