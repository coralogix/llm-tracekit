import pytest


from tests.bedrock.utils import assert_attributes_in_span
from tests.utils import assert_messages_in_span, assert_choices_in_span


@pytest.mark.vcr()
def test_converse_with_content(bedrock_client_with_content, claude_model_id: str, span_exporter):
    result = bedrock_client_with_content.converse(
        modelId=claude_model_id,
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
        model=claude_model_id,
        usage_input_tokens=result["usage"]["inputTokens"],
        usage_output_tokens=result["usage"]["outputTokens"],
        finish_reasons=(result["stopReason"],)
    )

    expected_messages = [
        {"role": "system", "content": "you are a helpful assistant"},
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(spans[0], expected_messages)

    expected_choice = {
        "finish_reason": result["stopReason"],
        "message": {
            "role": result["output"]["message"]["role"],
            "content": result["output"]["message"]["content"][0]["text"],
        }
    }
    assert_choices_in_span(spans[0], [expected_choice])


@pytest.mark.vcr()
def test_converse_no_content(bedrock_client_no_content, claude_model_id: str, span_exporter):
    result = bedrock_client_no_content.converse(
        modelId=claude_model_id,
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
        model=claude_model_id,
        usage_input_tokens=result["usage"]["inputTokens"],
        usage_output_tokens=result["usage"]["outputTokens"],
        finish_reasons=(result["stopReason"],)
    )

    expected_messages = [
        {"role": "system"},
        {"role": "user"},
    ]
    assert_messages_in_span(spans[0], expected_messages)

    expected_choice = {
        "finish_reason": result["stopReason"],
        "message": {
            "role": result["output"]["message"]["role"],
        }
    }
    assert_choices_in_span(spans[0], [expected_choice])


def test_converse_tool_calls_with_content():
    pytest.fail("TODO")


def test_converse_tool_calls_no_content():
    pytest.fail("TODO")


def test_converse_stream_non_existing_model():
    pytest.fail("TODO")


def test_converse_bad_auth():
    pytest.fail("TODO")


def test_converse_mixed_content_blocks():
    pytest.fail("TODO")


def test_converse_unsupported_content_blocks():
    pytest.fail("TODO")


def test_converse_error_in_wrapped_function():
    pytest.fail("TODO")


# TODO: consider making this part of the regular test
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


def test_converse_stream_stream_non_existing_model():
    pytest.fail("TODO")


def test_converse_stream_bad_auth():
    pytest.fail("TODO")


def test_converse_stream_mixed_content_blocks():
    pytest.fail("TODO")


def test_converse_stream_unsupported_content_blocks():
    pytest.fail("TODO")
