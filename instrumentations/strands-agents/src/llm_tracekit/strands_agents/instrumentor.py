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

from typing import Collection

import wrapt

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor  # type: ignore[attr-defined]
from opentelemetry.metrics import get_meter
from opentelemetry.semconv.schemas import Schemas
from opentelemetry.trace import get_tracer

from llm_tracekit.core import is_content_enabled
from llm_tracekit.core._metrics import Instruments
from llm_tracekit.strands_agents.hook_provider import StrandsHookProvider
from llm_tracekit.strands_agents.package import _instruments


class StrandsInstrumentor(BaseInstrumentor):
    def __init__(self):
        super().__init__()
        self._hook_provider: StrandsHookProvider | None = None
        self._original_init = None

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        tracer_provider = kwargs.get("tracer_provider")
        meter_provider = kwargs.get("meter_provider")

        tracer = get_tracer(
            __name__,
            "",
            tracer_provider,
            schema_url=Schemas.V1_28_0.value,
        )
        meter = get_meter(
            __name__,
            "",
            meter_provider,
            schema_url=Schemas.V1_28_0.value,
        )
        instruments = Instruments(meter)

        self._hook_provider = StrandsHookProvider(
            tracer=tracer,
            instruments=instruments,
            capture_content=is_content_enabled(),
        )

        from strands import Agent

        self._original_init = Agent.__init__

        @wrapt.patch_function_wrapper("strands", "Agent.__init__")
        def patched_init(wrapped, instance, args, kwargs):
            wrapped(*args, **kwargs)
            instance.hooks.add_hook_provider(self._hook_provider)

    def _uninstrument(self, **kwargs):
        if self._hook_provider is not None:
            self._hook_provider.disabled = True

        if self._original_init is not None:
            from strands import Agent

            Agent.__init__ = self._original_init
            self._original_init = None
