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
import os
from typing import Generator
from urllib.parse import urlparse, urlunparse

import boto3
import pytest
import yaml
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF

from llm_tracekit.bedrock.instrumentor import BedrockInstrumentor
from llm_tracekit.core import OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT

EVENT_STREAM_CT = "application/vnd.amazon.eventstream"


@pytest.fixture(scope="function", name="span_exporter")
def fixture_span_exporter() -> Generator[InMemorySpanExporter, None, None]:
    exporter = InMemorySpanExporter()
    yield exporter


@pytest.fixture(scope="function", name="metric_reader")
def fixture_metric_reader() -> Generator[InMemoryMetricReader, None, None]:
    exporter = InMemoryMetricReader()
    yield exporter


@pytest.fixture(scope="function", name="tracer_provider")
def fixture_tracer_provider(span_exporter) -> TracerProvider:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    return provider


@pytest.fixture(scope="function", name="meter_provider")
def fixture_meter_provider(metric_reader) -> MeterProvider:
    meter_provider = MeterProvider(
        metric_readers=[metric_reader],
    )
    return meter_provider


class LiteralBlockScalar(str):
    pass


def literal_block_scalar_presenter(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(LiteralBlockScalar, literal_block_scalar_presenter)


def process_string_value(string_value):
    try:
        json_data = json.loads(string_value)
        return LiteralBlockScalar(json.dumps(json_data, indent=2))
    except (ValueError, TypeError):
        if len(string_value) > 80:
            return LiteralBlockScalar(string_value)
    return string_value


def convert_body_to_literal(data):
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "body" and isinstance(value, dict) and "string" in value:
                value["string"] = process_string_value(value["string"])
            elif key == "body" and isinstance(value, str):
                data[key] = process_string_value(value)
            else:
                convert_body_to_literal(value)
    elif isinstance(data, list):
        for idx, choice in enumerate(data):
            data[idx] = convert_body_to_literal(choice)
    return data


class PrettyPrintJSONBody:
    @staticmethod
    def serialize(cassette_dict):
        cassette_dict = convert_body_to_literal(cassette_dict)
        return yaml.dump(cassette_dict, default_flow_style=False, allow_unicode=True)

    @staticmethod
    def deserialize(cassette_string):
        return yaml.load(cassette_string, Loader=yaml.Loader)


@pytest.fixture(scope="module", autouse=True)
def fixture_vcr(vcr):
    vcr.register_serializer("yaml", PrettyPrintJSONBody)
    return vcr


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


@pytest.fixture
def agent_id() -> str:
    return os.environ.get("AWS_BEDROCK_AGENT_ID", "test_agent_id")


@pytest.fixture
def agent_alias_id() -> str:
    return os.environ.get("AWS_BEDROCK_AGENT_ALIAS_ID", "test_agent_alias_id")


def handle_recording_filter_agent_uri(request):
    """Filters out any agent data before recording.

    Args:
        request: HTTP request

    Returns:
        Filtered request
    """
    try:
        parsed_uri = urlparse(request.uri)
        path_components = parsed_uri.path.split('/')

        idx_agents = path_components.index('agents')
        idx_aliases = path_components.index('agentAliases')

        path_components[idx_agents + 1] = "test_agent_id"
        path_components[idx_aliases + 1] = "test_agent_alias_id"

        new_path = '/'.join(path_components)

        new_uri = parsed_uri._replace(path=new_path)
        request.uri = urlunparse(new_uri)

    except ValueError:
        # if .index() returns no match (e.g. another URL)
        # do nothing
        pass

    return request


def handle_recording_boto_response(response: dict) -> dict:
    """Prepares boto3 responses for recording/playback.

    Args:
        response: HTTP response

    Returns:
        Fixed response

    Notes:
        * This function is required to play back streaming and invoke_model output
        * This function was generated by ChatGPT
    """
    # runs both when recording and when loading the cassette
    headers = response["headers"]
    if headers.get("x-vcr-base64") == ["yes"]:
        # playback branch ─ decode back to raw bytes
        response["body"]["string"] = base64.b64decode(response["body"]["string"])
        headers.pop("x-vcr-base64")
        return response

    if EVENT_STREAM_CT in (headers.get("Content-Type") or [""])[0]:
        # record branch ─ protect the bytes from PyYAML
        raw = response["body"]["string"]  # bytes from socket
        response["body"]["string"] = base64.b64encode(raw).decode()
        headers["x-vcr-base64"] = ["yes"]

    # Fix Content-Length header
    response["headers"]["Content-Length"] = [str(len(response["body"]["string"]))]
    return response


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": [
            ("X-Amz-Security-Token", "test-security-token"),
            ("Authorization", "test-auth"),
        ],
        "decode_compressed_response": True,
        "before_record_request": handle_recording_filter_agent_uri,
        "before_record_response": handle_recording_boto_response,
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
