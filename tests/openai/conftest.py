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
from openai import AsyncOpenAI, OpenAI
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF

from llm_tracekit.instrumentation_utils import (
    OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT,
)
from llm_tracekit.openai.instrumentor import OpenAIInstrumentor


@pytest.fixture(autouse=True)
def openai_env_vars():
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "test_openai_api_key"


@pytest.fixture
def openai_client():
    return OpenAI()


@pytest.fixture
def async_openai_client():
    return AsyncOpenAI()


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": [
            ("cookie", "test_cookie"),
            ("authorization", "Bearer test_openai_api_key"),
            ("openai-organization", "test_openai_org_id"),
            ("openai-project", "test_openai_project_id"),
        ],
        "decode_compressed_response": True,
        "before_record_response": scrub_response_headers,
    }


@pytest.fixture(scope="function")
def instrument_no_content(tracer_provider, meter_provider):
    os.environ.update({OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT: "False"})

    instrumentor = OpenAIInstrumentor()
    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    yield instrumentor
    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
    instrumentor.uninstrument()


@pytest.fixture(scope="function")
def instrument_with_content(tracer_provider, meter_provider):
    os.environ.update({OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT: "True"})
    instrumentor = OpenAIInstrumentor()
    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    yield instrumentor
    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
    instrumentor.uninstrument()


@pytest.fixture(scope="function")
def instrument_with_content_unsampled(span_exporter, meter_provider):
    os.environ.update({OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT: "True"})

    tracer_provider = TracerProvider(sampler=ALWAYS_OFF)
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))

    instrumentor = OpenAIInstrumentor()
    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    yield instrumentor
    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
    instrumentor.uninstrument()


def scrub_response_headers(response):
    """
    This scrubs sensitive response headers. Note they are case-sensitive!
    """
    response["headers"]["openai-organization"] = "test_openai_org_id"
    response["headers"]["Set-Cookie"] = "test_set_cookie"
    return response
