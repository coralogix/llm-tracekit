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
import asyncio
import litellm
from tests.utils import assert_choices_in_span, assert_messages_in_span
from tests.litellm.utils import assert_attributes, find_last_response_span


import time

@pytest.mark.vcr()
def test_litellm_completion(instrument):
    exporter = litellm.callbacks[-1].OTEL_EXPORTER
    exporter._finished_spans.clear()
    model = "gpt-4o-mini"
    messages = [{"role": "user", "content": "Say this is a test"}]

    response = litellm.completion(model=model, messages=messages)

    time.sleep(0.1) # wait for export to finish

    spans = exporter.get_finished_spans()
    assert len(spans) > 0
    span = find_last_response_span(spans) # find the response span
    
    assert_attributes(
        span,
        "openai",
        "chat",
        model,
        response.model,
        response.id,
        response.usage.prompt_tokens,
        response.usage.completion_tokens
    )

    user_message = {"role": "user", "content": messages[0]["content"]}
    assert_messages_in_span(
        span=span, expected_messages=[user_message], expect_content=True
    )

    choice = {
        "finish_reason": "stop",
        "message": {
            "role": "assistant",
            "content": response.choices[0].message.content,
        },
    }
    assert_choices_in_span(span=span, expected_choices=[choice], expect_content=True)


@pytest.mark.vcr()
def test_litellm_streaming(instrument):
    exporter = litellm.callbacks[-1].OTEL_EXPORTER
    exporter._finished_spans.clear()
    model = "gpt-4o-mini"
    messages = [{"role": "user", "content": "Say the exact message: 'this is a test'"}]

    response = litellm.completion(model=model, messages=messages, stream=True)

    for chunk in response:
        pass

    time.sleep(0.1)

    spans = exporter.get_finished_spans()
    assert len(spans) > 0
    span = find_last_response_span(spans) # find the response span

    actual_content = span.attributes.get("gen_ai.completion.0.content")

    assert actual_content is not None
    assert "test" in actual_content

    assert_attributes(
        span,
        "openai",
        "chat",
        model
    )

    user_message = {"role": "user", "content": messages[0]["content"]}
    assert_messages_in_span(
        span=span, expected_messages=[user_message], expect_content=True
    )

    choice = {
        "finish_reason": "stop",
        "message": {
            "role": "assistant",
            "content": actual_content,
        },
    }
    assert_choices_in_span(span=span, expected_choices=[choice], expect_content=True)


@pytest.mark.vcr()
def test_litellm_multi_turn(instrument):
    exporter = litellm.callbacks[-1].OTEL_EXPORTER
    exporter._finished_spans.clear()
    model = "gpt-4o-mini"
    messages = [{"role": "user", "content": "Say this is a test"}]

    response = litellm.completion(model=model, messages=messages)

    response_message = response.choices[0].message
    messages.append(response_message)

    messages.append({"role": "user", "content": "Now do it again"})

    final_response = litellm.completion(model=model, messages=messages)
    completion_content = final_response.choices[0].message.content

    time.sleep(0.2)

    spans = exporter.get_finished_spans()

    assert len(spans) > 0
    span = find_last_response_span(spans) # find the response span

    assert_attributes(
        span,
        "openai",
        "chat",
        model,
        final_response.model,
        final_response.id,
        final_response.usage.prompt_tokens,
        final_response.usage.completion_tokens,
    )

    assert_messages_in_span(span=span, expected_messages=messages, expect_content=True)

    choice = {
        "finish_reason": "stop",
        "message": {
            "role": "assistant",
            "content": completion_content,
        },
    }
    assert_choices_in_span(span=span, expected_choices=[choice], expect_content=True)


@pytest.mark.vcr()
def test_litellm_tool_usage(instrument):
    exporter = litellm.callbacks[-1].OTEL_EXPORTER
    exporter._finished_spans.clear()
    model = "gpt-4o-mini"
    messages = [{"role": "user", "content": "What is the weather in Tel Aviv?"}]

    def get_current_weather(location: str):
        return f"location: {location}, weather 15°C, sunny"

    weather_tool_description = {
        "type": "function", "function": {
            "name": "get_current_weather", "description": "Get current weather in a given location.",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string", "description": "Exact city to get weather for"}},
                "required": ["location"],
            },
        }
    }

    response = litellm.completion(model=model, messages=messages, tools=[weather_tool_description], tool_choice="auto")

    time.sleep(0.1)

    spans = exporter.get_finished_spans()
    assert len(spans) > 0
    span = find_last_response_span(spans) # find the response span

    assert_attributes(
        span,
        "openai",
        "chat",
        model,
        response.model,
        response.id,
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
    )

    assert_messages_in_span(span=span, expected_messages=messages, expect_content=True)

    tool_call = response.choices[0].message.tool_calls[0]
    choice = {
        "finish_reason": "tool_calls",
        "message": {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
            ],
        },
    }
    assert_choices_in_span(span=span, expected_choices=[choice], expect_content=True)


@pytest.mark.vcr()
@pytest.mark.asyncio()
async def test_litellm_async_completion(instrument):
    exporter = litellm.callbacks[-1].OTEL_EXPORTER
    exporter._finished_spans.clear()
    model = "gpt-4o-mini"
    messages = [{"role": "user", "content": "Say this is a test"}]

    response = await litellm.acompletion(model=model, messages=messages)
    
    await asyncio.sleep(0.1)

    spans = exporter.get_finished_spans()
    assert len(spans) > 0
    span = find_last_response_span(spans) # find the response span

    assert_attributes(
        span,
        "openai",
        "chat",
        model,
        response.model,
        response.id,
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
    )

    user_message = {"role": "user", "content": messages[0]["content"]}
    assert_messages_in_span(
        span=span, expected_messages=[user_message], expect_content=True
    )

    choice = {
        "finish_reason": "stop",
        "message": {
            "role": "assistant",
            "content": response.choices[0].message.content,
        },
    }
    assert_choices_in_span(span=span, expected_choices=[choice], expect_content=True)