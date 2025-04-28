import os

import boto3
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF

from llm_tracekit.bedrock.instrumentor import BedrockInstrumentor
from llm_tracekit.instrumentation_utils import (
    OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT,
)


pytest.register_assert_rewrite("tests.bedrock.utils")


@pytest.fixture(autouse=True)
def bedrock_env_vars():
    for env_var_name in [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    ]:
        if not os.getenv(env_var_name):
            os.environ[env_var_name] = f"test_{env_var_name.lower()}"

    if not os.getenv("AWS_DEFAULT_REGION"):
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def bedrock_client_with_content(instrument_with_content):
    return boto3.client("bedrock-runtime")


@pytest.fixture
def bedrock_client_no_content(instrument_no_content):
    return boto3.client("bedrock-runtime")


@pytest.fixture
def bedrock_agent_client_with_content(instrument_with_content):
    return boto3.client("bedrock-agent-runtime")


@pytest.fixture
def bedrock_agent_client_no_content(instrument_no_content):
    return boto3.client("bedrock-agent-runtime")


@pytest.fixture
def claude_model_id() -> str:
    return "anthropic.claude-3-5-sonnet-20240620-v1:0"


@pytest.fixture
def llama_model_id() -> str:
    return "meta.llama3-8b-instruct-v1:0"


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": [
            ("X-Amz-Security-Token", 'test-security-token'),
            ("Authorization", 'test-auth'),
        ],
        "decode_compressed_response": True,
    }


@pytest.fixture(scope="function")
def instrument_no_content(tracer_provider, meter_provider):
    os.environ.update({OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT: "False"})

    instrumentor = BedrockInstrumentor()
    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    yield instrumentor
    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
    instrumentor.uninstrument()


@pytest.fixture(scope="function")
def instrument_with_content(tracer_provider, meter_provider):
    os.environ.update({OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT: "True"})
    instrumentor = BedrockInstrumentor()
    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    yield instrumentor
    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
    instrumentor.uninstrument()


@pytest.fixture(scope="function")
def instrument_with_content_unsampled(span_exporter, meter_provider):
    os.environ.update({OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT: "True"})

    tracer_provider = TracerProvider(sampler=ALWAYS_OFF)
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))

    instrumentor = BedrockInstrumentor()
    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    yield instrumentor
    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
    instrumentor.uninstrument()
