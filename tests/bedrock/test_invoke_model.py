import json

import boto3
import pytest
from botocore.exceptions import ClientError

from tests.bedrock.utils import assert_attributes_in_span, assert_expected_metrics
from tests.utils import assert_choices_in_span, assert_messages_in_span


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
        model=model_id,
        usage_input_tokens=result["prompt_token_count"],
        usage_output_tokens=result["generation_token_count"],
    )


def test_invoke_model_calude_with_content():
    pytest.skip("TODO")


def test_invoke_model_calude_no_content():
    pytest.skip("TODO")


def test_invoke_model_calude_tool_calls_with_content():
    pytest.skip("TODO")


def test_invoke_model_calude_tool_calls_no_content():
    pytest.skip("TODO")


def test_invoke_model_calude_mixed_content_blocks():
    pytest.skip("TODO")


def test_invoke_model_calude_unsupported_content_blocks():
    pytest.skip("TODO")


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


def test_invoke_model_non_existing_model():
    pytest.skip("TODO")


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
        model=llama_model_id,
        error="ClientError",
    )


def test_invoke_model_with_response_stream_calude_with_content():
    pytest.skip("TODO")


def test_invoke_model_with_response_stream_calude_no_content():
    pytest.skip("TODO")


def test_invoke_model_with_response_stream_calude_tool_calls_with_content():
    pytest.skip("TODO")


def test_invoke_model_with_response_stream_calude_tool_calls_no_content():
    pytest.skip("TODO")


def test_invoke_model_with_response_stream_calude_mixed_content_blocks():
    pytest.skip("TODO")


def test_invoke_model_with_response_stream_calude_unsupported_content_blocks():
    pytest.skip("TODO")


def test_invoke_model_with_response_stream_llama_with_content():
    pytest.skip("TODO")


def test_invoke_model_with_response_stream_llama_no_content():
    pytest.skip("TODO")


def test_invoke_model_with_response_stream_non_existing_model():
    pytest.skip("TODO")


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
        model=llama_model_id,
        error="ClientError",
    )
