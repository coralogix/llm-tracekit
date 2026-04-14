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

"""LangGraph callback handler: span structure and node attributes.

Creates a 3-level hierarchy: one global span per graph run (START→END), one span
per node as child of the global span, and LLM spans from other instrumentors
appear as children of the node span. Node spans get attributes: node name and
step number.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler  # type: ignore
from opentelemetry import context, trace
from opentelemetry.trace import Tracer

from llm_tracekit.core import handle_span_exception
from llm_tracekit.core import _extended_gen_ai_attributes as ExtendedGenAIAttributes
from llm_tracekit.langgraph.span_manager import LangGraphSpanManager
from llm_tracekit.langgraph.utils import (
    LangGraphSpanAttributes,
    build_node_span_name,
    extract_node_attributes,
)


class LangGraphCallbackHandler(BaseCallbackHandler):  # type: ignore[misc]
    """Creates OpenTelemetry spans for LangGraph: global span (START→END) and node spans.

    Only creates spans when chain metadata contains \"langgraph_node\". Node spans
    get two attributes: gen_ai.langgraph.node (node name) and gen_ai.langgraph.step
    (step number, when present). Use with LangChain/OpenAI/etc. instrumentors for
    LLM-level spans (which will appear as children of the node span).
    """

    def __init__(self, tracer: Tracer) -> None:  # type: ignore[override]
        super().__init__()  # type: ignore
        self._span_manager = LangGraphSpanManager(tracer)

    def on_chain_start(  # type: ignore[override]
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        node_info = extract_node_attributes(metadata)
        if node_info is None:
            return None

        # Skip sub-runs whose parent is a node we already created a span for
        # (e.g. conditional edge runs). We want one span per node execution.
        if parent_run_id is not None and self._span_manager.has_node_run(parent_run_id):
            return None

        node_name, attrs = node_info
        span_name = build_node_span_name(node_name)
        self._span_manager.ensure_global_span_and_create_node_span(
            run_id=run_id,
            parent_run_id=parent_run_id,
            span_name=span_name,
        )
        # Set node name and step number on the current (node) span
        current_span = trace.get_current_span()
        if current_span.is_recording():
            if LangGraphSpanAttributes.NODE in attrs:
                current_span.set_attribute(
                    LangGraphSpanAttributes.NODE, attrs[LangGraphSpanAttributes.NODE]
                )
            current_span.set_attribute(
                LangGraphSpanAttributes.STEP,
                self._span_manager.node_execution_index(),
            )
            user = (metadata or {}).get("user")
            if user is None:
                configurable = (kwargs.get("config") or {}).get("configurable") or {}
                user = configurable.get("user") or configurable.get("user_id")
            if user is not None:
                current_span.set_attribute(
                    ExtendedGenAIAttributes.GEN_AI_REQUEST_USER, str(user)
                )
        return None

    def on_chain_end(  # type: ignore[override]
        self,
        outputs: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> Any:
        state = self._span_manager.pop_node_state(run_id)
        if state is not None:
            try:
                context.detach(state.token)
            finally:
                if state.span.is_recording():
                    state.span.end()

        self._span_manager.end_global_span(run_id)
        return None

    def on_chain_error(  # type: ignore[override]
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> Any:
        state = self._span_manager.pop_node_state(run_id)
        if state is not None:
            try:
                handle_span_exception(state.span, error)
            finally:
                try:
                    context.detach(state.token)
                finally:
                    if state.span.is_recording():
                        state.span.end()

        self._span_manager.end_global_span(run_id)
        return None
