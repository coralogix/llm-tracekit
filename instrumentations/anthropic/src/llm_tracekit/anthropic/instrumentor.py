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

"""Anthropic client instrumentation via ``AnthropicInstrumentor``."""

from typing import Collection

from anthropic.resources.messages.messages import AsyncMessages, Messages
from opentelemetry.instrumentation.instrumentor import (  # type: ignore[attr-defined]
    BaseInstrumentor,
)
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.metrics import get_meter, Meter
from opentelemetry.semconv.schemas import Schemas
from opentelemetry.trace import get_tracer
from wrapt import wrap_function_wrapper

from llm_tracekit.core import Instruments, is_content_enabled
from llm_tracekit.anthropic.package import _instruments
from llm_tracekit.anthropic.patch import async_messages_create, messages_create


class AnthropicInstrumentor(BaseInstrumentor):
    def __init__(self) -> None:
        self._meter: Meter | None = None

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
            module="anthropic.resources.messages.messages",
            name="Messages.create",
            wrapper=messages_create(tracer, instruments, capture_content),
        )
        wrap_function_wrapper(
            module="anthropic.resources.messages.messages",
            name="AsyncMessages.create",
            wrapper=async_messages_create(tracer, instruments, capture_content),
        )

    def _uninstrument(self, **kwargs) -> None:
        unwrap(Messages, "create")
        unwrap(AsyncMessages, "create")
