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

import base64
import json

import boto3
import pytest
from botocore.exceptions import ClientError

from tests.bedrock.utils import (
    IMAGE_DATA,
    assert_attributes_in_span,
    assert_expected_metrics,
    assert_tool_definitions_in_span,
)
from tests.utils import assert_choices_in_span, assert_messages_in_span


def _get_current_weather_tool_definition():
    return {
        "name": "get_current_weather",
        "description": "Get the current weather in a given location",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. Boston, MA",
                },
            },
            "required": ["location"],
            "additionalProperties": False,
        },
    }


def _convert_claude_stream_to_response(stream) -> dict:
    result = {
        "model": "",
        "role": "",
        "content": [],
        "stop_reason": "",
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
        },
    }

    current_block = {}
    for event in stream:
        parsed_chunk = json.loads(event["chunk"]["bytes"])
        if parsed_chunk["type"] == "message_start":
            result["model"] = parsed_chunk["message"]["model"]
            result["role"] = parsed_chunk["message"]["role"]
        elif parsed_chunk["type"] == "content_block_start":
            current_block = parsed_chunk["content_block"]
            if "input" in current_block:
                current_block["input"] = ""
        elif parsed_chunk["type"] == "content_block_delta":
            if parsed_chunk["delta"]["type"] == "text_delta":
                current_block["text"] += parsed_chunk["delta"]["text"]
            elif parsed_chunk["delta"]["type"] == "input_json_delta":
                current_block["input"] += parsed_chunk["delta"]["partial_json"]
        if parsed_chunk["type"] == "content_block_stop":
            if current_block["type"] == "tool_use":
                current_block["input"] = json.loads(current_block["input"])

            result["content"].append(current_block)
            current_block = {}
        elif parsed_chunk["type"] == "message_delta":
            result["stop_reason"] = parsed_chunk["delta"]["stop_reason"]
        elif parsed_chunk["type"] == "message_stop":
            result["usage"]["input_tokens"] = parsed_chunk[
                "amazon-bedrock-invocationMetrics"
            ]["inputTokenCount"]
            result["usage"]["output_tokens"] = parsed_chunk[
                "amazon-bedrock-invocationMetrics"
            ]["outputTokenCount"]

    return result


def _run_and_check_invoke_model_llama(
    bedrock_client,
    model_id: str,
    span_exporter,
    metric_reader,
    expect_content: bool,
    stream: bool,
):
    args = {
        "modelId": model_id,
        "contentType": "application/json",
        "accept": "application/json",
        "body": json.dumps(
            {
                "prompt": "say this is a test",
                "temperature": 0,
                "max_gen_len": 300,
                "top_p": 1,
            }
        ),
    }
    if stream:
        span_name = "bedrock.invoke_model_with_response_stream"
        stream_result = bedrock_client.invoke_model_with_response_stream(**args)
        result = {
            "stop_reason": "",
            "generation": "",
            "prompt_token_count": 0,
            "generation_token_count": 0,
        }
        for chunk in stream_result["body"]:
            parsed_chunk = json.loads(chunk["chunk"]["bytes"])
            result["generation"] += parsed_chunk.get("generation", "")
            if parsed_chunk.get("stop_reason") is not None:
                result["stop_reason"] = parsed_chunk["stop_reason"]
                result["prompt_token_count"] = parsed_chunk[
                    "amazon-bedrock-invocationMetrics"
                ]["inputTokenCount"]
                result["generation_token_count"] = parsed_chunk[
                    "amazon-bedrock-invocationMetrics"
                ]["outputTokenCount"]
    else:
        span_name = "bedrock.invoke_model"
        invoke_result = bedrock_client.invoke_model(**args)
        result = json.loads(invoke_result["body"].read())

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    assert_attributes_in_span(
        span=spans[0],
        span_name=span_name,
        request_model=model_id,
        response_model=model_id,
        usage_input_tokens=result["prompt_token_count"],
        usage_output_tokens=result["generation_token_count"],
        finish_reasons=(result["stop_reason"],),
        max_tokens=300,
        temperature=0,
        top_p=1,
    )

    expected_messages = [
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(
        span=spans[0],
        expected_messages=expected_messages,
        expect_content=expect_content,
    )

    expected_choice = {
        "finish_reason": result["stop_reason"],
        "message": {
            "role": "assistant",
            "content": result["generation"],
        },
    }
    assert_choices_in_span(
        span=spans[0], expected_choices=[expected_choice], expect_content=expect_content
    )

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        request_model=model_id,
        response_model=model_id,
        usage_input_tokens=result["prompt_token_count"],
        usage_output_tokens=result["generation_token_count"],
    )


