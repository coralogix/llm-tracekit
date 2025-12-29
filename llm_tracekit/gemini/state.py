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

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from opentelemetry.trace import Span

from llm_tracekit.gemini.utils import (
    GeminiResponseDetails,
    GeminiStreamState,
)


@dataclass
class GeminiSpanContext:
    span: Span
    capture_content: bool
    start_time_ns: int
    request_attributes: Dict[str, Any]


@dataclass
class GeminiOperationState:
    span_context: GeminiSpanContext
    stream_state: Optional[GeminiStreamState] = None
    response_details: Optional[GeminiResponseDetails] = None
    error_type: Optional[str] = None
    finish_reasons: List[str] = field(default_factory=list)
    span_finished: bool = False
    metrics_recorded: bool = False

    def ensure_stream_state(self) -> GeminiStreamState:
        if self.stream_state is None:
            self.stream_state = GeminiStreamState(
                capture_content=self.span_context.capture_content
            )
        return self.stream_state

    def mark_span_finished(self) -> None:
        self.span_finished = True

    def mark_metrics_recorded(self) -> None:
        self.metrics_recorded = True
