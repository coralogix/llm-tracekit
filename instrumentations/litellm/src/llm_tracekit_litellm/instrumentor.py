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


from typing import Any, Collection, Union

from opentelemetry.instrumentation.instrumentor import (  # type: ignore[attr-defined]
    BaseInstrumentor,
)

from llm_tracekit_core import generate_exporter_config, is_content_enabled
from llm_tracekit_litellm.package import _instruments
from llm_tracekit_litellm.callback import LitellmCallback

import litellm
from litellm.integrations.opentelemetry import OpenTelemetryConfig as LiteLLMConfig

class LiteLLMInstrumentor(BaseInstrumentor):
    def __init__(
        self,
        coralogix_token: str | None = None,
        coralogix_endpoint: str | None = None,
        application_name: str | None = None,
        subsystem_name: str | None = None,
        tracer_provider: Any | None = None,
    ):
        otel_config = generate_exporter_config(
            coralogix_token=coralogix_token,
            coralogix_endpoint=coralogix_endpoint,
            application_name=application_name,
            subsystem_name=subsystem_name
        )
        
        if otel_config.headers is not None and otel_config.endpoint is not None:
            config: Union[LiteLLMConfig, None] = LiteLLMConfig(
                exporter="grpc",
                endpoint=otel_config.endpoint,
                headers=otel_config.headers # type: ignore
            )
        else:
            config = None

        self._custom_handler = LitellmCallback(
            capture_content=is_content_enabled(),
            config=config,
            tracer_provider=tracer_provider,
        )

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        if self._custom_handler not in litellm.callbacks:
            litellm.callbacks.append(self._custom_handler)

    def _uninstrument(self, **kwargs):
        if self._custom_handler in litellm.callbacks:
            litellm.callbacks.remove(self._custom_handler)