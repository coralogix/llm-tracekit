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

"""Span lifecycle helpers for LangGraph instrumentation.

Provides a 3-level structure: global span (START→END), node spans (children of
global), and LLM spans (children of node spans, created by other instrumentors).
Node spans are attached to the current context so LLM calls inside a node become
children of that node span.
"""

from __future__ import annotations

from contextvars import Token
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from opentelemetry import context
from opentelemetry.trace import Span, SpanKind, Tracer, set_span_in_context


GLOBAL_SPAN_NAME = "LangGraph"


@dataclass
class _GlobalSpanState:
    span: Span
    token: Token[Any]
    root_run_id: UUID


@dataclass
class _NodeSpanState:
    span: Span
    token: Token[Any]


class LangGraphSpanManager:
    """Tracks global (graph) and node spans for LangGraph runs.

    Global span: one per graph invocation, created on the first node and reused
    for all nodes in that run. Ended when the root run ends. Node spans: one
    per node, child of the single global span.
    """

    def __init__(self, tracer: Tracer) -> None:
        self._tracer = tracer
        self._node_states: dict[UUID, _NodeSpanState] = {}
        self._global_span_state: _GlobalSpanState | None = None
        self._node_execution_counter = 0

    def ensure_global_span_and_create_node_span(
        self,
        *,
        run_id: UUID,
        parent_run_id: UUID | None,
        span_name: str,
    ) -> None:
        """Ensure a global span exists for this graph run, then create a node span as its child.

        Only one global span exists per graph invocation (created on first node).
        The node span is attached to the current context so LLM calls are children of it.
        """
        if self._global_span_state is None and parent_run_id is not None:
            global_span = self._tracer.start_span(
                name=GLOBAL_SPAN_NAME,
                kind=SpanKind.INTERNAL,
            )
            ctx = set_span_in_context(global_span)
            token = context.attach(ctx)
            self._global_span_state = _GlobalSpanState(
                span=global_span,
                token=token,
                root_run_id=parent_run_id,
            )

        parent_ctx = None
        if self._global_span_state is not None:
            parent_ctx = set_span_in_context(self._global_span_state.span)

        node_span = self._tracer.start_span(
            name=span_name,
            kind=SpanKind.INTERNAL,
            context=parent_ctx,
        )
        ctx = set_span_in_context(node_span)
        token = context.attach(ctx)
        self._node_states[run_id] = _NodeSpanState(span=node_span, token=token)
        self._node_execution_counter += 1

    def node_execution_index(self) -> int:
        """Return the 1-based execution index of the node span just created in this graph run."""
        return self._node_execution_counter

    def has_node_run(self, run_id: UUID) -> bool:
        """Return True if we have an active node span for this run_id.

        Used to skip sub-runs (e.g. conditional edges) whose parent is a node
        we already spanned, so we get one span per node execution.
        """
        return run_id in self._node_states

    def pop_node_state(self, run_id: UUID) -> _NodeSpanState | None:
        """Remove and return node state for run_id. Caller must detach token and end span."""
        return self._node_states.pop(run_id, None)

    def end_global_span(self, root_run_id: UUID) -> bool:
        """End the global span only if run_id is the root run we stored. Return True if ended."""
        if (
            self._global_span_state is None
            or self._global_span_state.root_run_id != root_run_id
        ):
            return False
        state = self._global_span_state
        self._global_span_state = None
        self._node_execution_counter = 0
        try:
            context.detach(state.token)
        finally:
            if state.span.is_recording():
                state.span.end()
        return True
