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

from opentelemetry.semconv.attributes import (
    error_attributes as ErrorAttributes,
)
from opentelemetry.trace.status import Status, StatusCode

OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT = (
    "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
)


def is_content_enabled() -> bool:
    """Checks if capturing message content is enabled."""
    capture_content = os.environ.get(
        OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, "false"
    )

    return capture_content.lower() == "true"


def enable_capture_content():
    """Enables capturing message content."""
    os.environ[OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT] = "true"


def handle_span_exception(span, error):
    span.set_status(Status(StatusCode.ERROR, str(error)))
    if span.is_recording():
        span.set_attribute(ErrorAttributes.ERROR_TYPE, type(error).__qualname__)
    span.end()