def _run_and_check_invoke_model_claude(
    bedrock_client,
    model_id: str,
    span_exporter,
    metric_reader,
    expect_content: bool,
    stream: bool,
):
    args = {
        "modelId": model_id,
        "contentType": "application/json",
        "accept": "application/json",
        "body": json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": "say this is a test"}],
                "system": "You are a helpful assistant",
                "temperature": 0,
                "top_p": 1,
            }
        ),
    }
    if stream:
        span_name = "bedrock.invoke_model_with_response_stream"
        stream_result = bedrock_client.invoke_model_with_response_stream(**args)
        result = _convert_claude_stream_to_response(stream_result["body"])
    else:
        span_name = "bedrock.invoke_model"
        invoke_result = bedrock_client.invoke_model(**args)
        result = json.loads(invoke_result["body"].read())

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    assert_attributes_in_span(
        span=spans[0],
        span_name=span_name,
        request_model=model_id,
        response_model=result["model"],
        usage_input_tokens=result["usage"]["input_tokens"],
        usage_output_tokens=result["usage"]["output_tokens"],
        finish_reasons=(result["stop_reason"],),
        max_tokens=300,
        temperature=0,
        top_p=1,
    )

    expected_messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(
        span=spans[0],
        expected_messages=expected_messages,
        expect_content=expect_content,
    )

    expected_choice = {
        "finish_reason": result["stop_reason"],
        "message": {
            "role": result["role"],
            "content": result["content"][0]["text"],
        },
    }
    assert_choices_in_span(
        span=spans[0], expected_choices=[expected_choice], expect_content=expect_content
    )

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        request_model=model_id,
        response_model=result["model"],
        usage_input_tokens=result["usage"]["input_tokens"],
        usage_output_tokens=result["usage"]["output_tokens"],
    )


