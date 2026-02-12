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

"""Span lifecycle helpers for LangGraph instrumentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from timeit import default_timer
from typing import Any
from uuid import UUID

from opentelemetry.trace import Span, SpanKind, Tracer, set_span_in_context


@dataclass
class LangGraphNodeSpanState:
    """Book-keeping for an in-flight LangGraph node span."""

    span: Span
    attributes: dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=default_timer)
    node_name: str | None = None


class LangGraphSpanManager:
    """Tracks spans created for LangGraph node executions."""

    def __init__(self, tracer: Tracer) -> None:
        self._tracer = tracer
        self._states: dict[UUID, LangGraphNodeSpanState] = {}

    def create_node_span(
        self,
        *,
        run_id: UUID,
        parent_run_id: UUID | None,
        span_name: str,
        attributes: dict[str, Any],
        node_name: str | None = None,
    ) -> LangGraphNodeSpanState:
        """Create and register a new span for a LangGraph node."""

        context = None
        if parent_run_id is not None:
            parent_state = self._states.get(parent_run_id)
            if parent_state is not None:
                context = set_span_in_context(parent_state.span)
        span = self._tracer.start_span(
            name=span_name,
            kind=SpanKind.INTERNAL,
            context=context,
            attributes=attributes,
        )

        state = LangGraphNodeSpanState(
            span=span,
            attributes=dict(attributes),
            node_name=node_name,
        )
        self._states[run_id] = state
        return state

    def get_state(self, run_id: UUID) -> LangGraphNodeSpanState | None:
        return self._states.get(run_id)

    def pop_state(self, run_id: UUID) -> LangGraphNodeSpanState | None:
        return self._states.pop(run_id, None)
