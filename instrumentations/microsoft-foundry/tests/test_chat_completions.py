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
    assert_base_chat_span,
    assert_prompt_messages,
    assert_completion,
)

MODEL = os.environ.get("FOUNDRY_TEST_MODEL", "gpt-4o")


@pytest.mark.vcr()
def test_chat_completion_with_content(
    span_exporter, project_client, instrument_with_content
):
    with project_client.get_openai_client() as openai_client:
        response = openai_client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Say hello"}],
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert_base_chat_span(span, request_model=MODEL)
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
def test_chat_completion_no_content(
    span_exporter, project_client, instrument_no_content
):
    with project_client.get_openai_client() as openai_client:
        response = openai_client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Say hello"}],
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert_base_chat_span(span, request_model=MODEL)
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
def test_chat_completion_streaming(
    span_exporter, project_client, instrument_with_content
):
    with project_client.get_openai_client() as openai_client:
        stream = openai_client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Count to 3"}],
            stream=True,
        )
        chunks = list(stream)

    assert len(chunks) > 0

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert_base_chat_span(span, request_model=MODEL)
    assert_prompt_messages(
        span,
        expected=[{"role": "user", "content": "Count to 3"}],
        expect_content=True,
    )
    assert_completion(
        span,
        finish_reason="stop",
        role="assistant",
        expect_content=True,
    )


@pytest.mark.vcr()
def test_chat_completion_with_tools(
    span_exporter, project_client, instrument_with_content
):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                    },
                    "required": ["location"],
                },
            },
        }
    ]

    with project_client.get_openai_client() as openai_client:
        response = openai_client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "What's the weather in Paris?"}],
            tools=tools,
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert_base_chat_span(span, request_model=MODEL)
    assert span.attributes["gen_ai.request.tools.0.type"] == "function"
    assert span.attributes["gen_ai.request.tools.0.function.name"] == "get_weather"


@pytest.mark.vcr()
def test_chat_completion_multi_turn(
    span_exporter, project_client, instrument_with_content
):
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "My name is Alice."},
        {"role": "assistant", "content": "Hello Alice! How can I help you today?"},
        {"role": "user", "content": "What is my name?"},
    ]

    with project_client.get_openai_client() as openai_client:
        response = openai_client.chat.completions.create(
            model=MODEL,
            messages=messages,
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert_base_chat_span(span, request_model=MODEL)
    assert_prompt_messages(
        span,
        expected=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "My name is Alice."},
            {"role": "assistant", "content": "Hello Alice! How can I help you today?"},
            {"role": "user", "content": "What is my name?"},
        ],
        expect_content=True,
    )
