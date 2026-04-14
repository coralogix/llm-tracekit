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

import pytest
from openai import OpenAI
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.trace import SpanKind

import llm_tracekit.core._extended_gen_ai_attributes as ExtendedGenAIAttributes
from openai.types.responses import Response
from openai.types.responses.response_completed_event import ResponseCompletedEvent

from llm_tracekit.openai.patch import ResponsesStreamWrapper
from .utils import (
    assert_all_attributes,
    assert_messages_in_span,
    assert_choices_in_span,
)


@pytest.mark.vcr()
def test_responses_with_content(
    span_exporter: InMemorySpanExporter,
    openai_client: OpenAI,
    instrument_with_content,
):
    llm_model_value = "gpt-4o-mini"
    input_text = "Say this is a test"

    response = openai_client.responses.create(
        model=llm_model_value,
        input=input_text,
    )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.kind == SpanKind.CLIENT

    assert response.usage is not None
    assert_all_attributes(
        span,
        llm_model_value,
        response.id,
        response.model,
        response.usage.input_tokens,
        response.usage.output_tokens,
        "chat",
    )

    assert_messages_in_span(
        span=span,
        expected_messages=[{"role": "user", "content": input_text}],
        expect_content=True,
    )

    choice = {
        "finish_reason": "stop",
        "message": {
            "role": "assistant",
            "content": response.output_text,
        },
    }
    assert_choices_in_span(span=span, expected_choices=[choice], expect_content=True)


@pytest.mark.vcr()
def test_responses_no_content(
    span_exporter: InMemorySpanExporter,
    openai_client: OpenAI,
    instrument_no_content,
):
    llm_model_value = "gpt-4o-mini"
    input_text = "Say this is a test"

    response = openai_client.responses.create(
        model=llm_model_value,
        input=input_text,
    )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert response.usage is not None
    assert_all_attributes(
        span,
        llm_model_value,
        response.id,
        response.model,
        response.usage.input_tokens,
        response.usage.output_tokens,
        "chat",
    )

    assert_messages_in_span(
        span=span,
        expected_messages=[{"role": "user"}],
        expect_content=False,
    )

    choice = {
        "finish_reason": "stop",
        "message": {
            "role": "assistant",
        },
    }
    assert_choices_in_span(span=span, expected_choices=[choice], expect_content=False)


def test_responses_stream_wrapper_completed_sets_span_attributes(
    tracer_provider,
    span_exporter: InMemorySpanExporter,
):
    from opentelemetry import trace

    trace.set_tracer_provider(tracer_provider)
    tracer = trace.get_tracer(__name__)

    raw: dict = {
        "id": "resp_stream_test",
        "object": "response",
        "created_at": 1731368630,
        "model": "gpt-4o-mini-2024-07-18",
        "output": [
            {
                "type": "message",
                "id": "msg_1",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": "Streamed reply.",
                        "annotations": [],
                    }
                ],
            }
        ],
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "status": "completed",
        "usage": {
            "input_tokens": 5,
            "output_tokens": 3,
            "total_tokens": 8,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }
    completed = ResponseCompletedEvent(
        type="response.completed",
        sequence_number=1,
        response=Response.model_validate(raw),
    )

    class _EventStream:
        def __init__(self) -> None:
            self._it = iter([completed])

        def __iter__(self) -> "_EventStream":
            return self

        def __next__(self) -> ResponseCompletedEvent:
            return next(self._it)

        def close(self) -> None:
            pass

    with tracer.start_as_current_span(
        "responses_stream_test", end_on_exit=False
    ) as span:
        wrapper = ResponsesStreamWrapper(_EventStream(), span, capture_content=True)
        for _ in wrapper:
            pass

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    finished = spans[0]
    assert finished.attributes is not None
    assert finished.attributes[GenAIAttributes.GEN_AI_RESPONSE_ID] == "resp_stream_test"
    assert (
        finished.attributes[
            ExtendedGenAIAttributes.GEN_AI_COMPLETION_CONTENT.format(completion_index=0)
        ]
        == "Streamed reply."
    )
