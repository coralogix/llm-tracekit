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
import brotli

from llm_tracekit.instrumentation_utils import (
    OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT,
)
from llm_tracekit.litellm.instrumentor import LiteLLMInstrumentor


@pytest.fixture(autouse=True)
def litellm_env_vars():
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "test_openai_api_key"


def handle_request(request):
    if 'cookie' in request.headers:
        request.headers['cookie'] = 'redacted_cookie'
    if 'openai-organization' in request.headers:
        request.headers['openai-organization'] = 'test_organization'
    if 'openai-project' in request.headers:
        request.headers['openai-project'] = 'test_project'
    return request


def handle_response(response):
    """
    Remove sensitive headers and fix brotli decoding issue by manually decoding the body
    """
    headers = response.get('headers', {})
    if 'Set-Cookie' in response['headers']:
        response['headers']['Set-Cookie'] = ['redacted_set_cookie']
    if 'openai-organization' in response['headers']:
        response['headers']['openai-organization'] = ['test_openai_org_id']
    if 'openai-project' in response['headers']:
        response['headers']['openai-project'] = ['test_openai_project']
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
            "openai-organization",
            "openai-project"
        ],
        "decode_compressed_response": True,
        "before_record_request": handle_request,
        "before_record_response": handle_response,
    }

@pytest.fixture(scope="module")
def instrument():
    os.environ.update({OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT: "True"})
    os.environ.update({"OTEL_EXPORTER_OTLP_PROTOCOL": "in_memory"})
    os.environ.update({"OTEL_EXPORTER": "in_memory"})
    

    instrumentor = LiteLLMInstrumentor()
    instrumentor.instrument()

    yield instrumentor

    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
    os.environ.pop("OTEL_EXPORTER_OTLP_PROTOCOL", None)
    os.environ.pop("OTEL_EXPORTER", None)
    instrumentor.uninstrument()