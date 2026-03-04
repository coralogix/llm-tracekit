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
from opentelemetry.trace import StatusCode

from llm_tracekit.langgraph.callback import LangGraphCallbackHandler
from llm_tracekit.langgraph.span_manager import GLOBAL_SPAN_NAME


def _node_a(state: dict) -> dict:
    return {"value": state.get("value", 0) + 1}


def _node_b(state: dict) -> dict:
    return {"value": state.get("value", 0) + 10}


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


def test_invoke_produces_global_span_and_node_spans(
    compiled_graph,
    handler: LangGraphCallbackHandler,
    span_exporter,
):
    """Invoking a StateGraph produces one global span and one span per node."""
    config = {
        "callbacks": [handler],
        "configurable": {"thread_id": "integration-test"},
    }
    result = compiled_graph.invoke({"value": 0}, config=config)

    assert result["value"] == 11

    spans = span_exporter.get_finished_spans()
    global_spans = [s for s in spans if s.name == GLOBAL_SPAN_NAME]
    node_spans = [s for s in spans if s.name.startswith("LangGraph Node ")]

    assert len(global_spans) >= 1
    assert len(node_spans) >= 2

    names = [s.name for s in node_spans]
    assert "LangGraph Node a" in names
    assert "LangGraph Node b" in names

    for span in node_spans:
        assert span.status.status_code in (StatusCode.OK, StatusCode.UNSET)


def test_node_spans_are_children_of_global_span(
    compiled_graph,
    handler: LangGraphCallbackHandler,
    span_exporter,
):
    """Node spans are children of the global (START→END) span."""
    config = {
        "callbacks": [handler],
        "configurable": {"thread_id": "parent-test"},
    }
    compiled_graph.invoke({"value": 0}, config=config)

    spans = span_exporter.get_finished_spans()
    global_spans = [s for s in spans if s.name == GLOBAL_SPAN_NAME]
    node_spans = [s for s in spans if s.name.startswith("LangGraph Node ")]

    assert len(global_spans) == 1
    assert len(node_spans) >= 2
    global_ctx = global_spans[0].get_span_context()
    for node_span in node_spans:
        assert node_span.parent.span_id == global_ctx.span_id


def test_instrument_produces_same_structure(
    compiled_graph,
    instrument,
    span_exporter,
):
    """With instrumentor (no explicit handler), we still get global + node spans."""
    config = {"configurable": {"thread_id": "instrument-test"}}
    compiled_graph.invoke({"value": 0}, config=config)

    spans = span_exporter.get_finished_spans()
    global_spans = [s for s in spans if s.name == GLOBAL_SPAN_NAME]
    node_spans = [s for s in spans if s.name.startswith("LangGraph Node ")]

    assert len(global_spans) >= 1
    assert len(node_spans) >= 2
