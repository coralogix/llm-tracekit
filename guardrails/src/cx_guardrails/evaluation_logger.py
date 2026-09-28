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

from functools import cache

from opentelemetry import trace
from opentelemetry._logs import Logger, NoOpLogger
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from llm_tracekit.core import generate_exporter_config, setup_log_exporter

from .log_attributes import (
    INTEGRATION_SOURCE_TYPE_KEY,
    INTEGRATION_SOURCE_TYPE_VALUE,
    INTEGRATION_SOURCE_VERSION_KEY,
    INTEGRATION_SOURCE_VERSION_VALUE,
)

EVALUATION_LOGGER_NAME = "cx_guardrails"


@cache
def get_evaluation_logger() -> Logger:
    """Return the logger that exports guardrail evaluation logs to Coralogix.

    Uses a private LoggerProvider so the user's global logs setup is never
    touched. Created lazily, once, since the tracer provider is only known
    after setup_export_to_coralogix has run.
    """
    tracer_provider = trace.get_tracer_provider()
    # Without an SDK tracer provider, telemetry export was never set up.
    if not isinstance(tracer_provider, TracerProvider):
        return NoOpLogger(EVALUATION_LOGGER_NAME)

    exporter_config = generate_exporter_config(None, None, None, None)
    if not exporter_config.endpoint:
        return NoOpLogger(EVALUATION_LOGGER_NAME)

    # Merged onto the tracer resource so service.name matches the spans.
    resource = tracer_provider.resource.merge(
        Resource(
            {
                INTEGRATION_SOURCE_TYPE_KEY: INTEGRATION_SOURCE_TYPE_VALUE,
                INTEGRATION_SOURCE_VERSION_KEY: INTEGRATION_SOURCE_VERSION_VALUE,
            }
        )
    )
    logger_provider = LoggerProvider(resource=resource)
    setup_log_exporter(logger_provider, exporter_config)
    return logger_provider.get_logger(EVALUATION_LOGGER_NAME)
