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

import os

import pytest
from anthropic import Anthropic, AsyncAnthropic
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.trace import StatusCode

import llm_tracekit.core._extended_gen_ai_attributes as ExtendedGenAIAttributes

from utils import assert_base_chat_span, assert_completion, assert_prompt_messages

MODEL = os.environ.get("ANTHROPIC_TEST_MODEL", "claude-haiku-4-5-20251001")

# max_tokens must stay within non-streaming limits for current Anthropic SDK.
_MAX_TOKENS = 1024
_USER_PROMPT = "Say this is a test"
_ASSISTANT_REPLY = "This is a test."


def _chat_spans(spans):
    return [s for s in spans if s.name.startswith("chat ")]


def _text_from_response(resp) -> str:
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


@pytest.mark.vcr()
def test_messages_completion(span_exporter, instrument_with_content):
    client = Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=_MAX_TOKENS,
        temperature=0,
        messages=[{"role": "user", "content": _USER_PROMPT}],
    )

    span = _chat_spans(span_exporter.get_finished_spans())[-1]
    assert_base_chat_span(span, request_model=MODEL)
    assert span.attributes is not None
    assert span.attributes[GenAIAttributes.GEN_AI_RESPONSE_ID] == resp.id
    assert span.attributes[GenAIAttributes.GEN_AI_RESPONSE_MODEL] == str(resp.model)
    assert (
        span.attributes[GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS]
        == resp.usage.input_tokens
    )
    assert (
        span.attributes[GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS]
        == resp.usage.output_tokens
    )

    assert_prompt_messages(
        span,
        [{"role": "user", "content": _USER_PROMPT}],
        expect_content=True,
    )
    assert_completion(
        span,
        finish_reason=str(resp.stop_reason) if resp.stop_reason else None,
        expect_content=True,
        content=_text_from_response(resp),
    )


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_messages_async(span_exporter, instrument_with_content):
    client = AsyncAnthropic()
    resp = await client.messages.create(
        model=MODEL,
        max_tokens=_MAX_TOKENS,
        temperature=0,
        messages=[{"role": "user", "content": _USER_PROMPT}],
    )

    span = _chat_spans(span_exporter.get_finished_spans())[-1]
    assert_base_chat_span(span, request_model=MODEL)
    assert span.attributes is not None
    assert span.attributes[GenAIAttributes.GEN_AI_RESPONSE_ID] == resp.id


@pytest.mark.vcr()
def test_messages_streaming(span_exporter, instrument_with_content):
    client = Anthropic()
    stream = client.messages.create(
        model=MODEL,
        max_tokens=_MAX_TOKENS,
        temperature=0,
        stream=True,
        messages=[{"role": "user", "content": _USER_PROMPT}],
    )
    for _ in stream:
        pass

    span = _chat_spans(span_exporter.get_finished_spans())[-1]
    assert_base_chat_span(span, request_model=MODEL)
    assert span.attributes is not None
    assert GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS in span.attributes


@pytest.mark.vcr()
def test_messages_multi_turn_system(span_exporter, instrument_with_content):
    client = Anthropic()
    system_text = "You're a helpful assistant."
    resp = client.messages.create(
        model=MODEL,
        max_tokens=_MAX_TOKENS,
        temperature=0,
        system=system_text,
        messages=[
            {"role": "user", "content": _USER_PROMPT},
            {"role": "assistant", "content": _ASSISTANT_REPLY},
            {"role": "user", "content": "Now do it again"},
        ],
    )

    span = _chat_spans(span_exporter.get_finished_spans())[-1]
    assert_base_chat_span(span, request_model=MODEL)
    expected_prompt = [
        {"role": "system", "content": system_text},
        {"role": "user", "content": _USER_PROMPT},
        {"role": "assistant", "content": _ASSISTANT_REPLY},
        {"role": "user", "content": "Now do it again"},
    ]
    assert_prompt_messages(span, expected_prompt, expect_content=True)
    assert_completion(
        span,
        finish_reason=str(resp.stop_reason) if resp.stop_reason else None,
        expect_content=True,
        content=_text_from_response(resp),
    )


@pytest.mark.vcr()
def test_messages_tool_use(span_exporter, instrument_with_content):
    client = Anthropic()
    tools = [
        {
            "name": "report_city",
            "description": "Report a city name the user cares about.",
            "input_schema": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        }
    ]
    resp = client.messages.create(
        model=MODEL,
        max_tokens=256,
        temperature=0,
        tools=tools,
        tool_choice={"type": "any"},
        messages=[
            {
                "role": "user",
                "content": "You must use the report_city tool with city Tokyo.",
            }
        ],
    )

    span = _chat_spans(span_exporter.get_finished_spans())[-1]
    assert_base_chat_span(span, request_model=MODEL)
    assert span.attributes is not None
    assert (
        span.attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_NAME.format(
                tool_index=0
            )
        ]
        == "report_city"
    )

    tool_blocks = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
    assert tool_blocks, "expected model to return tool_use for this prompt"
    tb = tool_blocks[0]
    assert (
        span.attributes[
            ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_ID.format(
                completion_index=0, tool_call_index=0
            )
        ]
        == tb.id
    )
    assert (
        span.attributes[
            ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_FUNCTION_NAME.format(
                completion_index=0, tool_call_index=0
            )
        ]
        == tb.name
    )


@pytest.mark.vcr()
def test_messages_error_invalid_model(span_exporter, instrument_with_content):
    client = Anthropic()
    with pytest.raises(Exception):
        client.messages.create(
            model="claude-invalid-model-xyz-00000000",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}],
        )

    span = _chat_spans(span_exporter.get_finished_spans())[-1]
    assert span.status is not None
    assert span.status.status_code == StatusCode.ERROR


@pytest.mark.vcr()
def test_messages_no_content_capture(span_exporter, instrument_no_content):
    client = Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=_MAX_TOKENS,
        temperature=0,
        messages=[{"role": "user", "content": _USER_PROMPT}],
    )

    span = _chat_spans(span_exporter.get_finished_spans())[-1]
    assert_base_chat_span(span, request_model=MODEL)
    assert span.attributes is not None
    assert (
        ExtendedGenAIAttributes.GEN_AI_PROMPT_CONTENT.format(prompt_index=0)
        not in span.attributes
    )
    assert (
        ExtendedGenAIAttributes.GEN_AI_COMPLETION_CONTENT.format(completion_index=0)
        not in span.attributes
    )
    assert GenAIAttributes.GEN_AI_RESPONSE_ID in span.attributes
    assert span.attributes[GenAIAttributes.GEN_AI_RESPONSE_ID] == resp.id
