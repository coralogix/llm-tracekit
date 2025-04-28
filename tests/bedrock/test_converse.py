import pytest

from opentelemetry.semconv.attributes import error_attributes as ErrorAttributes
from opentelemetry.semconv._incubating.metrics import gen_ai_metrics
from tests.bedrock.utils import assert_attributes_in_span
from tests.utils import assert_messages_in_span, assert_choices_in_span


def _run_and_check_converse(bedrock_client, model_id: str, span_exporter, expect_content: bool):
    result = bedrock_client.converse(
        modelId=model_id,
        system=[{"text": "you are a helpful assistant"}],
        messages=[
            {"role": "user", "content": [{"text": "say this is a test"}]}
        ],
        inferenceConfig={
            "maxTokens": 300,
            "temperature": 0,
            "topP": 1,
        },
    )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    assert_attributes_in_span(
        span=spans[0],
        span_name="bedrock.converse",
        request_model=model_id,
        response_model=model_id,
        usage_input_tokens=result["usage"]["inputTokens"],
        usage_output_tokens=result["usage"]["outputTokens"],
        finish_reasons=(result["stopReason"],)
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


@pytest.mark.vcr()
def test_converse_with_content(bedrock_client_with_content, claude_model_id: str, span_exporter):
    _run_and_check_converse(
        bedrock_client=bedrock_client_with_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        expect_content=True,
    )


@pytest.mark.vcr()
def test_converse_no_content(bedrock_client_no_content, claude_model_id: str, span_exporter):
    _run_and_check_converse(
        bedrock_client=bedrock_client_no_content,
        model_id=claude_model_id,
        span_exporter=span_exporter,
        expect_content=False,
    )


def test_converse_tool_calls_with_content():
    pytest.fail("TODO")


def test_converse_tool_calls_no_content():
    pytest.fail("TODO")


def test_converse_non_existing_model(bedrock_client_with_content, span_exporter, metric_reader):
    model_id = "anthropic.claude-0-0-fake-00000000-v0:0"
    with pytest.raises(Exception):
        result = bedrock_client_with_content.converse(
            modelId=model_id,
            messages=[
                {"role": "user", "content": [{"text": "say this is a test"}]}
            ],
            inferenceConfig={
                "maxTokens": 300,
                "temperature": 0,
                "topP": 1,
            },
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
        == "ValidationException"
    )


def test_converse_bad_auth():
    pytest.fail("TODO")


def test_converse_mixed_content_blocks():
    pytest.fail("TODO")


def test_converse_unsupported_content_blocks():
    pytest.fail("TODO")


# TODO: consider making this part of the regular test, or in a separate test file entirely
def test_converse_metrics():
    pytest.fail("TODO")


def test_converse_stream_with_content():
    pytest.fail("TODO")


def test_converse_stream_no_content():
    pytest.fail("TODO")


def test_converse_stream_tool_calls_with_content():
    pytest.fail("TODO")


def test_converse_stream_tool_calls_no_content():
    pytest.fail("TODO")


def test_converse_stream_non_existing_model():
    pytest.fail("TODO")


def test_converse_stream_bad_auth():
    pytest.fail("TODO")


def test_converse_stream_mixed_content_blocks():
    pytest.fail("TODO")


def test_converse_stream_unsupported_content_blocks():
    pytest.fail("TODO")
