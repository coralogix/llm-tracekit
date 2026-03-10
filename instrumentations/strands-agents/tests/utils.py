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

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)


def find_spans_by_name_prefix(
    exporter: InMemorySpanExporter, prefix: str
) -> list[ReadableSpan]:
    return [s for s in exporter.get_finished_spans() if s.name.startswith(prefix)]


def find_span_by_name(
    exporter: InMemorySpanExporter, name: str
) -> ReadableSpan | None:
    for s in exporter.get_finished_spans():
        if s.name == name:
            return s
    return None


def find_span_by_name_prefix(
    exporter: InMemorySpanExporter, prefix: str
) -> ReadableSpan | None:
    for s in exporter.get_finished_spans():
        if s.name.startswith(prefix):
            return s
    return None


def assert_span_attributes(
    span: ReadableSpan,
    system: str = "strands",
    operation_name: str = "chat",
):
    assert span.attributes is not None
    assert span.attributes[GenAIAttributes.GEN_AI_SYSTEM] == system
    assert span.attributes[GenAIAttributes.GEN_AI_OPERATION_NAME] == operation_name


def get_child_spans(
    exporter: InMemorySpanExporter, parent: ReadableSpan
) -> list[ReadableSpan]:
    parent_ctx = parent.context
    if parent_ctx is None:
        return []
    return [
        s
        for s in exporter.get_finished_spans()
        if s.parent is not None and s.parent.span_id == parent_ctx.span_id
    ]
