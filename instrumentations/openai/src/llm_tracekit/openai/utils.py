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
from typing import Any, Mapping
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

from llm_tracekit.core import (
    ToolCall,
    Message,
    Choice,
    attribute_generator,
    generate_base_attributes,
    generate_message_attributes,
    generate_choice_attributes,
    generate_request_attributes,
    generate_response_attributes,
    _extended_gen_ai_attributes as ExtendedGenAIAttributes,
)


def parse_tool_calls(
    tool_calls: list[dict[str, Any] | ChatCompletionMessageToolCall] | None,
) -> list[ToolCall] | None:
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


def generate_server_address_and_port_attributes(client_instance) -> dict[str, Any]:
    base_client = getattr(client_instance, "_client", None)
    base_url = getattr(base_client, "base_url", None)
    if not base_url:
        return {}

    host = None
    port: int | None = -1
    if isinstance(base_url, URL):
        host = base_url.host
        port = base_url.port
    elif isinstance(base_url, str):
        url = urlparse(base_url)
        host = url.hostname
        port = url.port

    attributes: dict[str, Any] = {ServerAttributes.SERVER_ADDRESS: host}
    if port and port != 443 and port > 0:
        attributes[ServerAttributes.SERVER_PORT] = port

    return attributes


def get_property_value(obj, property_name):
    if isinstance(obj, dict):
        return obj.get(property_name, None)

    return getattr(obj, property_name, None)


def messages_to_span_attributes(
    messages: list, capture_content: bool
) -> dict[str, Any]:
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
    choices: list[OpenAIChoice], capture_content
) -> dict[str, Any]:
    parsed_choices = []
    for choice in choices:
        role = None
        content = None
        tool_calls = None
        if choice.message:
            role = choice.message.role
            content = choice.message.content
            tool_calls = parse_tool_calls(choice.message.tool_calls)  # type: ignore

        parsed_choices.append(
            Choice(
                finish_reason=choice.finish_reason or "error",
                role=role,
                content=content,
                tool_calls=tool_calls,
            )
        )

    return generate_choice_attributes(
        choices=parsed_choices, capture_content=capture_content
    )


def set_span_attributes(span, attributes: dict):
    for field, value in attributes.items():
        set_span_attribute(span, field, value)


def set_span_attribute(span, name, value):
    if non_numerical_value_is_set(value) is False:
        return

    span.set_attribute(name, value)


def is_streaming(kwargs):
    return non_numerical_value_is_set(kwargs.get("stream"))


def non_numerical_value_is_set(value: bool | str | None):
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
        ExtendedGenAIAttributes.GEN_AI_REQUEST_USER: kwargs.get("user"),
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
                ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_TYPE.format(
                    tool_index=index
                )
            ] = tool.get("type", "function")
            function = tool.get("function")
            if function is not None and isinstance(function, Mapping):
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_NAME.format(
                        tool_index=index
                    )
                ] = function.get("name")
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_DESCRIPTION.format(
                        tool_index=index
                    )
                ] = function.get("description")
                function_parameters = function.get("parameters")
                if function_parameters is not None:
                    attributes[
                        ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_PARAMETERS.format(
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
) -> dict[str, Any]:
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


def _embedding_input_to_prompt_messages(
    embedding_input: Any,
) -> list[Message]:
    """Convert embeddings input to prompt messages."""

    def to_message(content: str | None) -> Message:
        return Message(role="user", content=content)

    if embedding_input is None:
        return []

    if isinstance(embedding_input, str):
        return [to_message(embedding_input)]

    if isinstance(embedding_input, list):
        messages: list[Message] = []
        for item in embedding_input:
            if isinstance(item, str):
                messages.append(to_message(item))
            else:
                messages.append(to_message(None))
        return messages

    return [to_message(None)]


@attribute_generator
def get_embedding_request_attributes(
    kwargs: dict[str, Any],
    client_instance,
    capture_content: bool,
) -> dict[str, Any]:
    """
    Build span attributes for `client.embeddings.create(...)`.
    """

    attributes: dict[str, Any] = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: "embeddings",
        GenAIAttributes.GEN_AI_SYSTEM: GenAIAttributes.GenAiSystemValues.OPENAI.value,
        GenAIAttributes.GEN_AI_REQUEST_MODEL: kwargs.get("model"),
        ExtendedGenAIAttributes.GEN_AI_REQUEST_USER: kwargs.get("user"),
    }

    encoding_format = kwargs.get("encoding_format")
    if encoding_format and encoding_format is not NOT_GIVEN:
        attributes[ExtendedGenAIAttributes.GEN_AI_REQUEST_ENCODING_FORMATS] = (
            encoding_format,
        )
    else:
        attributes[ExtendedGenAIAttributes.GEN_AI_REQUEST_ENCODING_FORMATS] = ("float",)

    dimensions = kwargs.get("dimensions")
    if dimensions and dimensions is not NOT_GIVEN:
        attributes[ExtendedGenAIAttributes.GEN_AI_EMBEDDINGS_DIMENSION_COUNT] = (
            dimensions
        )

    embedding_input = kwargs.get("input")
    prompt_messages = _embedding_input_to_prompt_messages(embedding_input)
    attributes.update(
        generate_message_attributes(
            messages=prompt_messages, capture_content=capture_content
        )
    )

    attributes.update(generate_server_address_and_port_attributes(client_instance))
    return attributes


