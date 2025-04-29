import boto3
from botocore.exceptions import ClientError
import pytest

from tests.bedrock.utils import assert_attributes_in_span, assert_expected_metrics
from tests.utils import assert_messages_in_span, assert_choices_in_span

# This is a PNG of a single black pixel
IMAGE_DATA = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x01\x00\x00\x00\x007n\xf9$\x00\x00\x00\nIDATx\x01c`\x00\x00\x00\x02\x00\x01su\x01\x18\x00\x00\x00\x00IEND\xaeB`\x82'


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
        "messages": [
            {"role": "user", "content": [{"text": "say this is a test"}]}
        ],
        "inferenceConfig": {
            "maxTokens": 300,
            "temperature": 0,
            "topP": 1,
        },
    }
    if stream:
        span_name = "bedrock.converse_stream"
        stream_result = bedrock_client.converse_stream(**args)
        result = {
            "stopReason": "",
            "output": {
                "usage": {},
                "message": {
                    "content": [{"text": ""}],
                }
            }
        }
        for event in stream_result["stream"]:
            if "messageStart" in event:
                result["output"]["message"]["role"] = event["messageStart"]["role"]
            if "contentBlockDelta" in event:
                result["output"]["message"]["content"][0]["text"] += event["contentBlockDelta"]["delta"]["text"]
            if "metadata" in event:
                result["usage"] = event["metadata"]["usage"]
            if "messageStop" in event:
                result["stopReason"] = event["messageStop"]["stopReason"]
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
    assert_messages_in_span(span=spans[0], expected_messages=expected_messages, expect_content=expect_content)

    expected_choice = {
        "finish_reason": result["stopReason"],
        "message": {
            "role": result["output"]["message"]["role"],
            "content": result["output"]["message"]["content"][0]["text"],
        }
    }
    assert_choices_in_span(span=spans[0], expected_choices=[expected_choice], expect_content=expect_content)


    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        model=model_id,
        usage_input_tokens=result["usage"]["inputTokens"],
        usage_output_tokens=result["usage"]["outputTokens"],
    )


@pytest.mark.vcr()
def test_converse_with_content(bedrock_client_with_content, claude_model_id: str, span_exporter, metric_reader):
    _run_and_check_converse(
        bedrock_client=bedrock_client_with_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=True,
        stream=False,
    )


@pytest.mark.vcr()
def test_converse_no_content(bedrock_client_no_content, claude_model_id: str, span_exporter, metric_reader):
    _run_and_check_converse(
        bedrock_client=bedrock_client_no_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=False,
        stream=False,
    )


def test_converse_tool_calls_with_content():
    pytest.fail("TODO")


def test_converse_tool_calls_no_content():
    pytest.fail("TODO")


@pytest.mark.vcr()
def test_converse_non_existing_model(bedrock_client_with_content, span_exporter, metric_reader):
    model_id = "anthropic.claude-0-0-fake-00000000-v0:0"
    with pytest.raises(Exception):
        bedrock_client_with_content.converse(
            modelId=model_id,
            messages=[
                {"role": "user", "content": [{"text": "say this is a test"}]}
            ],
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
    assert_messages_in_span(span=spans[0], expected_messages=expected_messages, expect_content=True)

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        model=model_id,
        error="ValidationException",
    )


@pytest.mark.vcr()
def test_converse_bad_auth(instrument_with_content, claude_model_id: str, span_exporter, metric_reader):
    client = boto3.client(
        "bedrock-runtime",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        aws_session_token="test",
    )
    with pytest.raises(ClientError):
        client.converse(
            modelId=claude_model_id,
            messages=[
                {"role": "user", "content": [{"text": "say this is a test"}]}
            ],
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
    assert_messages_in_span(span=spans[0], expected_messages=expected_messages, expect_content=True)

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        model=claude_model_id,
        error="ClientError",
    )


@pytest.mark.vcr()
def test_converse_content_blocks(bedrock_client_with_content, claude_model_id: str, span_exporter):
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
    assert_messages_in_span(span=spans[0], expected_messages=expected_messages, expect_content=True)


@pytest.mark.vcr()
def test_converse_unsupported_content_blocks(bedrock_client_with_content, claude_model_id: str, span_exporter):
    bedrock_client_with_content.converse(
        modelId=claude_model_id,
        messages=[
            {"role": "user", "content": [
                {"text": "say this"},
                {"image": {"format": "png", "source": {"bytes": IMAGE_DATA}}},
                {"text": " is a test"},
            ]}
        ],
    )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    expected_messages = [
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(span=spans[0], expected_messages=expected_messages, expect_content=True)


@pytest.mark.vcr()
def test_converse_stream_with_content(bedrock_client_with_content, claude_model_id: str, span_exporter, metric_reader):
    _run_and_check_converse(
        bedrock_client=bedrock_client_with_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=True,
        stream=True,
    )


@pytest.mark.vcr()
def test_converse_stream_no_content(bedrock_client_no_content, claude_model_id: str, span_exporter, metric_reader):
    _run_and_check_converse(
        bedrock_client=bedrock_client_no_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        expect_content=False,
        stream=True,
    )


def test_converse_stream_tool_calls_with_content():
    pytest.fail("TODO")


def test_converse_stream_tool_calls_no_content():
    pytest.fail("TODO")


@pytest.mark.vcr()
def test_converse_stream_non_existing_model(bedrock_client_with_content, span_exporter, metric_reader):
    model_id = "anthropic.claude-0-0-fake-00000000-v0:0"
    with pytest.raises(Exception):
        bedrock_client_with_content.converse_stream(
            modelId=model_id,
            messages=[
                {"role": "user", "content": [{"text": "say this is a test"}]}
            ],
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
    assert_messages_in_span(span=spans[0], expected_messages=expected_messages, expect_content=True)

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        model=model_id,
        error="ValidationException",
    )


@pytest.mark.vcr()
def test_converse_stream_bad_auth(instrument_with_content, claude_model_id: str, span_exporter, metric_reader):
    client = boto3.client(
        "bedrock-runtime",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        aws_session_token="test",
    )
    with pytest.raises(ClientError):
        client.converse_stream(
            modelId=claude_model_id,
            messages=[
                {"role": "user", "content": [{"text": "say this is a test"}]}
            ],
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
    assert_messages_in_span(span=spans[0], expected_messages=expected_messages, expect_content=True)

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        model=claude_model_id,
        error="ClientError",
    )


@pytest.mark.vcr()
def test_converse_stream_content_blocks(bedrock_client_with_content, claude_model_id: str, span_exporter):
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
    assert_messages_in_span(span=spans[0], expected_messages=expected_messages, expect_content=True)


@pytest.mark.vcr()
def test_converse_stream_unsupported_content_blocks(bedrock_client_with_content, claude_model_id: str, span_exporter):
    result = bedrock_client_with_content.converse_stream(
        modelId=claude_model_id,
        messages=[
            {"role": "user", "content": [
                {"text": "say this"},
                {"image": {"format": "png", "source": {"bytes": IMAGE_DATA}}},
                {"text": " is a test"},
            ]}
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
    assert_messages_in_span(span=spans[0], expected_messages=expected_messages, expect_content=True)
