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

"""Test fixtures for Strands instrumentation tests."""

import os
import pytest

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from llm_tracekit.strands import StrandsInstrumentor


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": [
            ("authorization", "Bearer test_api_key"),
            ("x-api-key", "test_api_key"),
        ],
        "record_mode": "none",
    }


@pytest.fixture
def span_exporter():
    """Create an in-memory span exporter for testing."""
    exporter = InMemorySpanExporter()
    yield exporter
    exporter.clear()


@pytest.fixture
def setup_tracing(span_exporter):
    """Set up OpenTelemetry tracing with the in-memory exporter."""
    provider = TracerProvider()
    processor = SimpleSpanProcessor(span_exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    yield provider


@pytest.fixture
def instrument_with_content(setup_tracing):
    """Instrument Strands with content capture enabled."""
    os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"
    instrumentor = StrandsInstrumentor()
    instrumentor.instrument()
    yield instrumentor
    instrumentor.uninstrument()
    os.environ.pop("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", None)


@pytest.fixture
def instrument_no_content(setup_tracing):
    """Instrument Strands without content capture."""
    os.environ.pop("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", None)
    instrumentor = StrandsInstrumentor()
    instrumentor.instrument()
    yield instrumentor
    instrumentor.uninstrument()
