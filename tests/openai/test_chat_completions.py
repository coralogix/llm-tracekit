# Copyright The OpenTelemetry Authors
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
# pylint: disable=too-many-locals


import pytest
from openai import APIConnectionError, NotFoundError, OpenAI
from opentelemetry.semconv._incubating.attributes import (
    error_attributes as ErrorAttributes,
)
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.semconv._incubating.attributes import (
    server_attributes as ServerAttributes,
)
from opentelemetry.semconv._incubating.metrics import gen_ai_metrics

import llm_tracekit.extended_gen_ai_attributes as ExtendedGenAIAttributes
from tests.openai.utils import (
    assert_all_attributes,
    assert_completion_attributes,
    get_current_weather_tool_definition,
)
from tests.utils import assert_choices_in_span, assert_messages_in_span


@pytest.mark.vcr()
def test_chat_completion_with_content(
    span_exporter, openai_client, instrument_with_content
):
    llm_model_value = "gpt-4o-mini"
    messages_value = [{"role": "user", "content": "Say this is a test"}]

    response = openai_client.chat.completions.create(
        messages=messages_value, model=llm_model_value, stream=False
    )

    spans = span_exporter.get_finished_spans()
    assert_completion_attributes(spans[0], llm_model_value, response)

    user_message = {"role": "user", "content": messages_value[0]["content"]}
    assert_messages_in_span(
        span=spans[0], expected_messages=[user_message], expect_content=True
    )

    choice = {
        "finish_reason": "stop",
        "message": {
            "role": "assistant",
            "content": response.choices[0].message.content,
        },
    }
    assert_choices_in_span(
        span=spans[0], expected_choices=[choice], expect_content=True
    )


@pytest.mark.vcr()
def test_chat_completion_with_content_array(
    span_exporter, openai_client, instrument_with_content
):
    llm_model_value = "gpt-4o-mini"
    messages_value = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "Say this is a test"}],
        }
    ]

    response = openai_client.chat.completions.create(
        messages=messages_value, model=llm_model_value, stream=False
    )

    spans = span_exporter.get_finished_spans()
    assert_completion_attributes(spans[0], llm_model_value, response)

    user_message = {"role": "user"}
    assert_messages_in_span(
        span=spans[0], expected_messages=[user_message], expect_content=True
    )

    choice = {
        "finish_reason": "stop",
        "message": {
            "role": "assistant",
            "content": response.choices[0].message.content,
        },
    }
    assert_choices_in_span(
        span=spans[0], expected_choices=[choice], expect_content=True
    )


@pytest.mark.vcr()
def test_chat_completion_no_content(
    span_exporter, openai_client, instrument_no_content
):
    llm_model_value = "gpt-4o-mini"
    messages_value = [{"role": "user", "content": "Say this is a test"}]

    response = openai_client.chat.completions.create(
        messages=messages_value, model=llm_model_value, stream=False
    )

    spans = span_exporter.get_finished_spans()
    assert_completion_attributes(spans[0], llm_model_value, response)

    assert_messages_in_span(
        span=spans[0], expected_messages=[{"role": "user"}], expect_content=False
    )

    choice = {"finish_reason": "stop", "message": {"role": "assistant"}}
    assert_choices_in_span(
        span=spans[0], expected_choices=[choice], expect_content=False
    )


def test_chat_completion_bad_endpoint(
    span_exporter, metric_reader, instrument_no_content
):
    llm_model_value = "gpt-4o-mini"
    messages_value = [{"role": "user", "content": "Say this is a test"}]

    client = OpenAI(base_url="http://localhost:4242")

    with pytest.raises(APIConnectionError):
        client.chat.completions.create(
            messages=messages_value,
            model=llm_model_value,
            timeout=0.1,
        )

    spans = span_exporter.get_finished_spans()
    assert_all_attributes(spans[0], llm_model_value, server_address="localhost")
    assert 4242 == spans[0].attributes[ServerAttributes.SERVER_PORT]
    assert "APIConnectionError" == spans[0].attributes[ErrorAttributes.ERROR_TYPE]

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    duration_metric = next(
        (
            m
            for m in metric_data
            if m.name == gen_ai_metrics.GEN_AI_CLIENT_OPERATION_DURATION
        ),
        None,
    )
    assert duration_metric is not None
    assert duration_metric.data.data_points[0].sum > 0
    assert (
        duration_metric.data.data_points[0].attributes[ErrorAttributes.ERROR_TYPE]
        == "APIConnectionError"
    )