@attribute_generator
def get_embedding_response_attributes(
    result: Any, capture_content: bool = False
) -> dict[str, Any]:
    usage = getattr(result, "usage", None)
    usage_input_tokens = None
    if usage is not None:
        usage_input_tokens = getattr(usage, "prompt_tokens", None) or getattr(
            usage, "total_tokens", None
        )

    attributes: dict[str, Any] = {
        **generate_response_attributes(
            model=getattr(result, "model", None),
            id=getattr(result, "id", None),
            usage_input_tokens=usage_input_tokens,
            usage_output_tokens=None,
            finish_reasons=None,
        ),
    }

    if capture_content:
        data = getattr(result, "data", None)
        if data:
            for item in data:
                index = getattr(item, "index", None)
                embedding = getattr(item, "embedding", None)
                if index is not None and embedding is not None:
                    attributes[
                        ExtendedGenAIAttributes.GEN_AI_EMBEDDING_VECTOR.format(
                            embedding_index=index
                        )
                    ] = embedding

    return attributes


def _responses_input_content_part_to_text(part: Any) -> str | None:
    """Extract text from a Responses API input content part (dict or object)."""
    if part is None:
        return None
    ptype = get_property_value(part, "type")
    if ptype in ("input_text", "output_text", "text"):
        text = get_property_value(part, "text")
        if isinstance(text, str):
            return text
    return None


def _responses_normalize_input_content(content: Any) -> str | None:
    """Normalize Responses `input` message content to a single string for span attrs."""
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            t = _responses_input_content_part_to_text(part)
            if t:
                parts.append(t)
        return "".join(parts) if parts else None
    return _responses_input_content_part_to_text(content)


def _responses_function_call_output_to_text(output: Any) -> str | None:
    if output is None:
        return None
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            t = _responses_input_content_part_to_text(item)
            if t:
                parts.append(t)
        return "".join(parts) if parts else None
    return None


def _map_responses_role(role: str | None) -> str | None:
    if role in ("developer", "system"):
        return "system"
    if role == "assistant":
        return "assistant"
    if role == "user":
        return "user"
    return role


def _responses_input_item_to_message(item: Any) -> Message | None:
    """Convert one Responses input list item to a Message, if recognized."""
    if item is None:
        return None
    item_type = get_property_value(item, "type")
    if item_type == "message":
        role = _map_responses_role(get_property_value(item, "role"))
        content = _responses_normalize_input_content(
            get_property_value(item, "content")
        )
        return Message(role=role, content=content)
    if item_type == "function_call_output":
        out = _responses_function_call_output_to_text(
            get_property_value(item, "output")
        )
        call_id = get_property_value(item, "call_id")
        return Message(role="tool", content=out, tool_call_id=call_id)
    return None


