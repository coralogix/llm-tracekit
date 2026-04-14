"""Tests for the LangGraph callback handler."""

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

from uuid import uuid4

import pytest
from opentelemetry.trace import StatusCode

import llm_tracekit.core._extended_gen_ai_attributes as ExtendedGenAIAttributes
from llm_tracekit.langgraph.callback import LangGraphCallbackHandler
from llm_tracekit.langgraph.span_manager import GLOBAL_SPAN_NAME
from llm_tracekit.langgraph.utils import LangGraphSpanAttributes


@pytest.fixture()
def langgraph_metadata() -> dict[str, object]:
    return {
        "langgraph_node": "ingest_messages",
        "langgraph_step": 3,
        "langgraph_triggers": ["start"],
        "langgraph_path": "root.ingest_messages",
        "langgraph_checkpoint_ns": "namespace",
        "thread_id": "thread-42",
        "langgraph_task_id": "task-007",
        "custom": "value",
    }


def _start_node(
    handler: LangGraphCallbackHandler,
    *,
    run_id,
    metadata: dict[str, object],
    tags: list[str] | None = None,
    serialized: dict[str, object] | None = None,
    parent_run_id=None,
) -> None:
    handler.on_chain_start(
        serialized=serialized or {},
        inputs={},
        run_id=run_id,
        parent_run_id=parent_run_id,
        tags=tags,
        metadata=metadata,
    )


def test_on_chain_start_and_end_creates_node_span(
    handler: LangGraphCallbackHandler, langgraph_metadata, span_exporter
):
    """One node start+end produces a node span (and possibly a global span)."""
    run_id = uuid4()
    _start_node(handler, run_id=run_id, metadata=langgraph_metadata)
    handler.on_chain_end(outputs={"result": "ok"}, run_id=run_id)

    spans = span_exporter.get_finished_spans()
    node_spans = [s for s in spans if s.name == "LangGraph Node ingest_messages"]
    assert len(node_spans) == 1


def test_node_span_has_node_name_and_step_attributes(
    handler: LangGraphCallbackHandler, langgraph_metadata, span_exporter
):
    """Node span has gen_ai.langgraph.node and gen_ai.langgraph.step attributes."""
    run_id = uuid4()
    _start_node(handler, run_id=run_id, metadata=langgraph_metadata)
    handler.on_chain_end(outputs={}, run_id=run_id)

    spans = span_exporter.get_finished_spans()
    node_spans = [s for s in spans if s.name == "LangGraph Node ingest_messages"]
    assert len(node_spans) == 1
    span = node_spans[0]
    assert span.attributes.get(LangGraphSpanAttributes.NODE) == "ingest_messages"
    assert span.attributes.get(LangGraphSpanAttributes.STEP) == 1


def test_on_chain_end_marks_success(
    handler: LangGraphCallbackHandler, langgraph_metadata, span_exporter
):
    """Node span is ended without error on on_chain_end (status may be UNSET or OK)."""
    run_id = uuid4()
    _start_node(handler, run_id=run_id, metadata=langgraph_metadata)
    handler.on_chain_end(outputs={"result": "ok"}, run_id=run_id)

    spans = span_exporter.get_finished_spans()
    node_spans = [s for s in spans if s.name.startswith("LangGraph Node ")]
    assert len(node_spans) >= 1
    for span in node_spans:
        assert span.status.status_code in (StatusCode.OK, StatusCode.UNSET)


def test_on_chain_error_sets_error_status(
    handler: LangGraphCallbackHandler, langgraph_metadata, span_exporter
):
    """Node span is marked error on on_chain_error."""
    run_id = uuid4()
    _start_node(handler, run_id=run_id, metadata=langgraph_metadata)
    handler.on_chain_error(ValueError("boom"), run_id=run_id)

    spans = span_exporter.get_finished_spans()
    node_spans = [s for s in spans if s.name.startswith("LangGraph Node ")]
    assert len(node_spans) >= 1
    for span in node_spans:
        assert span.status.status_code is StatusCode.ERROR