@pytest.mark.vcr()
def test_chat_completion_404(
    span_exporter, openai_client, metric_reader, instrument_no_content
):
    llm_model_value = "this-model-does-not-exist"
    messages_value = [{"role": "user", "content": "Say this is a test"}]

    with pytest.raises(NotFoundError):
        openai_client.chat.completions.create(
            messages=messages_value,
            model=llm_model_value,
        )

    spans = span_exporter.get_finished_spans()

    assert_all_attributes(spans[0], llm_model_value)
    assert "NotFoundError" == spans[0].attributes[ErrorAttributes.ERROR_TYPE]

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    duration_metric = next(
        (
            m
            for m in metric_data
            if m.name == gen_ai_metrics.GEN_AI_CLIENT_OPERATION_DURATION
        ),
        None,
    )
    assert duration_metric is not None
    assert duration_metric.data.data_points[0].sum > 0
    assert (
        duration_metric.data.data_points[0].attributes[ErrorAttributes.ERROR_TYPE]
        == "NotFoundError"
    )


@pytest.mark.vcr()
def test_chat_completion_extra_params(
    span_exporter, openai_client, instrument_no_content
):
    llm_model_value = "gpt-4o-mini"
    messages_value = [{"role": "user", "content": "Say this is a test"}]

    response = openai_client.chat.completions.create(
        messages=messages_value,
        model=llm_model_value,
        seed=42,
        temperature=0.5,
        max_tokens=50,
        stream=False,
        extra_body={"service_tier": "default"},
        response_format={"type": "text"},
        user="test_user",
    )

    spans = span_exporter.get_finished_spans()
    assert_completion_attributes(spans[0], llm_model_value, response)
    assert spans[0].attributes[GenAIAttributes.GEN_AI_OPENAI_REQUEST_SEED] == 42
    assert spans[0].attributes[GenAIAttributes.GEN_AI_REQUEST_TEMPERATURE] == 0.5
    assert spans[0].attributes[GenAIAttributes.GEN_AI_REQUEST_MAX_TOKENS] == 50
    assert (
        spans[0].attributes[GenAIAttributes.GEN_AI_OPENAI_REQUEST_SERVICE_TIER]
        == "default"
    )
    assert (
        spans[0].attributes[GenAIAttributes.GEN_AI_OPENAI_REQUEST_RESPONSE_FORMAT]
        == "text"
    )
    assert (
        spans[0].attributes[ExtendedGenAIAttributes.GEN_AI_OPENAI_REQUEST_USER]
        == "test_user"
    )


@pytest.mark.vcr()
def test_chat_completion_multiple_choices(
    span_exporter, openai_client, instrument_with_content
):
    llm_model_value = "gpt-4o-mini"
    messages_value = [{"role": "user", "content": "Say this is a test"}]

    response = openai_client.chat.completions.create(
        messages=messages_value, model=llm_model_value, n=2, stream=False
    )

    spans = span_exporter.get_finished_spans()
    assert_completion_attributes(spans[0], llm_model_value, response)

    user_message = {"role": "user", "content": messages_value[0]["content"]}
    assert_messages_in_span(
        span=spans[0], expected_messages=[user_message], expect_content=True
    )

    choices = [
        {
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": response.choices[0].message.content,
            },
        },
        {
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": response.choices[1].message.content,
            },
        },
    ]
    assert_choices_in_span(span=spans[0], expected_choices=choices, expect_content=True)


@pytest.mark.vcr()
def test_chat_completion_tool_calls_with_content(
    span_exporter, openai_client, instrument_with_content
):
    chat_completion_tool_call(span_exporter, openai_client, True)