def _run_and_check_invoke_model_claude_tool_calls(
    bedrock_client,
    model_id: str,
    span_exporter,
    metric_reader,
    expect_content: bool,
    stream: bool,
):
    tool_definition = _get_current_weather_tool_definition()
    common_args = {
        "modelId": model_id,
        "contentType": "application/json",
        "accept": "application/json",
    }
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": "What's the weather in Seattle and San Francisco today?",
            }
        ],
        "system": "You are a helpful assistant",
        "tools": [tool_definition],
        "tool_choice": {"type": "auto"},
    }
    args = {
        **common_args,
        "body": json.dumps(body),
    }
    if stream:
        span_name = "bedrock.invoke_model_with_response_stream"
        stream_result_0 = bedrock_client.invoke_model_with_response_stream(**args)
        result_0 = _convert_claude_stream_to_response(stream_result_0["body"])
    else:
        span_name = "bedrock.invoke_model"
        invoke_result_0 = bedrock_client.invoke_model(**args)
        result_0 = json.loads(invoke_result_0["body"].read())

    tool_call_blocks = [
        block for block in result_0["content"] if block["type"] == "tool_use"
    ]

    assert result_0["stop_reason"] == "tool_use"

    tool_results = [
        {
            "tool_call_id": tool_call_blocks[0]["id"],
            "content": "50 degrees and raining",
        },
        {"tool_call_id": tool_call_blocks[1]["id"], "content": "70 degrees and sunny"},
    ]
    expected_assistant_message = {
        "role": result_0["role"],
        "content": result_0["content"][0]["text"],
        "tool_calls": [
            {
                "id": tool_call_blocks[0]["id"],
                "type": "function",
                "function": {
                    "name": tool_call_blocks[0]["name"],
                    "arguments": json.dumps(tool_call_blocks[0]["input"]),
                },
            },
            {
                "id": tool_call_blocks[1]["id"],
                "type": "function",
                "function": {
                    "name": tool_call_blocks[1]["name"],
                    "arguments": json.dumps(tool_call_blocks[1]["input"]),
                },
            },
        ],
    }

    body["messages"].append({"role": result_0["role"], "content": result_0["content"]})
    body["messages"].append(
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_results[0]["tool_call_id"],
                    "content": tool_results[0]["content"],
                },
                {
                    "type": "tool_result",
                    "tool_use_id": tool_results[1]["tool_call_id"],
                    "content": tool_results[1]["content"],
                },
            ],
        }
    )
    args = {
        **common_args,
        "body": json.dumps(body),
    }

    if stream:
        stream_result_1 = bedrock_client.invoke_model_with_response_stream(**args)
        result_1 = _convert_claude_stream_to_response(stream_result_1["body"])
    else:
        invoke_result_1 = bedrock_client.invoke_model(**args)
        result_1 = json.loads(invoke_result_1["body"].read())

    assert result_1["stop_reason"] == "end_turn"

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 2

    assert_attributes_in_span(
        span=spans[0],
        span_name=span_name,
        request_model=model_id,
        response_model=result_0["model"],
        usage_input_tokens=result_0["usage"]["input_tokens"],
        usage_output_tokens=result_0["usage"]["output_tokens"],
        finish_reasons=(result_0["stop_reason"],),
        max_tokens=1000,
    )
    assert_attributes_in_span(
        span=spans[1],
        span_name=span_name,
        request_model=model_id,
        response_model=result_1["model"],
        usage_input_tokens=result_1["usage"]["input_tokens"],
        usage_output_tokens=result_1["usage"]["output_tokens"],
        finish_reasons=(result_1["stop_reason"],),
        max_tokens=1000,
    )

    expected_tool_definition = {
        "name": tool_definition["name"],
        "description": tool_definition["description"],
        "parameters": json.dumps(tool_definition["input_schema"]),
    }
    assert_tool_definitions_in_span(spans[0], [expected_tool_definition])
    assert_tool_definitions_in_span(spans[1], [expected_tool_definition])

    expected_messages_0 = [
        {"role": "system", "content": "You are a helpful assistant"},
        {
            "role": "user",
            "content": "What's the weather in Seattle and San Francisco today?",
        },
    ]
    assert_messages_in_span(
        span=spans[0],
        expected_messages=expected_messages_0,
        expect_content=expect_content,
    )

    expected_messages_1 = [
        *expected_messages_0,
        expected_assistant_message,
        {"role": "tool", **tool_results[0]},
        {"role": "tool", **tool_results[1]},
    ]
    assert_messages_in_span(
        span=spans[1],
        expected_messages=expected_messages_1,
        expect_content=expect_content,
    )

    expected_choice_0 = {
        "finish_reason": result_0["stop_reason"],
        "message": expected_assistant_message,
    }
    assert_choices_in_span(
        span=spans[0],
        expected_choices=[expected_choice_0],
        expect_content=expect_content,
    )
    expected_choice_1 = {
        "finish_reason": result_1["stop_reason"],
        "message": {
            "role": result_1["role"],
            "content": result_1["content"][0]["text"],
        },
    }
    assert_choices_in_span(
        span=spans[1],
        expected_choices=[expected_choice_1],
        expect_content=expect_content,
    )

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        request_model=model_id,
        response_model=result_0["model"],
        usage_input_tokens=result_0["usage"]["input_tokens"]
        + result_1["usage"]["input_tokens"],
        usage_output_tokens=result_0["usage"]["output_tokens"]
        + result_1["usage"]["output_tokens"],
    )


