"""Integration tests for LangGraph instrumentation with a real StateGraph."""

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

from __future__ import annotations

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from opentelemetry.semconv._incubating.metrics import gen_ai_metrics  # type: ignore[attr-defined]
from opentelemetry.trace import StatusCode

import llm_tracekit.core._extended_gen_ai_attributes as ExtendedGenAIAttributes
from llm_tracekit.langgraph.callback import LangGraphCallbackHandler
from llm_tracekit.langgraph.utils import LangGraphSpanAttributes


def _node_a(state: dict) -> dict:
    return {"value": state.get("value", 0) + 1}


def _node_b(state: dict) -> dict:
    return {"value": state.get("value", 0) + 10}


def _node_with_messages(state: dict) -> dict:
    messages = list(state.get("messages", []))
    messages.append({"role": "assistant", "content": "echo"})
    return {"messages": messages}


@pytest.fixture
def compiled_graph():
    """Build a minimal two-node graph: START -> a -> b -> END."""
    graph = StateGraph(dict)
    graph.add_node("a", _node_a)
    graph.add_node("b", _node_b)
    graph.add_edge(START, "a")
    graph.add_edge("a", "b")
    graph.add_edge("b", END)
    return graph.compile(checkpointer=MemorySaver())


@pytest.fixture
def compiled_messages_graph():
    """Build a one-node graph that passes messages for content capture tests."""
    graph = StateGraph(dict)
    graph.add_node("n", _node_with_messages)
    graph.add_edge(START, "n")
    graph.add_edge("n", END)
    return graph.compile(checkpointer=MemorySaver())


def test_invoke_produces_spans_per_node(
    compiled_graph,
    handler: LangGraphCallbackHandler,
    span_exporter,
):
    """Invoking a StateGraph with our handler produces one span per node."""
    config = {
        "callbacks": [handler],
        "configurable": {"thread_id": "integration-test"},
    }
    result = compiled_graph.invoke({"value": 0}, config=config)

    assert result["value"] == 11

    spans = span_exporter.get_finished_spans()
    assert len(spans) >= 2

    names = [s.name for s in spans]
    assert "LangGraph Node a" in names
    assert "LangGraph Node b" in names

    for span in spans:
        assert span.status.status_code is StatusCode.OK
        assert span.attributes.get(LangGraphSpanAttributes.STATUS) == "success"


def test_invoke_node_attributes(
    compiled_graph,
    handler: LangGraphCallbackHandler,
    span_exporter,
):
    """Spans include expected LangGraph attributes when present in metadata."""
    config = {
        "callbacks": [handler],
        "configurable": {"thread_id": "attr-test"},
    }
    compiled_graph.invoke({"value": 0}, config=config)

    spans = span_exporter.get_finished_spans()
    node_spans = [s for s in spans if s.name.startswith("LangGraph Node ")]
    assert len(node_spans) >= 2

    for span in node_spans:
        assert LangGraphSpanAttributes.NODE in span.attributes
        assert span.attributes.get(LangGraphSpanAttributes.STATUS) == "success"


def test_instrument_with_content_captures_prompt_and_completion(
    compiled_messages_graph,
    instrument_with_content,
    span_exporter,
):
    """With content capture on, node spans include gen_ai.prompt.* and gen_ai.completion.*."""
    config = {"configurable": {"thread_id": "content-on"}}
    compiled_messages_graph.invoke(
        {"messages": [{"role": "user", "content": "hello"}]},
        config=config,
    )

    spans = span_exporter.get_finished_spans()
    node_spans = [s for s in spans if s.name.startswith("LangGraph Node ")]
    assert len(node_spans) >= 1

    prompt_content_key = ExtendedGenAIAttributes.GEN_AI_PROMPT_CONTENT.format(
        prompt_index=0
    )
    completion_content_key = ExtendedGenAIAttributes.GEN_AI_COMPLETION_CONTENT.format(
        completion_index=0
    )
    found_prompt = any(prompt_content_key in s.attributes for s in node_spans)
    found_completion = any(completion_content_key in s.attributes for s in node_spans)
    assert found_prompt, f"Expected at least one span with {prompt_content_key}"
    assert found_completion, f"Expected at least one span with {completion_content_key}"


def test_instrument_no_content_omits_prompt_and_completion(
    compiled_messages_graph,
    instrument_no_content,
    span_exporter,
):
    """With content capture off, node spans do not include prompt/completion content."""
    config = {"configurable": {"thread_id": "content-off"}}
    compiled_messages_graph.invoke(
        {"messages": [{"role": "user", "content": "secret"}]},
        config=config,
    )

    spans = span_exporter.get_finished_spans()
    for span in spans:
        attrs = span.attributes or {}
        for key in attrs:
            if ".content" in key and (
                key.startswith("gen_ai.prompt.") or key.startswith("gen_ai.completion.")
            ):
                pytest.fail(
                    f"Content capture should be off but span has content attribute: {key}"
                )


def test_node_duration_metric_recorded(
    compiled_graph,
    instrument_no_content,
    metric_reader,
):
    """Invoking a graph records at least one operation duration metric."""
    config = {"configurable": {"thread_id": "metrics-test"}}
    compiled_graph.invoke({"value": 0}, config=config)

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) >= 1

    scope_metrics_list = [rm.scope_metrics for rm in metrics]
    all_metrics = []
    for sm_list in scope_metrics_list:
        for sm in sm_list:
            all_metrics.extend(sm.metrics)

    duration_metric = next(
        (
            m
            for m in all_metrics
            if m.name == gen_ai_metrics.GEN_AI_CLIENT_OPERATION_DURATION
        ),
        None,
    )
    assert duration_metric is not None
    assert len(duration_metric.data.data_points) >= 1
    assert duration_metric.data.data_points[0].sum >= 0