@pytest.mark.vcr()
def test_chat_completion_tool_calls_no_content(
    span_exporter, openai_client, instrument_no_content
):
    chat_completion_tool_call(span_exporter, openai_client, False)


def chat_completion_tool_call(span_exporter, openai_client, expect_content):
    llm_model_value = "gpt-4o-mini"
    messages_value = [
        {"role": "system", "content": "You're a helpful assistant."},
        {
            "role": "user",
            "content": "What's the weather in Seattle and San Francisco today?",
        },
    ]

    response_0 = openai_client.chat.completions.create(
        messages=messages_value,
        model=llm_model_value,
        tool_choice="auto",
        tools=[get_current_weather_tool_definition()],
    )

    # sanity check
    assert "tool_calls" in response_0.choices[0].finish_reason

    # final request
    messages_value.append(
        {
            "role": "assistant",
            "tool_calls": response_0.choices[0].message.to_dict()["tool_calls"],
        }
    )

    tool_call_result_0 = {
        "role": "tool",
        "content": "50 degrees and raining",
        "tool_call_id": response_0.choices[0].message.tool_calls[0].id,
    }
    tool_call_result_1 = {
        "role": "tool",
        "content": "70 degrees and sunny",
        "tool_call_id": response_0.choices[0].message.tool_calls[1].id,
    }

    messages_value.append(tool_call_result_0)
    messages_value.append(tool_call_result_1)

    response_1 = openai_client.chat.completions.create(
        messages=messages_value, model=llm_model_value
    )

    # sanity check
    assert "stop" in response_1.choices[0].finish_reason

    # validate both calls
    spans = span_exporter.get_finished_spans()
    assert len(spans) == 2
    assert_completion_attributes(spans[0], llm_model_value, response_0)
    assert_completion_attributes(spans[1], llm_model_value, response_1)

    # call one
    system_message = {"role": "system", "content": messages_value[0]["content"]}
    user_message = {"role": "user", "content": messages_value[1]["content"]}
    assert_messages_in_span(
        span=spans[0],
        expected_messages=[system_message, user_message],
        expect_content=expect_content,
    )

    function_call_0 = {
        "name": "get_current_weather",
        "arguments": (
            response_0.choices[0]
            .message.tool_calls[0]
            .function.arguments.replace("\n", "")
        ),
    }
    function_call_1 = {
        "name": "get_current_weather",
        "arguments": (
            response_0.choices[0]
            .message.tool_calls[1]
            .function.arguments.replace("\n", "")
        ),
    }

    choice = {
        "finish_reason": "tool_calls",
        "message": {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": response_0.choices[0].message.tool_calls[0].id,
                    "type": "function",
                    "function": function_call_0,
                },
                {
                    "id": response_0.choices[0].message.tool_calls[1].id,
                    "type": "function",
                    "function": function_call_1,
                },
            ],
        },
    }
    assert_choices_in_span(
        span=spans[0], expected_choices=[choice], expect_content=expect_content
    )

    # call two
    assistant_tool_call = {
        "role": "assistant",
        "tool_calls": messages_value[2]["tool_calls"],
    }
    tool_message_0 = {
        "role": "tool",
        "tool_call_id": tool_call_result_0["tool_call_id"],
        "content": tool_call_result_0["content"],
    }
    tool_message_1 = {
        "role": "tool",
        "tool_call_id": tool_call_result_1["tool_call_id"],
        "content": tool_call_result_1["content"],
    }

    assert_messages_in_span(
        span=spans[1],
        expected_messages=[
            system_message,
            user_message,
            assistant_tool_call,
            tool_message_0,
            tool_message_1,
        ],
        expect_content=expect_content,
    )

    choice = {
        "finish_reason": "stop",
        "message": {
            "role": "assistant",
            "content": response_1.choices[0].message.content,
        },
    }

    assert_choices_in_span(
        span=spans[1], expected_choices=[choice], expect_content=expect_content
    )


