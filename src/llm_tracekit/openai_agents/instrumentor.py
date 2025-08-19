# Copyright The OpenTelemetry Authors
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


from typing import Collection

from agents.tracing import add_trace_processor

from opentelemetry.instrumentation.instrumentor import (  # type: ignore[attr-defined] # Mypy doesn't recognize the attribute
    BaseInstrumentor,
)
from opentelemetry.semconv.schemas import Schemas
from opentelemetry.trace import get_tracer  

from llm_tracekit.instrumentation_utils import is_content_enabled
from llm_tracekit.openai_agents.package import _instruments
from llm_tracekit.openai_agents.tracing_processor import (
    OpenAIAgentsTracingProcessor
)


class OpenAIAgentsInstrumentor(BaseInstrumentor):
    def __init__(self):
        self._agent_tracer = None
        self._processor_added = False

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        """Enable OpenAI instrumentation."""
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(
            __name__,
            "",
            tracer_provider,
            schema_url=Schemas.V1_28_0.value,
        )
        self._agent_tracer = OpenAIAgentsTracingProcessor(
            tracer=tracer,
            capture_content=is_content_enabled()
        )
        if not self._processor_added:
            add_trace_processor(self._agent_tracer)
            self._processor_added = True

    def _uninstrument(self, **kwargs):
        self._agent_tracer.disabled = True