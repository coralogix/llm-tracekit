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

import llm_tracekit.core._extended_gen_ai_attributes as ExtendedGenAIAttributes
import pytest
from opentelemetry.trace import StatusCode

from llm_tracekit.langgraph.callback import LangGraphCallbackHandler
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


def _make_tool_definition():
    return [
        {
            "type": "function",
            "function": {
                "name": "search_documents",
                "description": "Search knowledge base",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
            },
        }
    ]


def _start_node(
    handler: LangGraphCallbackHandler,
    *,
    run_id,
    metadata: dict[str, object],
    tags: list[str] | None = None,
    serialized: dict[str, object] | None = None,
) -> None:
    handler.on_chain_start(
        serialized=serialized or {},
        inputs={},
        run_id=run_id,
        parent_run_id=None,
        tags=tags,
        metadata=metadata,
    )


def test_on_chain_start_populates_span_state(
    handler: LangGraphCallbackHandler, langgraph_metadata
):
    run_id = uuid4()
    tags = ["alpha"]
    serialized = {"tools": _make_tool_definition()}

    _start_node(
        handler,
        run_id=run_id,
        metadata=langgraph_metadata,
        tags=tags,
        serialized=serialized,
    )

    state = handler._span_manager.get_state(run_id)  # noqa: SLF001
    assert state is not None
    assert getattr(state.span, "name", None) == "LangGraph Node ingest_messages"
    assert state.attributes[LangGraphSpanAttributes.NODE] == "ingest_messages"
    assert state.attributes[LangGraphSpanAttributes.STEP] == 3
    assert state.attributes[LangGraphSpanAttributes.THREAD_ID] == "thread-42"
    assert state.attributes["langgraph.metadata.custom"] == "value"
    assert state.attributes[LangGraphSpanAttributes.TAGS] == tags

    tool_name_attr = ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_NAME.format(
        tool_index=0
    )
    assert state.attributes[tool_name_attr] == "search_documents"


def test_on_chain_end_marks_success(
    handler: LangGraphCallbackHandler, langgraph_metadata, span_exporter
):
    run_id = uuid4()
    _start_node(handler, run_id=run_id, metadata=langgraph_metadata)

    handler.on_chain_end(outputs={"result": "ok"}, run_id=run_id)

    finished_spans = span_exporter.get_finished_spans()
    assert len(finished_spans) == 1
    span = finished_spans[0]
    assert span.status.status_code is StatusCode.OK
    assert span.attributes[LangGraphSpanAttributes.STATUS] == "success"


def test_on_chain_error_sets_error_status(
    handler: LangGraphCallbackHandler, langgraph_metadata, span_exporter
):
    run_id = uuid4()
    _start_node(handler, run_id=run_id, metadata=langgraph_metadata)

    handler.on_chain_error(ValueError("boom"), run_id=run_id)

    finished_spans = span_exporter.get_finished_spans()
    assert len(finished_spans) == 1
    span = finished_spans[0]
    assert span.status.status_code is StatusCode.ERROR
    assert span.attributes[LangGraphSpanAttributes.STATUS] == "error"


def test_child_node_links_to_parent(
    handler: LangGraphCallbackHandler, langgraph_metadata, span_exporter
):
    parent_run = uuid4()
    child_run = uuid4()

    _start_node(handler, run_id=parent_run, metadata=langgraph_metadata)
    handler.on_chain_start(
        serialized={},
        inputs={},
        run_id=child_run,
        parent_run_id=parent_run,
        tags=None,
        metadata={**langgraph_metadata, "langgraph_node": "child"},
    )

    handler.on_chain_end(outputs={}, run_id=child_run)
    handler.on_chain_end(outputs={}, run_id=parent_run)

    finished_spans = span_exporter.get_finished_spans()
    assert len(finished_spans) == 2
    parent_span = next(
        span for span in finished_spans if span.name == "LangGraph Node ingest_messages"
    )
    child_span = next(
        span for span in finished_spans if span.name == "LangGraph Node child"
    )
    assert child_span.parent.span_id == parent_span.get_span_context().span_id