def _responses_input_to_messages(
    input_value: Any,
    instructions: str | None,
) -> list[Message]:
    """Build prompt messages from Responses `instructions` and `input` parameters."""
    messages: list[Message] = []
    if instructions:
        messages.append(Message(role="system", content=instructions))
    if input_value is None or input_value is NOT_GIVEN:
        return messages
    if isinstance(input_value, str):
        messages.append(Message(role="user", content=input_value))
        return messages
    if isinstance(input_value, list):
        for item in input_value:
            msg = _responses_input_item_to_message(item)
            if msg is not None:
                messages.append(msg)
        return messages
    return messages


def _responses_tool_item_to_attributes(tool: Any, index: int) -> dict[str, Any]:
    """Map one Responses tool to gen_ai.request.tools.* attributes."""
    attributes: dict[str, Any] = {}
    if hasattr(tool, "model_dump") and callable(getattr(tool, "model_dump")):
        tool = tool.model_dump(mode="python")
    if not isinstance(tool, Mapping):
        return attributes

    tool_type = tool.get("type")
    if tool_type is None:
        tool_type = "function"

    nested_fn = tool.get("function")
    if isinstance(nested_fn, Mapping):
        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_TYPE.format(tool_index=index)
        ] = tool_type or "function"
        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_NAME.format(
                tool_index=index
            )
        ] = nested_fn.get("name")
        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_DESCRIPTION.format(
                tool_index=index
            )
        ] = nested_fn.get("description")
        params = nested_fn.get("parameters")
        if params is not None:
            attributes[
                ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_PARAMETERS.format(
                    tool_index=index
                )
            ] = json.dumps(params)
        return attributes

    attributes[
        ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_TYPE.format(tool_index=index)
    ] = tool_type
    name = tool.get("name")
    if name is not None:
        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_NAME.format(
                tool_index=index
            )
        ] = name
    desc = tool.get("description")
    if desc is not None:
        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_DESCRIPTION.format(
                tool_index=index
            )
        ] = desc
    elif tool_type not in (None, "function") and name is None:
        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_NAME.format(
                tool_index=index
            )
        ] = str(tool_type)
        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_DESCRIPTION.format(
                tool_index=index
            )
        ] = str(tool_type)
    params = tool.get("parameters")
    if params is not None:
        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_PARAMETERS.format(
                tool_index=index
            )
        ] = json.dumps(params)
    return attributes


def _response_status_to_finish_reason(response: Any) -> str:
    status = getattr(response, "status", None)
    if status == "completed":
        return "stop"
    if status == "incomplete":
        details = getattr(response, "incomplete_details", None)
        reason = getattr(details, "reason", None) if details is not None else None
        return str(reason) if reason else "incomplete"
    if status == "failed":
        return "error"
    if status == "cancelled":
        return "cancelled"
    if status in ("in_progress", "queued"):
        return str(status)
    if getattr(response, "error", None) is not None:
        return "error"
    return str(status) if status else "error"


def _responses_output_text_from_message(msg: Any) -> str | None:
    content = get_property_value(msg, "content")
    if not content:
        return None
    parts: list[str] = []
    for block in content:
        btype = get_property_value(block, "type")
        if btype == "output_text":
            text = get_property_value(block, "text")
            if isinstance(text, str):
                parts.append(text)
        elif btype == "refusal":
            ref = get_property_value(block, "refusal")
            if isinstance(ref, str):
                parts.append(ref)
    return "".join(parts) if parts else None


def _responses_output_to_choice(response: Any) -> Choice:
    output = getattr(response, "output", None) or []
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for item in output:
        item_type = get_property_value(item, "type")
        if item_type == "message":
            text = _responses_output_text_from_message(item)
            if text:
                text_parts.append(text)
        elif item_type == "function_call":
            call_id = get_property_value(item, "call_id") or get_property_value(
                item, "id"
            )
            name = get_property_value(item, "name")
            arguments = get_property_value(item, "arguments")
            if isinstance(arguments, str):
                arguments = arguments.replace("\n", "")
            tool_calls.append(
                ToolCall(
                    id=call_id,
                    type="function",
                    function_name=name,
                    function_arguments=arguments,
                )
            )
    content = "".join(text_parts) if text_parts else None
    finish = _response_status_to_finish_reason(response)
    if tool_calls and finish == "stop":
        finish = "tool_calls"
    return Choice(
        finish_reason=finish,
        role="assistant",
        content=content,
        tool_calls=tool_calls if tool_calls else None,
    )


