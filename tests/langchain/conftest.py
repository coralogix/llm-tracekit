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
import base64

import pytest
import brotli

from llm_tracekit.instrumentation_utils import (
    OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT,
)
from llm_tracekit.langchain.instrumentor import LangChainInstrumentor

EVENT_STREAM_CT = "application/vnd.amazon.eventstream"


@pytest.fixture(autouse=True)
def langchain_env_vars():
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "test_openai_api_key"
    if not os.getenv("AWS_ACCESS_KEY_ID"):
        os.environ["AWS_ACCESS_KEY_ID"] = "test_aws_access_key"
    if not os.getenv("AWS_SECRET_ACCESS_KEY"):
        os.environ["AWS_SECRET_ACCESS_KEY"] = "test_aws_secret"


def handle_response(response):
    headers = response["headers"]
    headers["openai-organization"] = "test_openai_org_id"
    headers["openai-project"] = "test_openai_project"
    headers["Set-Cookie"] = "redacted_set_cookie"
    if 'Content-Encoding' in headers and 'br' in headers['Content-Encoding']:
        body = response.get('body', {}).get('string')
        if body and isinstance(body, bytes):
            try:
                decoded_body = brotli.decompress(body)
                response['body']['string'] = decoded_body
                del headers['Content-Encoding']
                
            except brotli.error:
                pass
    return response


def handle_recording_boto_response(response: dict) -> dict:
    headers = response["headers"]
    if headers.get("x-vcr-base64") == ["yes"]:
        response["body"]["string"] = base64.b64decode(response["body"]["string"])
        headers.pop("x-vcr-base64")
        return response

    content_type = (headers.get("Content-Type") or [""])[0]
    if EVENT_STREAM_CT in content_type:
        raw = response["body"]["string"]
        response["body"]["string"] = base64.b64encode(raw).decode()
        headers["x-vcr-base64"] = ["yes"]

    response["headers"]["Content-Length"] = [str(len(response["body"]["string"]))]
    return response


def before_record_response(response):
    response = handle_response(response)
    return handle_recording_boto_response(response)


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
            "x-stainless-arch",
            "x-stainless-os",
            "x-stainless-package-version",
            "x-stainless-runtime-version",
            "Set-Cookie",
            "cookie",
            "openai-organization",
            "openai-project",
            "x-amz-security-token",
        ],
        "decode_compressed_response": True,
        "before_record_response": before_record_response,
    }

@pytest.fixture(scope="function")
def instrument_langchain(tracer_provider, meter_provider):
    os.environ[OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT] = "True"
    os.environ.update({"OTEL_EXPORTER_OTLP_PROTOCOL": "in_memory"})
    os.environ.update({"OTEL_EXPORTER": "in_memory"})

    instrumentor = LangChainInstrumentor()
    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    yield instrumentor

    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
    os.environ.pop("OTEL_EXPORTER_OTLP_PROTOCOL", None)
    os.environ.pop("OTEL_EXPORTER", None)
    instrumentor.uninstrument()
