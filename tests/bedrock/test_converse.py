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
from copy import deepcopy

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
        "toolSpec": {
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "inputSchema": {
                "json": {
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
            },
        },
    }


def _convert_stream_to_response(stream) -> dict:
    result = {
        "stopReason": "",
        "output": {
            "usage": {},
            "message": {
                "content": [],
            },
        },
    }
    current_block = {}
    for event in stream:
        if "messageStart" in event:
            result["output"]["message"]["role"] = event["messageStart"]["role"]
        if "contentBlockStart" in event:
            start = event["contentBlockStart"].get("start", {})
            if "toolUse" in start:
                current_block = {"toolUse": deepcopy(start["toolUse"])}
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            if "text" in delta:
                current_block.setdefault("text", "")
                current_block["text"] += delta["text"]
            elif "toolUse" in delta:
                current_block["toolUse"].setdefault("input", "")
                current_block["toolUse"]["input"] += delta["toolUse"]["input"]
        if "contentBlockStop" in event:
            if "toolUse" in current_block:
                current_block["toolUse"]["input"] = json.loads(
                    current_block["toolUse"]["input"]
                )
            result["output"]["message"]["content"].append(current_block)
            current_block = {}
        if "metadata" in event:
            result["usage"] = event["metadata"]["usage"]
        if "messageStop" in event:
            result["stopReason"] = event["messageStop"]["stopReason"]

    return result


