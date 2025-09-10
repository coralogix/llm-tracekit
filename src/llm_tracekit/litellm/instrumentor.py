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


from typing import Collection, Optional, Union

from opentelemetry.instrumentation.instrumentor import (  # type: ignore[attr-defined]
    BaseInstrumentor,
)

from llm_tracekit.coralogix import ExportConfig, generate_exporter_config
from llm_tracekit.instrumentation_utils import is_content_enabled
from llm_tracekit.litellm.package import _instruments
from llm_tracekit.litellm.callback import LitellmCallback

import litellm
from litellm.integrations.opentelemetry import OpenTelemetryConfig as LiteLLMConfig

class LiteLLMInstrumentor(BaseInstrumentor):
    def __init__(
        self,
        coralogix_token: Optional[str] = None,
        coralogix_endpoint: Optional[str] = None,
        application_name: Optional[str] = None,
        subsystem_name: Optional[str] = None,
    ):
        config = generate_exporter_config(
            coralogix_token,
            coralogix_endpoint,
            application_name,
            subsystem_name
        )

        if config.headers is not None and config.endpoint is not None:
            headers_string = ",".join([f"{key}={value}" for key, value in config.headers.items()])
            self._config = LiteLLMConfig(
                exporter="otlp_http",
                endpoint=config.endpoint,
                headers=headers_string
            )
        else:
            self._config = None

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        custom_handler = LitellmCallback(capture_content=is_content_enabled(), config=self._config)
        litellm.callbacks = [custom_handler]

    def _uninstrument(self, **kwargs):
        litellm.callbacks = []