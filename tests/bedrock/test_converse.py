import pytest


@pytest.mark.vcr()
def test_converse_with_content(bedrock_client, claude_model_id: str, span_exporter, instrument_with_content):
    try:
        result = bedrock_client.converse(
            modelId=claude_model_id,
            messages=[
                {"role": "user", "content": [{"text": "say this is a test"}]}
            ],
            system=[{"text": "you are a helpful assistant"}],
            inferenceConfig={
                "maxTokens": 300,
                "temperature": 0,
                "topP": 1,
            },

        )
    except Exception:
        pass
    spans = span_exporter.get_finished_spans()


def test_converse_no_content():
    pytest.fail("TODO")


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
