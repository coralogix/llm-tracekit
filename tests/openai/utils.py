# Copyright The OpenTelemetry Authors
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

from typing import Optional

from openai.types.chat import ChatCompletion
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.semconv._incubating.attributes import (
    server_attributes as ServerAttributes,
)


def assert_completion_attributes(
    span: ReadableSpan,
    request_model: str,
    response: ChatCompletion,
    operation_name: str = "chat",
    server_address: str = "api.openai.com",
):
    return assert_all_attributes(
        span,
        request_model,
        response.id,
        response.model,
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
        operation_name,
        server_address,
    )


def assert_all_attributes(
    span: ReadableSpan,
    request_model: str,
    response_id: str = None,
    response_model: str = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    operation_name: str = "chat",
    server_address: str = "api.openai.com",
):
    assert span.name == f"{operation_name} {request_model}"
    assert operation_name == span.attributes[GenAIAttributes.GEN_AI_OPERATION_NAME]
    assert (
        GenAIAttributes.GenAiSystemValues.OPENAI.value
        == span.attributes[GenAIAttributes.GEN_AI_SYSTEM]
    )
    assert request_model == span.attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL]
    if response_model:
        assert response_model == span.attributes[GenAIAttributes.GEN_AI_RESPONSE_MODEL]
    else:
        assert GenAIAttributes.GEN_AI_RESPONSE_MODEL not in span.attributes

    if response_id:
        assert response_id == span.attributes[GenAIAttributes.GEN_AI_RESPONSE_ID]
    else:
        assert GenAIAttributes.GEN_AI_RESPONSE_ID not in span.attributes

    if input_tokens is not None:
        assert (
            input_tokens == span.attributes[GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS]
        )
    else:
        assert GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS not in span.attributes

    if output_tokens is not None:
        assert (
            output_tokens == span.attributes[GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS]
        )
    else:
        assert GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS not in span.attributes

    assert server_address == span.attributes[ServerAttributes.SERVER_ADDRESS]


def get_current_weather_tool_definition():
    return {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. Boston, MA",
                    },
                },
                "required": ["location"],
                "additionalProperties": False,
            },
        },
    }
