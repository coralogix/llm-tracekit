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
from typing import Any, Dict, List, Mapping, Optional, Union
from urllib.parse import urlparse

from httpx import URL
from openai import NOT_GIVEN
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion import Choice as OpenAIChoice
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
)
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.semconv._incubating.attributes import (
    server_attributes as ServerAttributes,
)

from llm_tracekit import extended_gen_ai_attributes as ExtendedGenAIAttributes
from llm_tracekit.span_builder import (
    Choice,
    Message,
    ToolCall,
    attribute_generator,
    generate_base_attributes,
    generate_choice_attributes,
    generate_message_attributes,
    generate_request_attributes,
    generate_response_attributes,
)


def parse_tool_calls(
    tool_calls: Optional[
        Union[List[Dict[str, Any]], List[ChatCompletionMessageToolCall]]
    ],
) -> Optional[List[ToolCall]]:
    if tool_calls is None:
        return None

    parsed_tool_calls = []

    for tool_call in tool_calls:
        function_name = None
        arguments = None
        func = get_property_value(tool_call, "function")
        if func is not None:
            function_name = get_property_value(func, "name")
            arguments = get_property_value(func, "arguments")
            if isinstance(arguments, str):
                arguments = arguments.replace("\n", "")

        parsed_tool_calls.append(
            ToolCall(
                id=get_property_value(tool_call, "id"),
                type=get_property_value(tool_call, "type"),
                function_name=function_name,
                function_arguments=arguments,
            )
        )

    return parsed_tool_calls


def generate_server_address_and_port_attributes(client_instance) -> Dict[str, Any]:
    base_client = getattr(client_instance, "_client", None)
    base_url = getattr(base_client, "base_url", None)
    if not base_url:
        return {}

    host = None
    port: Optional[int] = -1
    if isinstance(base_url, URL):
        host = base_url.host
        port = base_url.port
    elif isinstance(base_url, str):
        url = urlparse(base_url)
        host = url.hostname
        port = url.port

    attributes: Dict[str, Any] = {ServerAttributes.SERVER_ADDRESS: host}
    if port and port != 443 and port > 0:
        attributes[ServerAttributes.SERVER_PORT] = port

    return attributes


def get_property_value(obj, property_name):
    if isinstance(obj, dict):
        return obj.get(property_name, None)

    return getattr(obj, property_name, None)


def messages_to_span_attributes(
    messages: list, capture_content: bool
) -> Dict[str, Any]:
    parsed_messages = []
    for message in messages:
        content = get_property_value(message, "content")
        if not isinstance(content, str):
            content = None

        tool_calls = parse_tool_calls(get_property_value(message, "tool_calls"))

        parsed_messages.append(
            Message(
                role=get_property_value(message, "role"),
                content=content,
                tool_call_id=get_property_value(message, "tool_call_id"),
                tool_calls=tool_calls,
            )
        )

    return generate_message_attributes(
        messages=parsed_messages, capture_content=capture_content
    )


def choices_to_span_attributes(
    choices: List[OpenAIChoice], capture_content
) -> Dict[str, Any]:
    parsed_choices = []
    for choice in choices:
        role = None
        content = None
        tool_calls = None
        if choice.message:
            role = choice.message.role
            content = choice.message.content
            tool_calls = parse_tool_calls(choice.message.tool_calls)

        parsed_choices.append(
            Choice(
                finish_reason=choice.finish_reason or "error",
                role=role,
                content=content,
                tool_calls=tool_calls,
            )
        )

    return generate_choice_attributes(choices=parsed_choices, capture_content=capture_content)


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


@attribute_generator
def get_llm_request_attributes(kwargs, client_instance, capture_content: bool):
    attributes = {
        **generate_base_attributes(system=GenAIAttributes.GenAiSystemValues.OPENAI),
        **generate_request_attributes(
            model=kwargs.get("model"),
            temperature=kwargs.get("temperature"),
            top_p=kwargs.get("p") or kwargs.get("top_p"),
            max_tokens=kwargs.get("max_tokens"),
            presence_penalty=kwargs.get("presence_penalty"),
            frequency_penalty=kwargs.get("frequency_penalty"),
        ),
        **messages_to_span_attributes(
            messages=kwargs.get("messages", []), capture_content=capture_content
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

    attributes.update(generate_server_address_and_port_attributes(client_instance))
    service_tier = kwargs.get("service_tier")
    if service_tier != "auto":
        attributes[GenAIAttributes.GEN_AI_OPENAI_RESPONSE_SERVICE_TIER] = service_tier

    return attributes


@attribute_generator
def get_llm_response_attributes(
    result: ChatCompletion, capture_content: bool
) -> Dict[str, Any]:
    finish_reasons = None
    if result.choices is not None:
        finish_reasons = []
        for choice in result.choices:
            finish_reasons.append(choice.finish_reason or "error")

    usage_input_tokens = None
    usage_output_tokens = None
    if result.usage is not None:
        usage_input_tokens = result.usage.prompt_tokens
        usage_output_tokens = result.usage.completion_tokens

    return {
        GenAIAttributes.GEN_AI_OPENAI_REQUEST_SERVICE_TIER: result.service_tier,
        **generate_response_attributes(
            model=result.model,
            finish_reasons=finish_reasons,
            id=result.id,
            usage_input_tokens=usage_input_tokens,
            usage_output_tokens=usage_output_tokens,
        ),
        **choices_to_span_attributes(result.choices, capture_content),
    }