@pytest.mark.vcr()
def test_invoke_model_claude_with_content(
    bedrock_client_with_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_invoke_model_claude(
        bedrock_client=bedrock_client_with_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=True,
        stream=False,
    )


@pytest.mark.vcr()
def test_invoke_model_claude_no_content(
    bedrock_client_no_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_invoke_model_claude(
        bedrock_client=bedrock_client_no_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=False,
        stream=False,
    )


@pytest.mark.vcr()
def test_invoke_model_claude_tool_calls_with_content(
    bedrock_client_with_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_invoke_model_claude_tool_calls(
        bedrock_client=bedrock_client_with_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=True,
        stream=False,
    )


@pytest.mark.vcr()
def test_invoke_model_claude_tool_calls_no_content(
    bedrock_client_no_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_invoke_model_claude_tool_calls(
        bedrock_client=bedrock_client_no_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=False,
        stream=False,
    )


@pytest.mark.vcr()
def test_invoke_model_claude_content_blocks(
    bedrock_client_with_content, claude_model_id: str, span_exporter
):
    bedrock_client_with_content.invoke_model(
        modelId=claude_model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "say this "},
                            {"type": "text", "text": "is a test"},
                        ],
                    }
                ],
            }
        ),
    )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    expected_messages = [
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(
        span=spans[0], expected_messages=expected_messages, expect_content=True
    )


@pytest.mark.vcr()
def test_invoke_model_claude_unsupported_content_blocks(
    bedrock_client_with_content, claude_model_id: str, span_exporter
):
    bedrock_client_with_content.invoke_model(
        modelId=claude_model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "say this "},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": base64.b64encode(IMAGE_DATA).decode(),
                                },
                            },
                            {"type": "text", "text": "is a test"},
                        ],
                    }
                ],
            }
        ),
    )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    expected_messages = [
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(
        span=spans[0], expected_messages=expected_messages, expect_content=True
    )


@pytest.mark.vcr()
def test_invoke_model_llama_with_content(
    bedrock_client_with_content, llama_model_id: str, span_exporter, metric_reader
):
    _run_and_check_invoke_model_llama(
        bedrock_client=bedrock_client_with_content,
        model_id=llama_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=True,
        stream=False,
    )


@pytest.mark.vcr()
def test_invoke_model_llama_no_content(
    bedrock_client_no_content, llama_model_id: str, span_exporter, metric_reader
):
    _run_and_check_invoke_model_llama(
        bedrock_client=bedrock_client_no_content,
        model_id=llama_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=False,
        stream=False,
    )


@pytest.mark.vcr()
def test_invoke_model_non_existing_model(
    bedrock_client_with_content, span_exporter, metric_reader
):
    model_id = "meta.llama3-8b-instruct-v999:999"
    with pytest.raises(Exception):
        bedrock_client_with_content.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({"prompt": "say this is a test"}),
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    assert_attributes_in_span(
        span=spans[0],
        span_name="bedrock.invoke_model",
        request_model=model_id,
        error="ValidationException",
    )

    expected_messages = [
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(
        span=spans[0], expected_messages=expected_messages, expect_content=True
    )

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        request_model=model_id,
        error="ValidationException",
    )


@pytest.mark.vcr()
def test_invoke_model_bad_auth(
    instrument_with_content, llama_model_id: str, span_exporter, metric_reader
):
    client = boto3.client(
        "bedrock-runtime",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        aws_session_token="test",
    )
    with pytest.raises(ClientError):
        client.invoke_model(
            modelId=llama_model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({"prompt": "say this is a test"}),
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    assert_attributes_in_span(
        span=spans[0],
        span_name="bedrock.invoke_model",
        request_model=llama_model_id,
        error="ClientError",
    )

    expected_messages = [
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(
        span=spans[0], expected_messages=expected_messages, expect_content=True
    )

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        request_model=llama_model_id,
        error="ClientError",
    )


@pytest.mark.vcr()
def test_invoke_model_with_response_stream_claude_with_content(
    bedrock_client_with_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_invoke_model_claude(
        bedrock_client=bedrock_client_with_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=True,
        stream=True,
    )


@pytest.mark.vcr()
def test_invoke_model_with_response_stream_claude_no_content(
    bedrock_client_no_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_invoke_model_claude(
        bedrock_client=bedrock_client_no_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=False,
        stream=True,
    )


@pytest.mark.vcr()
def test_invoke_model_with_response_stream_claude_tool_calls_with_content(
    bedrock_client_with_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_invoke_model_claude_tool_calls(
        bedrock_client=bedrock_client_with_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=True,
        stream=True,
    )


@pytest.mark.vcr()
def test_invoke_model_with_response_stream_claude_tool_calls_no_content(
    bedrock_client_no_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_invoke_model_claude_tool_calls(
        bedrock_client=bedrock_client_no_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=False,
        stream=True,
    )


@pytest.mark.vcr()
def test_invoke_model_with_response_stream_claude_content_blocks(
    bedrock_client_with_content, claude_model_id: str, span_exporter
):
    result = bedrock_client_with_content.invoke_model_with_response_stream(
        modelId=claude_model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "say this "},
                            {"type": "text", "text": "is a test"},
                        ],
                    }
                ],
            }
        ),
    )

    # consume the stream
    for _ in result["body"]:
        pass

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    expected_messages = [
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(
        span=spans[0], expected_messages=expected_messages, expect_content=True
    )


@pytest.mark.vcr()
def test_invoke_model_with_response_stream_claude_unsupported_content_blocks(
    bedrock_client_with_content, claude_model_id: str, span_exporter
):
    result = bedrock_client_with_content.invoke_model_with_response_stream(
        modelId=claude_model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "say this "},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": base64.b64encode(IMAGE_DATA).decode(),
                                },
                            },
                            {"type": "text", "text": "is a test"},
                        ],
                    }
                ],
            }
        ),
    )

    # consume the stream
    for _ in result["body"]:
        pass

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    expected_messages = [
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(
        span=spans[0], expected_messages=expected_messages, expect_content=True
    )


@pytest.mark.vcr()
def test_invoke_model_with_response_stream_llama_with_content(
    bedrock_client_with_content, llama_model_id: str, span_exporter, metric_reader
):
    _run_and_check_invoke_model_llama(
        bedrock_client=bedrock_client_with_content,
        model_id=llama_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=True,
        stream=True,
    )


@pytest.mark.vcr()
def test_invoke_model_with_response_stream_llama_no_content(
    bedrock_client_no_content, llama_model_id: str, span_exporter, metric_reader
):
    _run_and_check_invoke_model_llama(
        bedrock_client=bedrock_client_no_content,
        model_id=llama_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=False,
        stream=True,
    )


@pytest.mark.vcr()
def test_invoke_model_with_response_stream_non_existing_model(
    bedrock_client_with_content, span_exporter, metric_reader
):
    model_id = "meta.llama3-8b-instruct-v999:999"
    with pytest.raises(Exception):
        bedrock_client_with_content.invoke_model_with_response_stream(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({"prompt": "say this is a test"}),
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    assert_attributes_in_span(
        span=spans[0],
        span_name="bedrock.invoke_model_with_response_stream",
        request_model=model_id,
        error="ValidationException",
    )

    expected_messages = [
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(
        span=spans[0], expected_messages=expected_messages, expect_content=True
    )

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        request_model=model_id,
        error="ValidationException",
    )


@pytest.mark.vcr()
def test_invoke_model_with_response_stream_bad_auth(
    instrument_with_content, llama_model_id: str, span_exporter, metric_reader
):
    client = boto3.client(
        "bedrock-runtime",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        aws_session_token="test",
    )
    with pytest.raises(ClientError):
        client.invoke_model_with_response_stream(
            modelId=llama_model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({"prompt": "say this is a test"}),
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    assert_attributes_in_span(
        span=spans[0],
        span_name="bedrock.invoke_model_with_response_stream",
        request_model=llama_model_id,
        error="ClientError",
    )

    expected_messages = [
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(
        span=spans[0], expected_messages=expected_messages, expect_content=True
    )

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        request_model=llama_model_id,
        error="ClientError",
    )
