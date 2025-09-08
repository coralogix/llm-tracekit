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


import os
from typing import Collection, Optional

from opentelemetry.instrumentation.instrumentor import (  # type: ignore[attr-defined]
    BaseInstrumentor,
)

from llm_tracekit.instrumentation_utils import is_content_enabled
from llm_tracekit.litellm.package import _instruments
from llm_tracekit.litellm.callback import LitellmCallback

import litellm
from litellm.integrations.opentelemetry import OpenTelemetryConfig

class LiteLLMInstrumentor(BaseInstrumentor):
    def __init__(
        self,
        coralogix_token: Optional[str] = None,
        coralogix_endpoint: Optional[str] = None,
        application_name: Optional[str] = None,
        subsystem_name: Optional[str] = None,
    ):
        self._config: Optional[OpenTelemetryConfig] = self.generate_exporter_config(
            coralogix_token,
            coralogix_endpoint,
            application_name,
            subsystem_name
        )

    def generate_exporter_config(
        self,
        coralogix_token,
        coralogix_endpoint,
        application_name,
        subsystem_name
    ) -> Optional[OpenTelemetryConfig]:
        if coralogix_token is None:
            coralogix_token = os.environ.get("CX_TOKEN")
        if coralogix_endpoint is None:
            coralogix_endpoint = os.environ.get("CX_ENDPOINT")
        if application_name is None:
            application_name = os.environ.get("CX_APPLICATION_NAME")
        if subsystem_name is None:
            subsystem_name = os.environ.get("CX_SUBSYSTEM_NAME")
        
        if not coralogix_token or not coralogix_endpoint:
            return None

        headers_dict = {
            "authorization": f"Bearer {coralogix_token}",
            "cx-application-name": application_name,
            "cx-subsystem-name": subsystem_name,
        }
        headers_string = ",".join([f"{key}={value}" for key, value in headers_dict.items()])
        
        return OpenTelemetryConfig(
            exporter="otlp_http",
            endpoint=coralogix_endpoint,
            headers=headers_string
        )

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        custom_handler = LitellmCallback(capture_content=is_content_enabled(), config=self._config)
        litellm.callbacks = [custom_handler]

    def _uninstrument(self, **kwargs):
        litellm.callbacks = []