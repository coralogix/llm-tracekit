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

"""Shared pytest fixtures for LangGraph instrumentation tests."""

from __future__ import annotations

from typing import Generator

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from llm_tracekit.langgraph.callback import LangGraphCallbackHandler
from llm_tracekit.langgraph.instrumentor import LangGraphInstrumentor


@pytest.fixture(scope="function", name="span_exporter")
def fixture_span_exporter() -> Generator[InMemorySpanExporter, None, None]:
    exporter = InMemorySpanExporter()
    try:
        yield exporter
    finally:
        exporter.clear()


@pytest.fixture(scope="function", name="tracer_provider")
def fixture_tracer_provider(span_exporter: InMemorySpanExporter) -> TracerProvider:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    return provider


@pytest.fixture(scope="function", name="tracer")
def fixture_tracer(tracer_provider: TracerProvider):
    return tracer_provider.get_tracer(__name__)


@pytest.fixture(scope="function", name="handler")
def fixture_handler(tracer) -> LangGraphCallbackHandler:
    return LangGraphCallbackHandler(tracer=tracer)


@pytest.fixture(scope="function", name="instrument")
def fixture_instrument(tracer_provider):
    instrumentor = LangGraphInstrumentor()
    instrumentor.instrument(tracer_provider=tracer_provider)
    try:
        yield instrumentor
    finally:
        instrumentor.uninstrument()
