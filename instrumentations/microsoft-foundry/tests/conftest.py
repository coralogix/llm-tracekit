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
import re
from typing import Generator
from urllib.parse import urlparse

import pytest
import vcr.persisters.filesystem as _vcr_fs
from vcr.serialize import serialize as _vcr_serialize
import yaml
from azure.ai.projects import AIProjectClient
from azure.ai.projects.aio import AIProjectClient as AsyncAIProjectClient
from azure.core.credentials import AccessToken
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from llm_tracekit.core import OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT
from llm_tracekit.microsoft_foundry import MicrosoftFoundryInstrumentor


def _save_cassette_utf8(cassette_path, cassette_dict, serializer):
    data = _vcr_serialize(cassette_dict, serializer)
    with open(cassette_path, "w", encoding="utf-8") as f:
        f.write(data)


_vcr_fs.FilesystemPersister.save_cassette = staticmethod(_save_cassette_utf8)


TEST_ENDPOINT = "https://test-resource.services.ai.azure.com/api/projects/test-project"
_TEST_PARSED = urlparse(TEST_ENDPOINT)
_ENDPOINT_PATTERN = re.compile(
    r"https://[^/]+\.services\.ai\.azure\.com/api/projects/[^/]+"
)


def _normalize_uri(uri: str) -> str:
    return _ENDPOINT_PATTERN.sub(TEST_ENDPOINT, uri)


def _scrub_request(request):
    request.uri = _normalize_uri(request.uri)
    if "host" in request.headers:
        request.headers["host"] = _TEST_PARSED.netloc
    return request


def _uri_matcher(r1, r2):
    return _normalize_uri(r1.uri) == _normalize_uri(r2.uri)


class MockCredential:
    """Mock credential for VCR cassette playback."""

    def get_token(self, *scopes, **kwargs) -> AccessToken:
        return AccessToken(token="test_token", expires_on=9999999999)

    async def get_token_async(self, *scopes, **kwargs) -> AccessToken:
        return AccessToken(token="test_token", expires_on=9999999999)

    async def close(self):
        pass

    def close_sync(self):
        pass


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
    return MeterProvider(metric_readers=[metric_reader])


class LiteralBlockScalar(str):
    """Formats the string as a literal block scalar."""


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
    vcr.register_matcher("uri", _uri_matcher)
    return vcr


def _get_credential():
    real_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "")
    if real_endpoint and real_endpoint != TEST_ENDPOINT:
        from azure.identity import DefaultAzureCredential
        return DefaultAzureCredential()
    return MockCredential()


@pytest.fixture(autouse=True)
def env_vars():
    if not os.getenv("AZURE_AI_PROJECT_ENDPOINT"):
        os.environ["AZURE_AI_PROJECT_ENDPOINT"] = TEST_ENDPOINT


@pytest.fixture
def project_client() -> AIProjectClient:
    endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT", TEST_ENDPOINT)
    return AIProjectClient(
        endpoint=endpoint,
        credential=_get_credential(),
    )


@pytest.fixture
def async_project_client() -> AsyncAIProjectClient:
    endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT", TEST_ENDPOINT)
    return AsyncAIProjectClient(
        endpoint=endpoint,
        credential=_get_credential(),
    )


def scrub_response_headers(response):
    headers = response["headers"]

    encoding = headers.get("content-encoding", headers.get("Content-Encoding", ""))
    if isinstance(encoding, list):
        encoding = encoding[0] if encoding else ""
    body = response["body"].get("string", b"")
    if isinstance(body, bytes) and encoding:
        try:
            if "br" in encoding:
                import brotli
                body = brotli.decompress(body)
            elif "gzip" in encoding:
                import gzip
                body = gzip.decompress(body)
            response["body"]["string"] = body.decode("utf-8")
            for key in list(headers.keys()):
                if key.lower() == "content-encoding":
                    del headers[key]
        except Exception:
            pass

    scrub = {
        "x-ms-client-request-id",
        "x-ms-request-id",
        "x-request-id",
        "apim-request-id",
        "azureml-model-session",
        "openai-organization",
        "openai-project",
        "openai-client-partition-id",
        "Set-Cookie",
    }
    remove_prefixes = ("x-ratelimit-",)
    for key in list(headers.keys()):
        if key in scrub:
            headers[key] = "test_value"
        elif any(key.startswith(p) for p in remove_prefixes):
            del headers[key]
    return response


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": [
            ("authorization", "Bearer test_token"),
            ("api-key", "test_api_key"),
            ("host", _TEST_PARSED.netloc),
        ],
        "before_record_request": _scrub_request,
        "before_record_response": scrub_response_headers,
        "match_on": ["method", "uri", "body"],
    }


@pytest.fixture(scope="function")
def instrument_no_content(tracer_provider, meter_provider):
    os.environ.update({OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT: "False"})

    instrumentor = MicrosoftFoundryInstrumentor()
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
    instrumentor = MicrosoftFoundryInstrumentor()
    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    yield instrumentor
    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
    instrumentor.uninstrument()
