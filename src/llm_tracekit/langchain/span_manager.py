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

"""Helpers for tracking LangChain run spans.

This module keeps an in-memory registry of LangChain run IDs mapped to their
corresponding OpenTelemetry spans. It is responsible for wiring parent/child
relationships, keeping track of span attributes collected during the run, and
ensuring spans reliably finish even if LangChain fails to emit matching end
events. The callback handler treats this manager as its persistence layer for
per-run state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from timeit import default_timer
from typing import Any, Dict, List, Optional
from uuid import UUID

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.trace import Span, SpanKind, Tracer, set_span_in_context


@dataclass
class LangChainSpanState:
    """Book-keeping for a LangChain span run.

    The callback handler keeps a ``LangChainSpanState`` per run_id so that
    subsequent end/error signals can enrich the same span with response data.
    ``children`` captures LangChain's nested run graph, letting ``end_span``
    recursively close orphaned children when a parent finishes.
    """

    span: Span
    children: List[UUID] = field(default_factory=list)
    start_time: float = field(default_factory=default_timer)
    span_attributes: Dict[str, Any] = field(default_factory=dict)
    system_value: Optional[str] = None
    request_model: Optional[str] = None


class LangChainSpanManager:
    """Creates and tracks LangChain spans keyed by LangChain run IDs.

    The manager acts as a tiny span registry. When a new run starts we create a
    span (optionally linking it to its parent) and stash all mutable context we
    will need once the run completes. When the run ends or errors, the callback
    handler retrieves the state, updates the span, and finally asks the manager
    to end the span (which also tears down any nested children).
    """

    def __init__(self, tracer: Tracer) -> None:
        self._tracer = tracer
        self._states: Dict[UUID, LangChainSpanState] = {}

    def create_chat_span(
        self,
        run_id: UUID,
        parent_run_id: Optional[UUID],
        span_name: str,
        attributes: Dict[str, Any],
    ) -> Span:
        """Create and store a chat span for the provided LangChain run."""
        return self._create_span(
            run_id=run_id,
            parent_run_id=parent_run_id,
            span_name=span_name,
            attributes=attributes,
            kind=SpanKind.CLIENT,
        )

    def get_state(self, run_id: UUID) -> Optional[LangChainSpanState]:
        return self._states.get(run_id)

    def end_span(self, run_id: UUID) -> None:
        state = self._states.pop(run_id, None)
        if state is None:
            return

        for child_id in list(state.children):
            self.end_span(child_id)

        state.span.end()

    def _create_span(
        self,
        run_id: UUID,
        parent_run_id: Optional[UUID],
        span_name: str,
        attributes: Dict[str, Any],
        kind: SpanKind,
    ) -> Span:
        """Internal helper that creates a span and registers its state."""
        parent_state = self._states.get(parent_run_id) if parent_run_id else None
        context = set_span_in_context(parent_state.span) if parent_state else None

        span = self._tracer.start_span(
            name=span_name,
            kind=kind,
            context=context,
            attributes=attributes,
        )

        if parent_state:
            parent_state.children.append(run_id)

        span_state = LangChainSpanState(
            span=span,
            span_attributes=dict(attributes),
            system_value=attributes.get(GenAIAttributes.GEN_AI_SYSTEM),
            request_model=attributes.get(GenAIAttributes.GEN_AI_REQUEST_MODEL),
        )
        self._states[run_id] = span_state
        return span
