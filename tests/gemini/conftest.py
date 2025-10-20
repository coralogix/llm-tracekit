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
import pytest

from llm_tracekit.instrumentation_utils import (
    OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT,
)
from llm_tracekit.gemini.instrumentor import GeminiInstrumentor


@pytest.fixture(autouse=True)
def gemini_env_vars():
    if not os.getenv("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = "test_gemini_api_key"


def handle_request(request):
    if 'cookie' in request.headers:
        request.headers['cookie'] = 'redacted_cookie'
    if 'x-goog-api-key' in request.headers:
        request.headers['x-goog-api-key'] = 'redacted_x_goog_api_key'
    return request


def handle_response(response):
    """
    Remove sensitive headers
    """
    if 'Set-Cookie' in response['headers']:
        response['headers']['Set-Cookie'] = ['redacted_set_cookie']
    return response


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": [
            "authorization",
            "accept-encoding",
            "content-length",
            "user-agent",
            "x-stainless-retry-count",
            "x-stainless-async",
            "x-stainless-raw-response",
            "x-stainless-read-timeout",
            'x-stainless-arch',
            'x-stainless-os',
            'x-stainless-package-version',
            'x-stainless-runtime-version',
            "Set-Cookie",
        ],
        "decode_compressed_response": True,
        "before_record_request": handle_request,
        "before_record_response": handle_response,
    }

@pytest.fixture(scope="function")
def instrument(tracer_provider, meter_provider):
    os.environ.update({OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT: "True"})
    os.environ.update({"OTEL_EXPORTER_OTLP_PROTOCOL": "in_memory"})
    os.environ.update({"OTEL_EXPORTER": "in_memory"})
    

    instrumentor = GeminiInstrumentor()
    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    yield instrumentor

    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
    os.environ.pop("OTEL_EXPORTER_OTLP_PROTOCOL", None)
    os.environ.pop("OTEL_EXPORTER", None)
    instrumentor.uninstrument()