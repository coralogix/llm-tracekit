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
from openai import AsyncOpenAI
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind

from .utils import (
    assert_all_attributes,
    assert_messages_in_span,
    assert_choices_in_span,
)


@pytest.mark.asyncio
@pytest.mark.vcr()
async def test_async_responses_with_content(
    span_exporter: InMemorySpanExporter,
    async_openai_client: AsyncOpenAI,
    instrument_with_content,
):
    llm_model_value = "gpt-4o-mini"
    input_text = "Say this is a test"

    response = await async_openai_client.responses.create(
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


@pytest.mark.asyncio
@pytest.mark.vcr()
async def test_async_responses_no_content(
    span_exporter: InMemorySpanExporter,
    async_openai_client: AsyncOpenAI,
    instrument_no_content,
):
    llm_model_value = "gpt-4o-mini"
    input_text = "Say this is a test"

    response = await async_openai_client.responses.create(
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
