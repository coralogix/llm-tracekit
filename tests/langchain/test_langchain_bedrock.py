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

import json

import pytest

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from langchain_aws import ChatBedrock

from tests.utils import assert_choices_in_span, assert_messages_in_span
from tests.langchain.utils import assert_span_attributes


_MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"
_REGION_NAME = "us-east-1"


def _get_chat_spans(spans):
    return [span for span in spans if span.name.startswith("chat ")]


@pytest.mark.vcr()
def test_langchain_bedrock_completion(span_exporter, instrument_langchain):
    llm = ChatBedrock(
    model_id=_MODEL_ID,
    region_name=_REGION_NAME,
    model_kwargs={
        "temperature": 0.2,
        "max_tokens": 256,
        "top_p": 0.9,
        },
    )

    response = llm.invoke([HumanMessage(content="Say this is a test")])

    span = _get_chat_spans(span_exporter.get_finished_spans())[-1]
    
    assert span
    
    assert_span_attributes(
        span,
        request_model=_MODEL_ID,
        input_tokens=response.usage_metadata.get("input_tokens") if response.usage_metadata else None,
        output_tokens=response.usage_metadata.get("output_tokens") if response.usage_metadata else None,
    )

    user_message = {"role": "user", "content": "Say this is a test"}
    assert_messages_in_span(span=span, expected_messages=[user_message], expect_content=True)
    
    choice = {
        "finish_reason": "end_turn",
        "message": {
            "role": "assistant",
            "content": response.content,
        },
    }
    assert_choices_in_span(span=span, expected_choices=[choice], expect_content=True)


@pytest.mark.vcr()
def test_langchain_bedrock_multi_turn(span_exporter, instrument_langchain):
    llm = ChatBedrock(
    model_id=_MODEL_ID,
    region_name=_REGION_NAME,
    model_kwargs={
        "temperature": 0.2,
        "max_tokens": 256,
        "top_p": 0.9,
        },
    )

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
        request_model=_MODEL_ID,
        input_tokens=final_response.usage_metadata.get("input_tokens") if final_response.usage_metadata else None,
        output_tokens=final_response.usage_metadata.get("output_tokens") if final_response.usage_metadata else None,
    )

    expected_messages = [
        {"role": "system", "content": "You're a helpful assistant."},
        {"role": "user", "content": "Say this is a test"},
        {"role": "assistant", "content": first_response.content},
        {"role": "user", "content": "Now do it again"},
    ]
    assert_messages_in_span(span=span, expected_messages=expected_messages, expect_content=True)
    
    choice = {
        "finish_reason": "end_turn",
        "message": {
            "role": "assistant",
            "content": final_response.content,
        },
    }
    assert_choices_in_span(span=span, expected_choices=[choice], expect_content=True)


@pytest.mark.vcr()
def test_langchain_bedrock_tool_call(span_exporter, instrument_langchain):
    llm = ChatBedrock(
        model_id=_MODEL_ID,
        region_name=_REGION_NAME,
        model_kwargs={
            "temperature": 0.2,
            "max_tokens": 256,
            "top_p": 0.9,
        },
    )

    @tool
    def get_current_weather(location: str) -> str:
        """Return today's weather for the provided city."""
        if "seattle" in location.lower():
            return "50 degrees and raining"
        if "san francisco" in location.lower():
            return "70 degrees and sunny"
        return "Unknown weather"

    tool_llm = llm.bind_tools([get_current_weather])

    history = [
        SystemMessage(content="you are a helpful assistant"),
        HumanMessage(content="What's the weather in Seattle and San Francisco today?"),
    ]

    first_response = tool_llm.invoke(history)
    tool_messages = []
    normalized_tool_calls = []

    for call in first_response.tool_calls:
        location = call["args"].get("location")
        if not location:
            continue

        tool_result = get_current_weather.invoke({"location": location})

        tool_messages.append(
            ToolMessage(
                content=tool_result,
                tool_call_id=call["id"],
            )
        )
        normalized_tool_calls.append(
            {
                "id": call["id"],
                "type": "tool_call",
                "function": {
                    "name": call["name"],
                    "arguments": json.dumps(call["args"]),
                },
            }
        )

    final_history = history + [first_response] + tool_messages
    final_response = tool_llm.invoke(final_history)

    chat_spans = _get_chat_spans(span_exporter.get_finished_spans())
    assert len(chat_spans) >= 2
    first_span, second_span = chat_spans[-2:]

    assert_span_attributes(
        first_span,
        request_model=_MODEL_ID,
        input_tokens=first_response.usage_metadata.get("input_tokens") if first_response.usage_metadata else None,
        output_tokens=first_response.usage_metadata.get("output_tokens") if first_response.usage_metadata else None,
    )

    assert_messages_in_span(
        first_span,
        [
            {"role": "system", "content": "you are a helpful assistant"},
            {
                "role": "user",
                "content": "What's the weather in Seattle and San Francisco today?",
            },
        ],
        expect_content=True,
    )

    first_choice = {
        "finish_reason": "tool_use",
        "message": {
            "role": "assistant",
            "tool_calls": normalized_tool_calls,
        },
    }
    assert_choices_in_span(first_span, [first_choice], expect_content=True)

    assert_span_attributes(
        second_span,
        request_model=_MODEL_ID,
        input_tokens=final_response.usage_metadata.get("input_tokens") if final_response.usage_metadata else None,
        output_tokens=final_response.usage_metadata.get("output_tokens") if final_response.usage_metadata else None,
    )

    second_messages = [
        {"role": "system", "content": "you are a helpful assistant"},
        {
            "role": "user",
            "content": "What's the weather in Seattle and San Francisco today?",
        },
        {"role": "assistant", "tool_calls": normalized_tool_calls},
        {
            "role": "tool",
            "tool_call_id": normalized_tool_calls[0]["id"],
            "content": "50 degrees and raining",
        },
        {
            "role": "tool",
            "tool_call_id": normalized_tool_calls[1]["id"],
            "content": "70 degrees and sunny",
        },
    ]
    assert_messages_in_span(second_span, second_messages, expect_content=True)
    final_choice = {
        "finish_reason": "end_turn",
        "message": {"role": "assistant", "content": final_response.content},
    }
    assert_choices_in_span(second_span, [final_choice], expect_content=True)


@pytest.mark.vcr()
def test_langchain_bedrock_streaming(span_exporter, instrument_langchain):
    llm = ChatBedrock(
        model_id=_MODEL_ID,
        region_name=_REGION_NAME,
        model_kwargs={
            "temperature": 0.2,
            "max_tokens": 256,
            "top_p": 0.9,
        },
    )

    stream = llm.stream(
        [
            SystemMessage(content="you are a helpful assistant"),
            HumanMessage(content="say this is a test"),
        ]
    )

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
        request_model=_MODEL_ID,
        input_tokens=full_message.usage_metadata.get("input_tokens") if full_message.usage_metadata else None,
        output_tokens=full_message.usage_metadata.get("output_tokens") if full_message.usage_metadata else None,
    )

    messages = [
        {"role": "system", "content": "you are a helpful assistant"},
        {"role": "user", "content": "say this is a test"},
    ]

    assert_messages_in_span(span, messages, expect_content=True)

    choice = {
        "finish_reason": "end_turn",
        "message": {
            "role": getattr(full_message, "type", "assistant"),
            "content": full_message.content,
        },
    }
    assert_choices_in_span(span, [choice], expect_content=True)