def _run_and_check_converse(
    bedrock_client,
    model_id: str,
    span_exporter,
    metric_reader,
    expect_content: bool,
    stream: bool,
):
    args = {
        "modelId": model_id,
        "system": [{"text": "you are a helpful assistant"}],
        "messages": [{"role": "user", "content": [{"text": "say this is a test"}]}],
        "inferenceConfig": {
            "maxTokens": 300,
            "temperature": 0,
            "topP": 1,
        },
    }
    if stream:
        span_name = "bedrock.converse_stream"
        stream_result = bedrock_client.converse_stream(**args)
        result = _convert_stream_to_response(stream_result["stream"])
    else:
        span_name = "bedrock.converse"
        result = bedrock_client.converse(**args)

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    assert_attributes_in_span(
        span=spans[0],
        span_name=span_name,
        request_model=model_id,
        response_model=model_id,
        usage_input_tokens=result["usage"]["inputTokens"],
        usage_output_tokens=result["usage"]["outputTokens"],
        finish_reasons=(result["stopReason"],),
        max_tokens=300,
        temperature=0,
        top_p=1,
    )

    expected_messages = [
        {"role": "system", "content": "you are a helpful assistant"},
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(
        span=spans[0],
        expected_messages=expected_messages,
        expect_content=expect_content,
    )

    expected_choice = {
        "finish_reason": result["stopReason"],
        "message": {
            "role": result["output"]["message"]["role"],
            "content": result["output"]["message"]["content"][0]["text"],
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
        usage_input_tokens=result["usage"]["inputTokens"],
        usage_output_tokens=result["usage"]["outputTokens"],
    )


def _run_and_check_converse_tool_calls(
    bedrock_client,
    model_id: str,
    span_exporter,
    metric_reader,
    expect_content: bool,
    stream: bool,
):
    tool_definition = _get_current_weather_tool_definition()
    args = {
        "modelId": model_id,
        "system": [{"text": "you are a helpful assistant"}],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"text": "What's the weather in Seattle and San Francisco today?"}
                ],
            }
        ],
        "toolConfig": {"tools": [tool_definition]},
    }
    if stream:
        span_name = "bedrock.converse_stream"
        stream_result_0 = bedrock_client.converse_stream(**args)
        result_0 = _convert_stream_to_response(stream_result_0["stream"])
    else:
        span_name = "bedrock.converse"
        result_0 = bedrock_client.converse(**args)
    tool_call_blocks = [
        block
        for block in result_0["output"]["message"]["content"]
        if "toolUse" in block
    ]

    assert result_0["stopReason"] == "tool_use"

    tool_results = [
        {
            "tool_call_id": tool_call_blocks[0]["toolUse"]["toolUseId"],
            "content": "50 degrees and raining",
        },
        {
            "tool_call_id": tool_call_blocks[1]["toolUse"]["toolUseId"],
            "content": "70 degrees and sunny",
        },
    ]

    args["messages"].append(result_0["output"]["message"])
    args["messages"].append(
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": tool_results[0]["tool_call_id"],
                        "content": [{"text": tool_results[0]["content"]}],
                    }
                },
                {
                    "toolResult": {
                        "toolUseId": tool_results[1]["tool_call_id"],
                        "content": [{"text": tool_results[1]["content"]}],
                    }
                },
            ],
        }
    )

    if stream:
        stream_result_1 = bedrock_client.converse_stream(**args)
        result_1 = _convert_stream_to_response(stream_result_1["stream"])
    else:
        result_1 = bedrock_client.converse(**args)
    assert result_1["stopReason"] == "end_turn"

    expected_assistant_message = {
        "role": result_0["output"]["message"]["role"],
        "content": result_0["output"]["message"]["content"][0]["text"],
        "tool_calls": [
            {
                "id": tool_call_blocks[0]["toolUse"]["toolUseId"],
                "type": "function",
                "function": {
                    "name": tool_call_blocks[0]["toolUse"]["name"],
                    "arguments": json.dumps(tool_call_blocks[0]["toolUse"]["input"]),
                },
            },
            {
                "id": tool_call_blocks[1]["toolUse"]["toolUseId"],
                "type": "function",
                "function": {
                    "name": tool_call_blocks[1]["toolUse"]["name"],
                    "arguments": json.dumps(tool_call_blocks[1]["toolUse"]["input"]),
                },
            },
        ],
    }

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 2

    assert_attributes_in_span(
        span=spans[0],
        span_name=span_name,
        request_model=model_id,
        response_model=model_id,
        usage_input_tokens=result_0["usage"]["inputTokens"],
        usage_output_tokens=result_0["usage"]["outputTokens"],
        finish_reasons=(result_0["stopReason"],),
    )
    assert_attributes_in_span(
        span=spans[1],
        span_name=span_name,
        request_model=model_id,
        response_model=model_id,
        usage_input_tokens=result_1["usage"]["inputTokens"],
        usage_output_tokens=result_1["usage"]["outputTokens"],
        finish_reasons=(result_1["stopReason"],),
    )

    expected_tool_definition = {
        "name": tool_definition["toolSpec"]["name"],
        "description": tool_definition["toolSpec"]["description"],
        "parameters": json.dumps(tool_definition["toolSpec"]["inputSchema"]["json"]),
    }
    assert_tool_definitions_in_span(spans[0], [expected_tool_definition])
    assert_tool_definitions_in_span(spans[1], [expected_tool_definition])

    expected_messages_0 = [
        {"role": "system", "content": "you are a helpful assistant"},
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
        "finish_reason": result_0["stopReason"],
        "message": expected_assistant_message,
    }
    assert_choices_in_span(
        span=spans[0],
        expected_choices=[expected_choice_0],
        expect_content=expect_content,
    )

    expected_choice_1 = {
        "finish_reason": result_1["stopReason"],
        "message": {
            "role": result_1["output"]["message"]["role"],
            "content": result_1["output"]["message"]["content"][0]["text"],
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
        response_model=model_id,
        usage_input_tokens=result_0["usage"]["inputTokens"]
        + result_1["usage"]["inputTokens"],
        usage_output_tokens=result_0["usage"]["outputTokens"]
        + result_1["usage"]["outputTokens"],
    )


@pytest.mark.vcr()
def test_converse_with_content(
    bedrock_client_with_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_converse(
        bedrock_client=bedrock_client_with_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=True,
        stream=False,
    )


@pytest.mark.vcr()
def test_converse_no_content(
    bedrock_client_no_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_converse(
        bedrock_client=bedrock_client_no_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=False,
        stream=False,
    )


@pytest.mark.vcr()
def test_converse_tool_calls_with_content(
    bedrock_client_with_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_converse_tool_calls(
        bedrock_client=bedrock_client_with_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=True,
        stream=False,
    )


@pytest.mark.vcr()
def test_converse_tool_calls_no_content(
    bedrock_client_no_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_converse_tool_calls(
        bedrock_client=bedrock_client_no_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=False,
        stream=False,
    )


@pytest.mark.vcr()
def test_converse_non_existing_model(
    bedrock_client_with_content, span_exporter, metric_reader
):
    model_id = "anthropic.claude-0-0-fake-00000000-v0:0"
    with pytest.raises(Exception):
        bedrock_client_with_content.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "say this is a test"}]}],
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    assert_attributes_in_span(
        span=spans[0],
        span_name="bedrock.converse",
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
def test_converse_bad_auth(
    instrument_with_content, claude_model_id: str, span_exporter, metric_reader
):
    client = boto3.client(
        "bedrock-runtime",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        aws_session_token="test",
    )
    with pytest.raises(ClientError):
        client.converse(
            modelId=claude_model_id,
            messages=[{"role": "user", "content": [{"text": "say this is a test"}]}],
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    assert_attributes_in_span(
        span=spans[0],
        span_name="bedrock.converse",
        request_model=claude_model_id,
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
        request_model=claude_model_id,
        error="ClientError",
    )


@pytest.mark.vcr()
def test_converse_content_blocks(
    bedrock_client_with_content, claude_model_id: str, span_exporter
):
    bedrock_client_with_content.converse(
        modelId=claude_model_id,
        messages=[
            {"role": "user", "content": [{"text": "say this"}, {"text": " is a test"}]}
        ],
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
def test_converse_unsupported_content_blocks(
    bedrock_client_with_content, claude_model_id: str, span_exporter
):
    bedrock_client_with_content.converse(
        modelId=claude_model_id,
        messages=[
            {
                "role": "user",
                "content": [
                    {"text": "say this"},
                    {"image": {"format": "png", "source": {"bytes": IMAGE_DATA}}},
                    {"text": " is a test"},
                ],
            }
        ],
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
def test_converse_stream_with_content(
    bedrock_client_with_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_converse(
        bedrock_client=bedrock_client_with_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=True,
        stream=True,
    )


@pytest.mark.vcr()
def test_converse_stream_no_content(
    bedrock_client_no_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_converse(
        bedrock_client=bedrock_client_no_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=False,
        stream=True,
    )


@pytest.mark.vcr()
def test_converse_stream_tool_calls_with_content(
    bedrock_client_with_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_converse_tool_calls(
        bedrock_client=bedrock_client_with_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=True,
        stream=True,
    )


@pytest.mark.vcr()
def test_converse_stream_tool_calls_no_content(
    bedrock_client_no_content, claude_model_id: str, span_exporter, metric_reader
):
    _run_and_check_converse_tool_calls(
        bedrock_client=bedrock_client_no_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=False,
        stream=True,
    )


@pytest.mark.vcr()
def test_converse_stream_non_existing_model(
    bedrock_client_with_content, span_exporter, metric_reader
):
    model_id = "anthropic.claude-0-0-fake-00000000-v0:0"
    with pytest.raises(Exception):
        bedrock_client_with_content.converse_stream(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "say this is a test"}]}],
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    assert_attributes_in_span(
        span=spans[0],
        span_name="bedrock.converse_stream",
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
def test_converse_stream_bad_auth(
    instrument_with_content, claude_model_id: str, span_exporter, metric_reader
):
    client = boto3.client(
        "bedrock-runtime",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        aws_session_token="test",
    )
    with pytest.raises(ClientError):
        client.converse_stream(
            modelId=claude_model_id,
            messages=[{"role": "user", "content": [{"text": "say this is a test"}]}],
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    assert_attributes_in_span(
        span=spans[0],
        span_name="bedrock.converse_stream",
        request_model=claude_model_id,
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
        request_model=claude_model_id,
        error="ClientError",
    )


@pytest.mark.vcr()
def test_converse_stream_content_blocks(
    bedrock_client_with_content, claude_model_id: str, span_exporter
):
    result = bedrock_client_with_content.converse_stream(
        modelId=claude_model_id,
        messages=[
            {"role": "user", "content": [{"text": "say this"}, {"text": " is a test"}]}
        ],
    )
    # Consume the stream
    for event in result["stream"]:
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
def test_converse_stream_unsupported_content_blocks(
    bedrock_client_with_content, claude_model_id: str, span_exporter
):
    result = bedrock_client_with_content.converse_stream(
        modelId=claude_model_id,
        messages=[
            {
                "role": "user",
                "content": [
                    {"text": "say this"},
                    {"image": {"format": "png", "source": {"bytes": IMAGE_DATA}}},
                    {"text": " is a test"},
                ],
            }
        ],
    )
    # Consume the stream
    for event in result["stream"]:
        pass

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    expected_messages = [
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(
        span=spans[0], expected_messages=expected_messages, expect_content=True
    )
