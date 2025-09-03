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
from typing import Collection

from opentelemetry.instrumentation.instrumentor import (  # type: ignore[attr-defined]
    BaseInstrumentor,
)

from llm_tracekit.instrumentation_utils import is_content_enabled
from llm_tracekit.litellm.package import _instruments
from llm_tracekit.litellm.callback import LitellmCallback

import litellm
from litellm.integrations.opentelemetry import OpenTelemetryConfig

class LiteLLMInstrumentor(BaseInstrumentor):
    def __init__(self):
        self._coralogix_token = os.environ.get("CX_TOKEN")
        self._coralogix_endpoint = os.environ.get("CX_ENDPOINT")
        self._application_name = os.environ.get("CX_APPLICATION_NAME")
        self._subsystem_name = os.environ.get("CX_SUBSYSTEM_NAME")
        if not self._coralogix_token or not self._coralogix_endpoint:
            self._config = None
        else:
            headers_dict = {
                "authorization": f"Bearer {self._coralogix_token}",
                "cx-application-name": self._application_name,
                "cx-subsystem-name": self._subsystem_name,
            }
            headers_string = ",".join([f"{key}={value}" for key, value in headers_dict.items()])
            self._config = OpenTelemetryConfig(
                exporter="otlp_http",
                endpoint=self._coralogix_endpoint,
                headers=headers_string
            )

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        custom_handler = LitellmCallback(capture_content=is_content_enabled(), config=self._config)
        litellm.callbacks = [custom_handler]

    def _uninstrument(self, **kwargs):
        litellm.callbacks = []