def test_first_node_creates_global_span_and_node_span(
    handler: LangGraphCallbackHandler, langgraph_metadata, span_exporter
):
    """When the first node has a parent_run_id, we get global span + node span."""
    root_run_id = uuid4()
    node_run_id = uuid4()
    _start_node(
        handler,
        run_id=node_run_id,
        metadata=langgraph_metadata,
        parent_run_id=root_run_id,
    )
    handler.on_chain_end(outputs={}, run_id=node_run_id)
    handler.on_chain_end(outputs={}, run_id=root_run_id)

    spans = span_exporter.get_finished_spans()
    global_spans = [s for s in spans if s.name == GLOBAL_SPAN_NAME]
    node_spans = [s for s in spans if s.name == "LangGraph Node ingest_messages"]
    assert len(global_spans) == 1
    assert len(node_spans) == 1
    assert node_spans[0].parent.span_id == global_spans[0].get_span_context().span_id


def test_two_nodes_under_same_global_span(
    handler: LangGraphCallbackHandler, langgraph_metadata, span_exporter
):
    """Two nodes with the same parent_run_id are both children of one global span."""
    root_run_id = uuid4()
    node_a_id = uuid4()
    node_b_id = uuid4()

    _start_node(
        handler,
        run_id=node_a_id,
        metadata=langgraph_metadata,
        parent_run_id=root_run_id,
    )
    handler.on_chain_end(outputs={}, run_id=node_a_id)

    _start_node(
        handler,
        run_id=node_b_id,
        metadata={**langgraph_metadata, "langgraph_node": "other"},
        parent_run_id=root_run_id,
    )
    handler.on_chain_end(outputs={}, run_id=node_b_id)
    handler.on_chain_end(outputs={}, run_id=root_run_id)

    spans = span_exporter.get_finished_spans()
    global_spans = [s for s in spans if s.name == GLOBAL_SPAN_NAME]
    node_spans = [s for s in spans if s.name.startswith("LangGraph Node ")]
    assert len(global_spans) == 1
    assert len(node_spans) == 2
    for node_span in node_spans:
        assert node_span.parent.span_id == global_spans[0].get_span_context().span_id
    # Step is 1-based order: first node=1, second=2
    node_spans_sorted = sorted(
        node_spans,
        key=lambda s: s.attributes.get(LangGraphSpanAttributes.STEP),
    )
    assert node_spans_sorted[0].attributes.get(LangGraphSpanAttributes.STEP) == 1
    assert node_spans_sorted[1].attributes.get(LangGraphSpanAttributes.STEP) == 2


def test_path_with_more_than_two_segments_skips_node_span(
    handler: LangGraphCallbackHandler, span_exporter
):
    """Runs with langgraph_path like root.node.conditional do not create a node span.

    Conditional edges (and similar sub-invocations) are reported with the same
    langgraph_node but a longer path; we skip them so we get one span per node execution.
    """
    run_id = uuid4()
    metadata = {
        "langgraph_node": "llm_call",
        "langgraph_path": "root.llm_call.conditional",
    }
    _start_node(handler, run_id=run_id, metadata=metadata)
    handler.on_chain_end(outputs={}, run_id=run_id)

    spans = span_exporter.get_finished_spans()
    node_spans = [s for s in spans if s.name.startswith("LangGraph Node ")]
    assert len(node_spans) == 0


def test_node_span_has_user_from_metadata(
    handler: LangGraphCallbackHandler, langgraph_metadata, span_exporter
):
    """Node span records gen_ai.request.user when metadata contains a 'user' key."""
    run_id = uuid4()
    metadata_with_user = {**langgraph_metadata, "user": "test-user-123"}
    _start_node(handler, run_id=run_id, metadata=metadata_with_user)
    handler.on_chain_end(outputs={}, run_id=run_id)

    spans = span_exporter.get_finished_spans()
    node_spans = [s for s in spans if s.name == "LangGraph Node ingest_messages"]
    assert len(node_spans) == 1
    span = node_spans[0]
    assert (
        span.attributes.get(ExtendedGenAIAttributes.GEN_AI_REQUEST_USER)
        == "test-user-123"
    )


def test_node_span_no_user_attribute_when_missing(
    handler: LangGraphCallbackHandler, langgraph_metadata, span_exporter
):
    """Node span has no gen_ai.request.user when metadata contains no 'user' key."""
    run_id = uuid4()
    _start_node(handler, run_id=run_id, metadata=langgraph_metadata)
    handler.on_chain_end(outputs={}, run_id=run_id)

    spans = span_exporter.get_finished_spans()
    node_spans = [s for s in spans if s.name == "LangGraph Node ingest_messages"]
    assert len(node_spans) == 1
    span = node_spans[0]
    assert ExtendedGenAIAttributes.GEN_AI_REQUEST_USER not in (span.attributes or {})