@pytest.mark.vcr()
def test_chat_completion_streaming(
    span_exporter, openai_client, instrument_with_content
):
    llm_model_value = "gpt-4"
    messages_value = [{"role": "user", "content": "Say this is a test"}]

    kwargs = {
        "model": llm_model_value,
        "messages": messages_value,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    response_stream_usage = None
    response_stream_model = None
    response_stream_id = None
    response_stream_result = ""
    response = openai_client.chat.completions.create(**kwargs)
    for chunk in response:
        if chunk.choices:
            response_stream_result += chunk.choices[0].delta.content or ""

        # get the last chunk
        if getattr(chunk, "usage", None):
            response_stream_usage = chunk.usage
            response_stream_model = chunk.model
            response_stream_id = chunk.id

    spans = span_exporter.get_finished_spans()
    assert_all_attributes(
        spans[0],
        llm_model_value,
        response_stream_id,
        response_stream_model,
        response_stream_usage.prompt_tokens,
        response_stream_usage.completion_tokens,
    )

    user_message = {"role": "user", "content": "Say this is a test"}
    assert_messages_in_span(
        span=spans[0], expected_messages=[user_message], expect_content=True
    )

    choice = {
        "finish_reason": "stop",
        "message": {"role": "assistant", "content": response_stream_result},
    }
    assert_choices_in_span(
        span=spans[0], expected_choices=[choice], expect_content=True
    )


@pytest.mark.vcr()
def test_chat_completion_streaming_not_complete(
    span_exporter, openai_client, instrument_with_content
):
    llm_model_value = "gpt-4"
    messages_value = [{"role": "user", "content": "Say this is a test"}]

    kwargs = {
        "model": llm_model_value,
        "messages": messages_value,
        "stream": True,
    }

    response_stream_model = None
    response_stream_id = None
    response_stream_result = ""
    response = openai_client.chat.completions.create(**kwargs)
    for idx, chunk in enumerate(response):
        if chunk.choices:
            response_stream_result += chunk.choices[0].delta.content or ""
        if idx == 1:
            # fake a stop
            break

        if chunk.model:
            response_stream_model = chunk.model
        if chunk.id:
            response_stream_id = chunk.id

    response.close()
    spans = span_exporter.get_finished_spans()
    assert_all_attributes(
        spans[0], llm_model_value, response_stream_id, response_stream_model, 0, 0
    )

    user_message = {"role": "user", "content": "Say this is a test"}
    assert_messages_in_span(
        span=spans[0], expected_messages=[user_message], expect_content=True
    )

    choice = {
        "finish_reason": "error",
        "message": {"role": "assistant", "content": response_stream_result},
    }
    assert_choices_in_span(
        span=spans[0], expected_choices=[choice], expect_content=True
    )


@pytest.mark.vcr()
def test_chat_completion_multiple_choices_streaming(
    span_exporter, openai_client, instrument_with_content
):
    llm_model_value = "gpt-4o-mini"
    messages_value = [
        {"role": "system", "content": "You're a helpful assistant."},
        {
            "role": "user",
            "content": "What's the weather in Seattle and San Francisco today?",
        },
    ]

    response_0 = openai_client.chat.completions.create(
        messages=messages_value,
        model=llm_model_value,
        n=2,
        stream=True,
        stream_options={"include_usage": True},
    )

    # two strings for each choice
    response_stream_result = ["", ""]
    finish_reasons = ["", ""]
    for chunk in response_0:
        if chunk.choices:
            for choice in chunk.choices:
                response_stream_result[choice.index] += choice.delta.content or ""
                if choice.finish_reason:
                    finish_reasons[choice.index] = choice.finish_reason

        # get the last chunk
        if getattr(chunk, "usage", None):
            response_stream_usage = chunk.usage
            response_stream_model = chunk.model
            response_stream_id = chunk.id

    # sanity check
    assert "stop" == finish_reasons[0]

    spans = span_exporter.get_finished_spans()
    assert_all_attributes(
        spans[0],
        llm_model_value,
        response_stream_id,
        response_stream_model,
        response_stream_usage.prompt_tokens,
        response_stream_usage.completion_tokens,
    )

    messages = [
        {"role": "system", "content": messages_value[0]["content"]},
        {
            "role": "user",
            "content": "What's the weather in Seattle and San Francisco today?",
        },
    ]
    assert_messages_in_span(
        span=spans[0], expected_messages=messages, expect_content=True
    )

    choices = [
        {
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": "".join(response_stream_result[0]),
            },
        },
        {
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": "".join(response_stream_result[1]),
            },
        },
    ]
    assert_choices_in_span(span=spans[0], expected_choices=choices, expect_content=True)


