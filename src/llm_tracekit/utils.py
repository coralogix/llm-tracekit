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

import json
from os import environ
from typing import Any, Mapping, Optional, Union
from urllib.parse import urlparse

from httpx import URL
from openai import NOT_GIVEN
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.semconv._incubating.attributes import (
    server_attributes as ServerAttributes,
)
from opentelemetry.semconv.attributes import (
    error_attributes as ErrorAttributes,
)
from opentelemetry.trace.status import Status, StatusCode

from . import extended_gen_ai_attributes as ExtendedGenAIAttributes

OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT = (
    "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
)


def is_content_enabled() -> bool:
    capture_content = environ.get(
        OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, "false"
    )

    return capture_content.lower() == "true"


def get_tool_call_attributes(item, capture_content: bool, base_path: str) -> dict:
    attributes = {}

    tool_calls = get_property_value(item, "tool_calls")
    if tool_calls is None:
        return {}

    for index, tool_call in enumerate(tool_calls):
        call_id = get_property_value(tool_call, "id")
        if call_id:
            attributes[f"{base_path}.tool_calls.{index}.id"] = call_id

        tool_type = get_property_value(tool_call, "type")
        if tool_type:
            attributes[f"{base_path}.tool_calls.{index}.type"] = tool_type

        func = get_property_value(tool_call, "function")
        if func:
            name = get_property_value(func, "name")
            if name:
                attributes[f"{base_path}.tool_calls.{index}.function.name"] = name

            arguments = get_property_value(func, "arguments")
            if capture_content and arguments:
                if isinstance(arguments, str):
                    arguments = arguments.replace("\n", "")

                attributes[f"{base_path}.tool_calls.{index}.function.arguments"] = (
                    arguments
                )

    return attributes


def set_server_address_and_port(client_instance, attributes):
    base_client = getattr(client_instance, "_client", None)
    base_url = getattr(base_client, "base_url", None)
    if not base_url:
        return

    port = -1
    if isinstance(base_url, URL):
        attributes[ServerAttributes.SERVER_ADDRESS] = base_url.host
        port = base_url.port
    elif isinstance(base_url, str):
        url = urlparse(base_url)
        attributes[ServerAttributes.SERVER_ADDRESS] = url.hostname
        port = url.port

    if port and port != 443 and port > 0:
        attributes[ServerAttributes.SERVER_PORT] = port


def get_property_value(obj, property_name):
    if isinstance(obj, dict):
        return obj.get(property_name, None)

    return getattr(obj, property_name, None)


def messages_to_span_attributes(
    messages: list, capture_content: bool
) -> Mapping[str, Any]:
    span_attributes = {}

    for index, message in enumerate(messages):
        role = get_property_value(message, "role")
        span_attributes[
            ExtendedGenAIAttributes.GEN_AI_PROMPT_ROLE.format(prompt_index=index)
        ] = role

        content = get_property_value(message, "content")
        if capture_content and isinstance(content, str) and content:
            span_attributes[
                ExtendedGenAIAttributes.GEN_AI_PROMPT_CONTENT.format(prompt_index=index)
            ] = content
        if role == "assistant":
            tool_call_attributes = get_tool_call_attributes(
                message, capture_content, f"gen_ai.prompt.{index}"
            )
            span_attributes.update(tool_call_attributes)
        elif role == "tool":
            tool_call_id = get_property_value(message, "tool_call_id")
            if tool_call_id:
                span_attributes[
                    ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALL_ID.format(
                        prompt_index=index
                    )
                ] = tool_call_id

    return span_attributes


def choices_to_span_attributes(choices: list, capture_content) -> Mapping[str, Any]:
    span_attributes = {}

    for index, choice in enumerate(choices):
        span_attributes[
            ExtendedGenAIAttributes.GEN_AI_COMPLETION_FINISH_REASON.format(
                completion_index=index
            )
        ] = choice.finish_reason or "error"

        if choice.message:
            role = choice.message.role if choice.message.role else None
            span_attributes[
                ExtendedGenAIAttributes.GEN_AI_COMPLETION_ROLE.format(
                    completion_index=index
                )
            ] = role

            tool_call_attributes = get_tool_call_attributes(
                choice.message, capture_content, f"gen_ai.completion.{index}"
            )
            span_attributes.update(tool_call_attributes)

            content = get_property_value(choice.message, "content")
            if capture_content and content:
                span_attributes[
                    ExtendedGenAIAttributes.GEN_AI_COMPLETION_CONTENT.format(
                        completion_index=index
                    )
                ] = content

    return span_attributes


