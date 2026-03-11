# Copyright Coralogix Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this package except in compliance with the License.
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
import os
from typing import Generator

import pytest
import yaml
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

try:
    from llm_tracekit.strands_agents.instrumentor import StrandsInstrumentor
except (ImportError, ModuleNotFoundError):
    pytest.skip(
        "Strands agents not available (requires Python 3.10+)", allow_module_level=True
    )

from llm_tracekit.core import OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT


@pytest.fixture(scope="function", name="span_exporter")
def fixture_span_exporter() -> Generator[InMemorySpanExporter, None, None]:
    exporter = InMemorySpanExporter()
    yield exporter


@pytest.fixture(scope="function", name="metric_reader")
def fixture_metric_reader() -> Generator[InMemoryMetricReader, None, None]:
    reader = InMemoryMetricReader()
    yield reader


@pytest.fixture(scope="function", name="tracer_provider")
def fixture_tracer_provider(span_exporter) -> TracerProvider:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    return provider


@pytest.fixture(scope="function", name="meter_provider")
def fixture_meter_provider(metric_reader) -> MeterProvider:
    return MeterProvider(metric_readers=[metric_reader])


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
                body_val = value["string"]
                if isinstance(body_val, str):
                    value["string"] = process_string_value(body_val)
            elif key == "body" and isinstance(value, str):
                data[key] = process_string_value(value)
            else:
                convert_body_to_literal(value)
    elif isinstance(data, list):
        for idx, choice in enumerate(data):
            data[idx] = convert_body_to_literal(choice)
    return data


class PrettyPrintJSONBody:
    """Custom YAML serializer that pretty-prints JSON request/response bodies.

    Binary bodies (like Bedrock event-streams) are left as bytes, which
    YAML serializes as !!binary and deserializes back to bytes automatically.
    """

    @staticmethod
    def serialize(cassette_dict):
        cassette_dict = convert_body_to_literal(cassette_dict)
        return yaml.dump(cassette_dict, default_flow_style=False, allow_unicode=True)

    @staticmethod
    def deserialize(cassette_string):
        return yaml.load(cassette_string, Loader=yaml.Loader)


@pytest.fixture(scope="module")
def vcr(request, vcr_cassette_dir, vcr_config):
    """Override pytest-vcr's vcr fixture to register our custom serializer."""
    from vcr import VCR

    kwargs = dict(
        cassette_library_dir=vcr_cassette_dir,
        path_transformer=VCR.ensure_suffix(".yaml"),
    )
    kwargs.update(vcr_config)

    record_mode = request.config.getoption("--vcr-record", default=None)
    if record_mode:
        kwargs["record_mode"] = record_mode

    v = VCR(**kwargs)
    v.register_serializer("yaml", PrettyPrintJSONBody)
    return v


@pytest.fixture(autouse=True)
def aws_env_vars():
    import botocore.session

    session = botocore.session.get_session()
    credentials = session.get_credentials()

    if credentials is None:
        for env_var_name in [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
        ]:
            if not os.getenv(env_var_name):
                os.environ[env_var_name] = f"test_{env_var_name.lower()}"

    if not os.getenv("AWS_DEFAULT_REGION"):
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


def before_record_request(request):
    if request.headers:
        for key in list(request.headers.keys()):
            val = request.headers[key]
            if isinstance(val, bytes):
                request.headers[key] = val.decode("utf-8", errors="replace")
    return request


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": [
            ("X-Amz-Security-Token", "test-security-token"),
            ("Authorization", "test-auth"),
            ("X-Amz-Date", None),
            ("amz-sdk-invocation-id", None),
            ("amz-sdk-request", None),
            ("User-Agent", None),
        ],
        "decode_compressed_response": True,
        "before_record_request": before_record_request,
    }


@pytest.fixture(scope="function")
def instrument_with_content(tracer_provider, meter_provider):
    os.environ[OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT] = "True"
    instrumentor = StrandsInstrumentor()

    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    yield instrumentor
    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
    instrumentor.uninstrument()


@pytest.fixture(scope="function")
def instrument_no_content(tracer_provider, meter_provider):
    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
    instrumentor = StrandsInstrumentor()

    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    yield instrumentor
    instrumentor.uninstrument()
