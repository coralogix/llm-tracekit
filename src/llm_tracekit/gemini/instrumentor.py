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


from __future__ import annotations

from typing import Collection, Union

from opentelemetry.instrumentation.instrumentor import (  # type: ignore[attr-defined]
    BaseInstrumentor,
)
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.metrics import get_meter, Meter
from opentelemetry.semconv.schemas import Schemas
from opentelemetry.trace import get_tracer
from wrapt import wrap_function_wrapper

from llm_tracekit.instrumentation_utils import is_content_enabled
from llm_tracekit.instruments import Instruments
from llm_tracekit.gemini.package import _instruments
from llm_tracekit.gemini.patch import (
    async_generate_content_stream_wrapper,
    async_generate_content_wrapper,
    generate_content_stream_wrapper,
    generate_content_wrapper,
)


class GeminiInstrumentor(BaseInstrumentor):
    def __init__(self) -> None:
        self._meter: Union[Meter, None] = None

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs) -> None:
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(
            __name__,
            "",
            tracer_provider,
            schema_url=Schemas.V1_28_0.value,
        )

        meter_provider = kwargs.get("meter_provider")
        self._meter = get_meter(
            __name__,
            "",
            meter_provider,
            schema_url=Schemas.V1_28_0.value,
        )

        instruments = Instruments(self._meter)
        capture_content = is_content_enabled()

        wrap_function_wrapper(
            module="google.genai.models",
            name="Models.generate_content",
            wrapper=generate_content_wrapper(tracer, instruments, capture_content),
        )
        wrap_function_wrapper(
            module="google.genai.models",
            name="Models.generate_content_stream",
            wrapper=generate_content_stream_wrapper(tracer, instruments, capture_content),
        )

        wrap_function_wrapper(
            module="google.genai.models",
            name="AsyncModels.generate_content",
            wrapper=async_generate_content_wrapper(
                tracer, instruments, capture_content
            ),
        )
        wrap_function_wrapper(
            module="google.genai.models",
            name="AsyncModels.generate_content_stream",
            wrapper=async_generate_content_stream_wrapper(
                tracer, instruments, capture_content
            ),
        )

    def _uninstrument(self, **kwargs) -> None:
        from google.genai.models import AsyncModels, Models

        unwrap(Models, "generate_content")
        unwrap(Models, "generate_content_stream")
        unwrap(AsyncModels, "generate_content")
        unwrap(AsyncModels, "generate_content_stream")
