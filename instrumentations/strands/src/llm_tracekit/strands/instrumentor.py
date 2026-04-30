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

"""Instrumentor for Strands Agents SDK."""

from collections.abc import Collection

from opentelemetry.instrumentation.instrumentor import (  # type: ignore[attr-defined]
    BaseInstrumentor,
)

from llm_tracekit.core import is_content_enabled
from llm_tracekit.strands.package import _instruments
from llm_tracekit.strands.patch import (
    create_wrapped_start_model_invoke_span,
    create_wrapped_end_model_invoke_span,
    create_wrapped_stream_messages,
)


LIBRARY_NAME = "llm_tracekit.strands"


class StrandsInstrumentor(BaseInstrumentor):
    """Instrumentor for Strands Agents SDK that adds semantic convention attributes to spans.

    Strands Agents SDK already creates OpenTelemetry spans for agent, model, and tool calls.
    This instrumentor wraps the tracer methods to add OpenTelemetry GenAI semantic convention
    attributes for prompts, completions, and tool definitions.

    Usage:
        from llm_tracekit.strands import StrandsInstrumentor

        StrandsInstrumentor().instrument()
    """

    def __init__(self):
        super().__init__()
        self._original_start_model_invoke_span = None
        self._original_end_model_invoke_span = None
        self._original_stream_messages = None
        self._original_inner_tracer = None
        self._original_service_name: str | None = None

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        """Enable Strands instrumentation by wrapping tracer methods."""
        import strands.telemetry.tracer as tracer_module
        import strands.event_loop.streaming as streaming_module

        capture_content = is_content_enabled()

        # Store original functions
        self._original_start_model_invoke_span = (
            tracer_module.Tracer.start_model_invoke_span
        )
        self._original_end_model_invoke_span = (
            tracer_module.Tracer.end_model_invoke_span
        )
        self._original_stream_messages = streaming_module.stream_messages

        # Create wrapped versions
        wrapped_start = create_wrapped_start_model_invoke_span(
            self._original_start_model_invoke_span, capture_content
        )
        wrapped_end = create_wrapped_end_model_invoke_span(
            self._original_end_model_invoke_span, capture_content
        )
        wrapped_stream = create_wrapped_stream_messages(
            self._original_stream_messages, capture_content
        )

        # Replace the methods
        tracer_module.Tracer.start_model_invoke_span = wrapped_start
        tracer_module.Tracer.end_model_invoke_span = wrapped_end
        streaming_module.stream_messages = wrapped_stream

        # Also patch in event_loop where stream_messages is imported
        try:
            import strands.event_loop.event_loop as event_loop_module

            event_loop_module.stream_messages = wrapped_stream
        except (ImportError, AttributeError):
            pass

        # Replace the strands tracer's internal tracer so that spans are created
        # with otel.library.name containing "llm_tracekit" instead of
        # "strands.telemetry.tracer"
        strands_tracer_instance = tracer_module.get_tracer()
        self._original_inner_tracer = strands_tracer_instance.tracer
        self._original_service_name = strands_tracer_instance.service_name
        strands_tracer_instance.service_name = LIBRARY_NAME
        strands_tracer_instance.tracer = (
            strands_tracer_instance.tracer_provider.get_tracer(LIBRARY_NAME)
        )

    def _uninstrument(self, **kwargs):
        """Disable Strands instrumentation."""
        if self._original_start_model_invoke_span is not None:
            import strands.telemetry.tracer as tracer_module

            tracer_module.Tracer.start_model_invoke_span = (
                self._original_start_model_invoke_span
            )
            self._original_start_model_invoke_span = None

        if self._original_end_model_invoke_span is not None:
            import strands.telemetry.tracer as tracer_module

            tracer_module.Tracer.end_model_invoke_span = (
                self._original_end_model_invoke_span
            )
            self._original_end_model_invoke_span = None

        if self._original_stream_messages is not None:
            import strands.event_loop.streaming as streaming_module

            streaming_module.stream_messages = self._original_stream_messages

            try:
                import strands.event_loop.event_loop as event_loop_module

                event_loop_module.stream_messages = self._original_stream_messages
            except (ImportError, AttributeError):
                pass

            self._original_stream_messages = None

        if self._original_inner_tracer is not None:
            import strands.telemetry.tracer as tracer_module

            strands_tracer_instance = tracer_module.get_tracer()
            strands_tracer_instance.service_name = self._original_service_name
            strands_tracer_instance.tracer = self._original_inner_tracer
            self._original_inner_tracer = None
            self._original_service_name = None
