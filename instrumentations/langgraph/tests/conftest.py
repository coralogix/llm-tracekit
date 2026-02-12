"""Shared pytest fixtures for LangGraph instrumentation tests."""

from __future__ import annotations

import os
from typing import Generator

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from llm_tracekit.core import OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT
from llm_tracekit.langgraph.callback import LangGraphCallbackHandler
from llm_tracekit.langgraph.instrumentor import LangGraphInstrumentor


@pytest.fixture(scope="function", name="span_exporter")
def fixture_span_exporter() -> Generator[InMemorySpanExporter, None, None]:
    exporter = InMemorySpanExporter()
    try:
        yield exporter
    finally:
        exporter.clear()


@pytest.fixture(scope="function", name="metric_reader")
def fixture_metric_reader() -> Generator[InMemoryMetricReader, None, None]:
    reader = InMemoryMetricReader()
    yield reader


@pytest.fixture(scope="function", name="tracer_provider")
def fixture_tracer_provider(span_exporter: InMemorySpanExporter) -> TracerProvider:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    return provider


@pytest.fixture(scope="function", name="meter_provider")
def fixture_meter_provider(
    metric_reader: InMemoryMetricReader,
) -> MeterProvider:
    return MeterProvider(metric_readers=[metric_reader])


@pytest.fixture(scope="function", name="tracer")
def fixture_tracer(tracer_provider: TracerProvider):
    return tracer_provider.get_tracer(__name__)


@pytest.fixture(scope="function", name="handler")
def fixture_handler(tracer) -> LangGraphCallbackHandler:
    return LangGraphCallbackHandler(tracer=tracer)


@pytest.fixture(scope="function", name="handler_with_content")
def fixture_handler_with_content(tracer) -> LangGraphCallbackHandler:
    return LangGraphCallbackHandler(tracer=tracer, capture_content=True)


@pytest.fixture(scope="function", name="instrument_no_content")
def fixture_instrument_no_content(tracer_provider, meter_provider):
    os.environ[OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT] = "False"
    instrumentor = LangGraphInstrumentor()
    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )
    try:
        yield instrumentor
    finally:
        os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
        instrumentor.uninstrument()


@pytest.fixture(scope="function", name="instrument_with_content")
def fixture_instrument_with_content(tracer_provider, meter_provider):
    os.environ[OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT] = "True"
    instrumentor = LangGraphInstrumentor()
    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )
    try:
        yield instrumentor
    finally:
        os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
        instrumentor.uninstrument()