def set_span_attributes(span, attributes: dict):
    for field, value in attributes.items():
        set_span_attribute(span, field, value)


def set_span_attribute(span, name, value):
    if non_numerical_value_is_set(value) is False:
        return

    span.set_attribute(name, value)


def is_streaming(kwargs):
    return non_numerical_value_is_set(kwargs.get("stream"))


def non_numerical_value_is_set(value: Optional[Union[bool, str]]):
    return bool(value) and value != NOT_GIVEN


def get_llm_request_attributes(
    kwargs,
    client_instance,
    operation_name=GenAIAttributes.GenAiOperationNameValues.CHAT.value,
):
    attributes = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: operation_name,
        GenAIAttributes.GEN_AI_SYSTEM: GenAIAttributes.GenAiSystemValues.OPENAI.value,
        GenAIAttributes.GEN_AI_REQUEST_MODEL: kwargs.get("model"),
        GenAIAttributes.GEN_AI_REQUEST_TEMPERATURE: kwargs.get("temperature"),
        GenAIAttributes.GEN_AI_REQUEST_TOP_P: kwargs.get("p") or kwargs.get("top_p"),
        GenAIAttributes.GEN_AI_REQUEST_MAX_TOKENS: kwargs.get("max_tokens"),
        GenAIAttributes.GEN_AI_REQUEST_PRESENCE_PENALTY: kwargs.get("presence_penalty"),
        GenAIAttributes.GEN_AI_REQUEST_FREQUENCY_PENALTY: kwargs.get(
            "frequency_penalty"
        ),
        GenAIAttributes.GEN_AI_OPENAI_REQUEST_SEED: kwargs.get("seed"),
        ExtendedGenAIAttributes.GEN_AI_OPENAI_REQUEST_USER: kwargs.get("user"),
    }

    response_format = kwargs.get("response_format")
    if response_format is not None:
        # response_format may be string or object with a string in the `type` key
        if isinstance(response_format, Mapping):
            response_format_type = response_format.get("type")
            if response_format_type is not None:
                attributes[GenAIAttributes.GEN_AI_OPENAI_REQUEST_RESPONSE_FORMAT] = (
                    response_format_type
                )
        else:
            attributes[GenAIAttributes.GEN_AI_OPENAI_REQUEST_RESPONSE_FORMAT] = (
                response_format
            )

    tools = kwargs.get("tools")
    if tools is not None and isinstance(tools, list):
        for index, tool in enumerate(tools):
            if not isinstance(tool, Mapping):
                continue

            attributes[
                ExtendedGenAIAttributes.GEN_AI_OPENAI_REQUEST_TOOLS_TYPE.format(
                    tool_index=index
                )
            ] = tool.get("type", "function")
            function = tool.get("function")
            if function is not None and isinstance(function, Mapping):
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_OPENAI_REQUEST_TOOLS_FUNCTION_NAME.format(
                        tool_index=index
                    )
                ] = function.get("name")
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_OPENAI_REQUEST_TOOLS_FUNCTION_DESCRIPTION.format(
                        tool_index=index
                    )
                ] = function.get("description")
                function_parameters = function.get("parameters")
                if function_parameters is not None:
                    attributes[
                        ExtendedGenAIAttributes.GEN_AI_OPENAI_REQUEST_TOOLS_FUNCTION_PARAMETERS.format(
                            tool_index=index
                        )
                    ] = json.dumps(function_parameters)

    set_server_address_and_port(client_instance, attributes)
    service_tier = kwargs.get("service_tier")
    attributes[GenAIAttributes.GEN_AI_OPENAI_RESPONSE_SERVICE_TIER] = (
        service_tier if service_tier != "auto" else None
    )

    # filter out None values
    return {k: v for k, v in attributes.items() if v is not None}


def handle_span_exception(span, error):
    span.set_status(Status(StatusCode.ERROR, str(error)))
    if span.is_recording():
        span.set_attribute(ErrorAttributes.ERROR_TYPE, type(error).__qualname__)
    span.end()
