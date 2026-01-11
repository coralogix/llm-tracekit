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

import os

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from llm_tracekit.google_adk.instrumentor import GoogleADKInstrumentor
from llm_tracekit.instrumentation_utils import (
    OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT,
)

# Set up tracer provider BEFORE any google.adk imports happen
# This is important because google.adk.telemetry creates its tracer at import time
_span_exporter = InMemorySpanExporter()
_tracer_provider = TracerProvider()
_tracer_provider.add_span_processor(SimpleSpanProcessor(_span_exporter))
trace.set_tracer_provider(_tracer_provider)

# Now we can safely set up the instrumentor
_instrumentor = None


@pytest.fixture(autouse=True)
def google_adk_env_vars():
    if not os.getenv("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = "test_google_api_key"


def handle_request(request):
    """Remove sensitive headers from requests."""
    if "cookie" in request.headers:
        request.headers["cookie"] = "redacted_cookie"
    if "x-goog-api-key" in request.headers:
        request.headers["x-goog-api-key"] = "redacted_x_goog_api_key"
    return request


def handle_response(response):
    """Remove sensitive headers from responses."""
    if "Set-Cookie" in response["headers"]:
        response["headers"]["Set-Cookie"] = ["redacted_set_cookie"]
    return response


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": [
            "authorization",
            "accept-encoding",
            "content-length",
            "user-agent",
            "x-goog-api-key",
            "x-stainless-retry-count",
            "x-stainless-async",
            "x-stainless-raw-response",
            "x-stainless-read-timeout",
            "x-stainless-arch",
            "x-stainless-os",
            "x-stainless-package-version",
            "x-stainless-runtime-version",
            "Set-Cookie",
        ],
        "decode_compressed_response": True,
        "before_record_request": handle_request,
        "before_record_response": handle_response,
    }


@pytest.fixture(scope="function")
def span_exporter():
    """Get the shared span exporter and clear it before each test."""
    _span_exporter.clear()
    return _span_exporter


@pytest.fixture(scope="function")
def instrument():
    """Instrument Google ADK with content capture enabled."""
    global _instrumentor

    os.environ.update({OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT: "True"})
    os.environ.update({"OTEL_EXPORTER_OTLP_PROTOCOL": "in_memory"})
    os.environ.update({"OTEL_EXPORTER": "in_memory"})

    if _instrumentor is None:
        _instrumentor = GoogleADKInstrumentor()
        _instrumentor.instrument()

    yield _instrumentor

    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
    os.environ.pop("OTEL_EXPORTER_OTLP_PROTOCOL", None)
    os.environ.pop("OTEL_EXPORTER", None)


def pytest_sessionfinish(session, exitstatus):
    """Clean up after all tests."""
    global _instrumentor
    if _instrumentor is not None:
        _instrumentor.uninstrument()
        _instrumentor = None
