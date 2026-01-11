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

"""Instrumentor for Google ADK (Agent Development Kit)."""

from collections.abc import Collection

from opentelemetry.instrumentation.instrumentor import (  # type: ignore[attr-defined]
    BaseInstrumentor,
)

from llm_tracekit.core import is_content_enabled
from llm_tracekit.google_adk.package import _instruments
from llm_tracekit.google_adk.patch import create_wrapped_trace_call_llm


class GoogleADKInstrumentor(BaseInstrumentor):
    """Instrumentor for Google ADK that adds semantic convention attributes to spans.

    Google ADK already creates OpenTelemetry spans for LLM calls. This instrumentor
    wraps the trace_call_llm function to add OpenTelemetry GenAI semantic convention
    attributes for prompts, completions, and tool calls.

    Usage:
        from llm_tracekit.google_adk import GoogleADKInstrumentor

        GoogleADKInstrumentor().instrument()
    """

    def __init__(self):
        super().__init__()
        self._original_trace_call_llm = None

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        """Enable Google ADK instrumentation by wrapping trace_call_llm."""
        import google.adk.telemetry as telemetry_module

        # Store the original function for uninstrumentation
        self._original_trace_call_llm = telemetry_module.trace_call_llm

        # Create wrapped version
        capture_content = is_content_enabled()
        wrapped_func = create_wrapped_trace_call_llm(
            telemetry_module.trace_call_llm, capture_content
        )

        # Replace the function in the module
        telemetry_module.trace_call_llm = wrapped_func

        # Also patch in base_llm_flow where it's imported
        try:
            import google.adk.flows.llm_flows.base_llm_flow as base_llm_flow_module

            base_llm_flow_module.trace_call_llm = wrapped_func
        except ImportError:
            pass

    def _uninstrument(self, **kwargs):
        """Disable Google ADK instrumentation."""
        if self._original_trace_call_llm is not None:
            import google.adk.telemetry as telemetry_module

            telemetry_module.trace_call_llm = self._original_trace_call_llm

            try:
                import google.adk.flows.llm_flows.base_llm_flow as base_llm_flow_module

                base_llm_flow_module.trace_call_llm = self._original_trace_call_llm
            except ImportError:
                pass

            self._original_trace_call_llm = None
