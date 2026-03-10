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

"""Tests for US4: Uninstrumentation."""

import pytest
from unittest.mock import MagicMock, patch

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from llm_tracekit.strands import StrandsInstrumentor


class TestInstrumentUninstrument:
    def test_instrument_patches_agent_init(self):
        instrumentor = StrandsInstrumentor()
        try:
            instrumentor.instrument()
            import strands
            assert hasattr(strands.Agent.__init__, "__wrapped__")
        finally:
            instrumentor.uninstrument()

    def test_uninstrument_restores_agent_init(self):
        instrumentor = StrandsInstrumentor()
        import strands

        original_init = strands.Agent.__init__
        instrumentor.instrument()
        assert hasattr(strands.Agent.__init__, "__wrapped__")

        instrumentor.uninstrument()
        assert not hasattr(strands.Agent.__init__, "__wrapped__")

    def test_double_instrument_is_safe(self):
        instrumentor = StrandsInstrumentor()
        try:
            instrumentor.instrument()
            instrumentor.instrument()
            import strands
            assert hasattr(strands.Agent.__init__, "__wrapped__")
        finally:
            instrumentor.uninstrument()

    def test_double_uninstrument_is_safe(self):
        instrumentor = StrandsInstrumentor()
        instrumentor.instrument()
        instrumentor.uninstrument()
        instrumentor.uninstrument()

    def test_no_spans_after_uninstrument(self):
        exporter = InMemorySpanExporter()
        tp = TracerProvider()
        tp.add_span_processor(SimpleSpanProcessor(exporter))

        instrumentor = StrandsInstrumentor()
        instrumentor.instrument(tracer_provider=tp)
        instrumentor.uninstrument()

        spans = exporter.get_finished_spans()
        assert len(spans) == 0
