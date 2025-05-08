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

from typing import Collection

import botocore.client
import botocore.session
from opentelemetry.instrumentation.instrumentor import (  # type: ignore[attr-defined] # Mypy doesn't recognize the attribute
    BaseInstrumentor,
)
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.metrics import get_meter
from opentelemetry.semconv.schemas import Schemas
from opentelemetry.trace import get_tracer
from wrapt import wrap_function_wrapper

from llm_tracekit.bedrock.package import _instruments
from llm_tracekit.bedrock.patch import create_client_wrapper
from llm_tracekit.instrumentation_utils import is_content_enabled
from llm_tracekit.instruments import Instruments


class BedrockInstrumentor(BaseInstrumentor):
    def __init__(self):
        self._meter = None

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        """Enable OpenAI instrumentation."""
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(
            __name__,
            "",
            tracer_provider,
            schema_url=Schemas.V1_32_0.value,
        )
        meter_provider = kwargs.get("meter_provider")
        self._meter = get_meter(
            __name__,
            "",
            meter_provider,
            schema_url=Schemas.V1_32_0.value,
        )

        instruments = Instruments(self._meter)

        wrap_function_wrapper(
            module="botocore.client",
            name="ClientCreator.create_client",
            wrapper=create_client_wrapper(tracer, instruments, is_content_enabled()),
        )

        wrap_function_wrapper(
            module="botocore.session",
            name="Session.create_client",
            wrapper=create_client_wrapper(tracer, instruments, is_content_enabled()),
        )

    def _uninstrument(self, **kwargs):
        unwrap(botocore.client.ClientCreator, "create_client")
        unwrap(botocore.session.Session, "create_client")
