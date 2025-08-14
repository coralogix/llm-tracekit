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

try:
    from llm_tracekit.openai_agents.instrumentor import OpenAIAgentsInstrumentor
except (ImportError, ModuleNotFoundError):
    pytest.skip("OpenAI agents not available (requires Python 3.10+)", allow_module_level=True)
    
from llm_tracekit.instrumentation_utils import (
    OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT,
)


@pytest.fixture(autouse=True)
def openai_env_vars():
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "test_openai_api_key"

@pytest.fixture(scope="function")
def instrument(tracer_provider, meter_provider):
    os.environ.update({OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT: "True"})
    instrumentor = OpenAIAgentsInstrumentor()
    
    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    yield instrumentor
    os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
    instrumentor.uninstrument()

def handle_request_cookies(request):
    if 'cookie' in request.headers:
        request.headers['cookie'] = 'redacted_cookie'
    if 'openai-organization' in request.headers:
        request.headers['openai-organization'] = 'test_organization'
    if 'openai-project' in request.headers:
        request.headers['openai-project'] = 'test_project'
    return request

def handle_response_cookies(response):
    if 'Set-Cookie' in response['headers']:
        response['headers']['Set-Cookie'] = ['redacted_set_cookie']
    if 'openai-organization' in response['headers']:
        response['headers']['openai-organization'] = ['test_openai_org_id']
    if 'openai-project' in response['headers']:
        response['headers']['openai-project'] = ['test_openai_project']
    return response

@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": [
            "authorization",
            "Idempotency-Key",
            "x-stainless-arch",
            "x-stainless-lang",
            "x-stainless-os",
            "x-stainless-package-version",
            "x-stainless-runtime",
            "x-stainless-runtime-version",
            "user-agent",
        ],
        "decode_compressed_response": True,
        "before_record_request": handle_request_cookies,
        "before_record_response": handle_response_cookies,
    }