@attribute_generator
def get_responses_request_attributes(
    kwargs: dict[str, Any],
    client_instance: Any,
    capture_content: bool,
) -> dict[str, Any]:
    """Build span attributes for `client.responses.create` / `parse`."""
    instructions = kwargs.get("instructions")
    if instructions is NOT_GIVEN:
        instructions = None
    input_val = kwargs.get("input")
    if input_val is NOT_GIVEN:
        input_val = None

    prompt_messages = _responses_input_to_messages(input_val, instructions)
    attributes: dict[str, Any] = {
        **generate_base_attributes(system=GenAIAttributes.GenAiSystemValues.OPENAI),
        **generate_request_attributes(
            model=kwargs.get("model"),
            temperature=kwargs.get("temperature"),
            top_p=kwargs.get("top_p"),
            max_tokens=kwargs.get("max_output_tokens"),
            presence_penalty=None,
            frequency_penalty=None,
        ),
        **generate_message_attributes(
            messages=prompt_messages, capture_content=capture_content
        ),
        ExtendedGenAIAttributes.GEN_AI_REQUEST_USER: kwargs.get("user"),
    }

    tools = kwargs.get("tools")
    if tools is not None and tools is not NOT_GIVEN:
        if isinstance(tools, list):
            tool_list = tools
        elif isinstance(tools, tuple):
            tool_list = list(tools)
        else:
            tool_list = [tools]
        for index, tool in enumerate(tool_list):
            attributes.update(_responses_tool_item_to_attributes(tool, index))

    metadata = kwargs.get("metadata")
    if (
        metadata is not None
        and metadata is not NOT_GIVEN
        and isinstance(metadata, Mapping)
    ):
        attributes[ExtendedGenAIAttributes.GEN_AI_CUSTOM] = json.dumps(dict(metadata))

    prev_id = kwargs.get("previous_response_id")
    if prev_id is not None and prev_id is not NOT_GIVEN:
        attributes["gen_ai.openai.request.previous_response_id"] = prev_id

    conversation = kwargs.get("conversation")
    if conversation is not None and conversation is not NOT_GIVEN:
        conv_id = get_property_value(conversation, "id")
        if conv_id:
            attributes["gen_ai.openai.request.conversation_id"] = conv_id

    attributes.update(generate_server_address_and_port_attributes(client_instance))
    service_tier = kwargs.get("service_tier")
    if (
        service_tier is not None
        and service_tier is not NOT_GIVEN
        and service_tier != "auto"
    ):
        attributes[GenAIAttributes.GEN_AI_OPENAI_RESPONSE_SERVICE_TIER] = service_tier

    return attributes


@attribute_generator
def get_responses_response_attributes(
    result: Any, capture_content: bool
) -> dict[str, Any]:
    """Build span attributes from a Responses `Response` or `ParsedResponse`."""
    usage_input = None
    usage_output = None
    usage = getattr(result, "usage", None)
    if usage is not None:
        usage_input = getattr(usage, "input_tokens", None) or getattr(
            usage, "prompt_tokens", None
        )
        usage_output = getattr(usage, "output_tokens", None) or getattr(
            usage, "completion_tokens", None
        )

    choice = _responses_output_to_choice(result)

    return {
        GenAIAttributes.GEN_AI_OPENAI_REQUEST_SERVICE_TIER: getattr(
            result, "service_tier", None
        ),
        **generate_response_attributes(
            model=getattr(result, "model", None),
            finish_reasons=[choice.finish_reason or "error"],
            id=getattr(result, "id", None),
            usage_input_tokens=usage_input,
            usage_output_tokens=usage_output,
        ),
        **generate_choice_attributes(
            choices=[choice],
            capture_content=capture_content,
        ),
    }
