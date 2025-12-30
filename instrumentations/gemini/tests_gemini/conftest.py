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
import os
import sys
from typing import Generator

import pytest
import yaml
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from llm_tracekit_core import OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT
from llm_tracekit_gemini.instrumentor import GeminiInstrumentor

collect_ignore = []

if sys.version_info < (3, 10):
    collect_ignore.append("openai_agents")
    collect_ignore.append("langchain")


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
def gemini_env_vars():
    if not os.getenv("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = "test_gemini_api_key"


def handle_request(request):
    if 'cookie' in request.headers:
        request.headers['cookie'] = 'redacted_cookie'
    if 'x-goog-api-key' in request.headers:
        request.headers['x-goog-api-key'] = 'redacted_x_goog_api_key'
    return request


def handle_response(response):
    """
    Remove sensitive headers
    """
    if 'Set-Cookie' in response['headers']:
        response['headers']['Set-Cookie'] = ['redacted_set_cookie']
    return response


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": [
            "authorization",
            "accept-encoding",
            "content-length",
            "user-agent",
            "x-stainless-retry-count",
            "x-stainless-async",
            "x-stainless-raw-response",
            "x-stainless-read-timeout",
            'x-stainless-arch',
            'x-stainless-os',
            'x-stainless-package-version',
            'x-stainless-runtime-version',
            "Set-Cookie",
        ],
        "decode_compressed_response": True,
        "before_record_request": handle_request,
        "before_record_response": handle_response,
    }

@pytest.fixture(scope="function")
def instrument(tracer_provider, meter_provider):
    os.environ.update({OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT: "True"})
    os.environ.update({"OTEL_EXPORTER_OTLP_PROTOCOL": "in_memory"})
    os.environ.update({"OTEL_EXPORTER": "in_memory"})
    

    instrumentor = GeminiInstrumentor()
    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    yield instrumentor

    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
    os.environ.pop("OTEL_EXPORTER_OTLP_PROTOCOL", None)
    os.environ.pop("OTEL_EXPORTER", None)
    instrumentor.uninstrument()