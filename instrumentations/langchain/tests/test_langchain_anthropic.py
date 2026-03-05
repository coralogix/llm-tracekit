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

"""VCR-based tests for Anthropic (ChatAnthropic).

To record cassettes (run once with a real API key):
  uv run pytest tests/test_langchain_anthropic.py -v --record-mode=once
Requires ANTHROPIC_API_KEY.

Model ID can be overridden with ANTHROPIC_TEST_MODEL (e.g. claude-sonnet-4-6).
Default uses a current model; older IDs like claude-3-5-sonnet-20241022 may 404.
"""

import os
import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic

from .utils import (
    assert_span_attributes,
    assert_choices_in_span,
    assert_messages_in_span,
)


def _get_chat_spans(spans):
    return [span for span in spans if span.name.startswith("chat ")]


# Current model IDs change over time; override with ANTHROPIC_TEST_MODEL if needed
ANTHROPIC_MODEL = os.environ.get(
    "ANTHROPIC_TEST_MODEL",
    "claude-haiku-4-5-20251001",
)


@pytest.mark.vcr()
def test_langchain_anthropic_completion(span_exporter, instrument_langchain):
    """Test ChatAnthropic.invoke() creates span with completion attributes."""
    llm = ChatAnthropic(model=ANTHROPIC_MODEL, temperature=0)

    response = llm.invoke([HumanMessage(content="Say this is a test")])

    span = _get_chat_spans(span_exporter.get_finished_spans())[-1]
    assert span

    assert_span_attributes(
        span,
        request_model=ANTHROPIC_MODEL,
        input_tokens=response.usage_metadata.get("input_tokens")
        if response.usage_metadata
        else None,
        output_tokens=response.usage_metadata.get("output_tokens")
        if response.usage_metadata
        else None,
    )

    user_message = {"role": "user", "content": "Say this is a test"}
    assert_messages_in_span(
        span=span, expected_messages=[user_message], expect_content=True
    )

    finish_reason = None
    meta = getattr(response, "response_metadata", None)
    if meta:
        finish_reason = meta.get("stop_reason") or meta.get("finish_reason")
    if (
        finish_reason is None
        and hasattr(response, "generation_info")
        and response.generation_info
    ):
        finish_reason = response.generation_info.get("finish_reason")
    if finish_reason is None:
        finish_reason = "end_turn"

    choice = {
        "finish_reason": finish_reason,
        "message": {
            "role": "assistant",
            "content": response.content,
        },
    }
    assert_choices_in_span(span=span, expected_choices=[choice], expect_content=True)


@pytest.mark.vcr()
def test_langchain_anthropic_multi_turn(span_exporter, instrument_langchain):
    """Test multi-turn conversation captures full prompt history."""
    llm = ChatAnthropic(model=ANTHROPIC_MODEL, temperature=0)

    conversation = [
        SystemMessage(content="You're a helpful assistant."),
        HumanMessage(content="Say this is a test"),
    ]

    first_response = llm.invoke(conversation)
    conversation.append(first_response)
    conversation.append(HumanMessage(content="Now do it again"))

    final_response = llm.invoke(conversation)

    chat_spans = _get_chat_spans(span_exporter.get_finished_spans())
    assert len(chat_spans) >= 2
    span = chat_spans[-1]

    assert_span_attributes(
        span,
        request_model=ANTHROPIC_MODEL,
        input_tokens=final_response.usage_metadata.get("input_tokens")
        if final_response.usage_metadata
        else None,
        output_tokens=final_response.usage_metadata.get("output_tokens")
        if final_response.usage_metadata
        else None,
    )

    expected_messages = [
        {"role": "system", "content": "You're a helpful assistant."},
        {"role": "user", "content": "Say this is a test"},
        {"role": "assistant", "content": first_response.content},
        {"role": "user", "content": "Now do it again"},
    ]
    assert_messages_in_span(
        span=span, expected_messages=expected_messages, expect_content=True
    )

    finish_reason = None
    meta = getattr(final_response, "response_metadata", None)
    if meta:
        finish_reason = meta.get("stop_reason") or meta.get("finish_reason")
    if finish_reason is None:
        finish_reason = "end_turn"

    choice = {
        "finish_reason": finish_reason,
        "message": {
            "role": "assistant",
            "content": final_response.content,
        },
    }
    assert_choices_in_span(span=span, expected_choices=[choice], expect_content=True)


@pytest.mark.vcr()
def test_langchain_anthropic_streaming(span_exporter, instrument_langchain):
    """Test ChatAnthropic.stream() creates span with completion attributes."""
    llm = ChatAnthropic(model=ANTHROPIC_MODEL, temperature=0)

    stream = llm.stream([HumanMessage(content="Say this is a test")])
    full_message = None
    for chunk in stream:
        if full_message is None:
            full_message = chunk
        else:
            full_message += chunk

    assert full_message is not None

    span = _get_chat_spans(span_exporter.get_finished_spans())[-1]
    assert_span_attributes(
        span,
        request_model=ANTHROPIC_MODEL,
        input_tokens=full_message.usage_metadata.get("input_tokens")
        if full_message.usage_metadata
        else None,
        output_tokens=full_message.usage_metadata.get("output_tokens")
        if full_message.usage_metadata
        else None,
    )

    user_message = {"role": "user", "content": "Say this is a test"}
    assert_messages_in_span(span, [user_message], expect_content=True)

    finish_reason = None
    meta = getattr(full_message, "response_metadata", None)
    if meta:
        finish_reason = meta.get("stop_reason") or meta.get("finish_reason")
    if finish_reason is None:
        finish_reason = "end_turn"

    choice = {
        "finish_reason": finish_reason,
        "message": {
            "role": "assistant",
            "content": full_message.content,
        },
    }
    assert_choices_in_span(span, [choice], expect_content=True)
