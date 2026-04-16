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

import os

import pytest
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

from .utils import (
    assert_base_responses_span,
    assert_prompt_messages,
    assert_completion,
)

MODEL = os.environ.get("FOUNDRY_TEST_MODEL", "gpt-4o")


@pytest.mark.vcr()
def test_responses_with_content(
    span_exporter, project_client, instrument_with_content
):
    with project_client.get_openai_client() as openai_client:
        response = openai_client.responses.create(
            model=MODEL,
            input="Say hello",
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert_base_responses_span(span, request_model=MODEL)
    assert_prompt_messages(
        span,
        expected=[{"role": "user", "content": "Say hello"}],
        expect_content=True,
    )
    assert_completion(
        span,
        finish_reason="stop",
        role="assistant",
        expect_content=True,
    )

    assert span.attributes[GenAIAttributes.GEN_AI_RESPONSE_MODEL] is not None
    assert span.attributes[GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS] > 0
    assert span.attributes[GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS] > 0


@pytest.mark.vcr()
def test_responses_no_content(
    span_exporter, project_client, instrument_no_content
):
    with project_client.get_openai_client() as openai_client:
        response = openai_client.responses.create(
            model=MODEL,
            input="Say hello",
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert_base_responses_span(span, request_model=MODEL)
    assert_prompt_messages(
        span,
        expected=[{"role": "user"}],
        expect_content=False,
    )
    assert_completion(
        span,
        finish_reason="stop",
        role="assistant",
        expect_content=False,
    )


@pytest.mark.vcr()
def test_responses_with_instructions(
    span_exporter, project_client, instrument_with_content
):
    with project_client.get_openai_client() as openai_client:
        response = openai_client.responses.create(
            model=MODEL,
            instructions="You are a pirate. Respond in pirate speak.",
            input="Say hello",
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert_base_responses_span(span, request_model=MODEL)
    assert_prompt_messages(
        span,
        expected=[
            {"role": "system", "content": "You are a pirate. Respond in pirate speak."},
            {"role": "user", "content": "Say hello"},
        ],
        expect_content=True,
    )


@pytest.mark.vcr()
def test_responses_streaming(
    span_exporter, project_client, instrument_with_content
):
    with project_client.get_openai_client() as openai_client:
        stream = openai_client.responses.create(
            model=MODEL,
            input="Count to 3",
            stream=True,
        )
        events = list(stream)

    assert len(events) > 0

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert_base_responses_span(span, request_model=MODEL)
    assert_prompt_messages(
        span,
        expected=[{"role": "user", "content": "Count to 3"}],
        expect_content=True,
    )
    assert_completion(
        span,
        role="assistant",
        expect_content=True,
    )