@pytest.mark.vcr()
def test_chat_completion_multiple_tools_streaming_with_content(
    span_exporter, openai_client, instrument_with_content
):
    chat_completion_multiple_tools_streaming(span_exporter, openai_client, True)


@pytest.mark.vcr()
def test_chat_completion_multiple_tools_streaming_no_content(
    span_exporter, openai_client, instrument_no_content
):
    chat_completion_multiple_tools_streaming(span_exporter, openai_client, False)


@pytest.mark.vcr()
def test_chat_completion_with_content_span_unsampled(
    span_exporter,
    openai_client,
    instrument_with_content_unsampled,
):
    llm_model_value = "gpt-4o-mini"
    messages_value = [{"role": "user", "content": "Say this is a test"}]

    openai_client.chat.completions.create(
        messages=messages_value, model=llm_model_value, stream=False
    )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 0


def chat_completion_multiple_tools_streaming(
    span_exporter, openai_client, expect_content
):
    llm_model_value = "gpt-4o-mini"
    messages_value = [
        {"role": "system", "content": "You're a helpful assistant."},
        {
            "role": "user",
            "content": "What's the weather in Seattle and San Francisco today?",
        },
    ]

    response = openai_client.chat.completions.create(
        messages=messages_value,
        model=llm_model_value,
        tool_choice="auto",
        tools=[get_current_weather_tool_definition()],
        stream=True,
        stream_options={"include_usage": True},
    )

    finish_reason = None
    # two tools
    tool_names = ["", ""]
    tool_call_ids = ["", ""]
    tool_args = ["", ""]
    for chunk in response:
        if chunk.choices:
            if chunk.choices[0].finish_reason:
                finish_reason = chunk.choices[0].finish_reason
            for tool_call in chunk.choices[0].delta.tool_calls or []:
                t_idx = tool_call.index
                if tool_call.id:
                    tool_call_ids[t_idx] = tool_call.id
                if tool_call.function:
                    if tool_call.function.arguments:
                        tool_args[t_idx] += tool_call.function.arguments
                    if tool_call.function.name:
                        tool_names[t_idx] = tool_call.function.name

        # get the last chunk
        if getattr(chunk, "usage", None):
            response_stream_usage = chunk.usage
            response_stream_model = chunk.model
            response_stream_id = chunk.id

    # sanity check
    assert "tool_calls" == finish_reason

    spans = span_exporter.get_finished_spans()
    assert_all_attributes(
        spans[0],
        llm_model_value,
        response_stream_id,
        response_stream_model,
        response_stream_usage.prompt_tokens,
        response_stream_usage.completion_tokens,
    )

    system_message = {"role": "system", "content": messages_value[0]["content"]}
    user_message = {
        "role": "user",
        "content": "What's the weather in Seattle and San Francisco today?",
    }

    assert_messages_in_span(
        span=spans[0],
        expected_messages=[system_message, user_message],
        expect_content=expect_content,
    )

    tool_call_0 = {
        "id": tool_call_ids[0],
        "type": "function",
        "function": {
            "name": tool_names[0],
            "arguments": tool_args[0].replace("\n", ""),
        },
    }
    tool_call_1 = {
        "id": tool_call_ids[1],
        "type": "function",
        "function": {
            "name": tool_names[1],
            "arguments": tool_args[1].replace("\n", ""),
        },
    }

    choice = {
        "finish_reason": "tool_calls",
        "message": {
            "role": "assistant",
            "tool_calls": [tool_call_0, tool_call_1],
        },
    }
    assert_choices_in_span(
        span=spans[0], expected_choices=[choice], expect_content=expect_content
    )
