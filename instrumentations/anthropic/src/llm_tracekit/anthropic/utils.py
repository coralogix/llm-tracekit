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

from __future__ import annotations

import json
from typing import Any, Mapping
from urllib.parse import urlparse

from anthropic._utils import is_given
from httpx import URL
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.semconv._incubating.attributes import (
    server_attributes as ServerAttributes,
)

from llm_tracekit.core import (
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
from llm_tracekit.core import _extended_gen_ai_attributes as ExtendedGenAIAttributes


def _get_prop(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def generate_server_address_and_port_attributes(client_instance: Any) -> dict[str, Any]:
    base_client = getattr(client_instance, "_client", None)
    base_url = getattr(base_client, "base_url", None) if base_client else None
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


def _tool_result_content_to_str(block: Any) -> str | None:
    content = _get_prop(block, "content")
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, Mapping):
                if item.get("type") == "text" and "text" in item:
                    parts.append(str(item["text"]))
                else:
                    parts.append(json.dumps(item))
            else:
                t = _get_prop(item, "type")
                if t == "text":
                    parts.append(str(_get_prop(item, "text") or ""))
                else:
                    parts.append(str(item))
        return "".join(parts) if parts else None
    return str(content)


def _parse_assistant_content_blocks(
    blocks: list[Any],
) -> tuple[str | None, list[ToolCall] | None]:
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for block in blocks:
        bt = _get_prop(block, "type")
        if bt == "text":
            text_parts.append(str(_get_prop(block, "text") or ""))
        elif bt == "tool_use":
            inp = _get_prop(block, "input")
            if inp is None:
                args = None
            elif isinstance(inp, str):
                args = inp
            else:
                args = json.dumps(inp)
            tool_calls.append(
                ToolCall(
                    id=str(_get_prop(block, "id") or ""),
                    type="function",
                    function_name=str(_get_prop(block, "name") or ""),
                    function_arguments=args,
                )
            )
    content = "".join(text_parts) if text_parts else None
    return content, tool_calls or None


def _expand_user_content_blocks(blocks: list[Any]) -> list[Message]:
    out: list[Message] = []
    text_buf: list[str] = []
    for block in blocks:
        bt = _get_prop(block, "type")
        if bt == "text":
            text_buf.append(str(_get_prop(block, "text") or ""))
        elif bt == "tool_result":
            if text_buf:
                out.append(Message(role="user", content="".join(text_buf) or None))
                text_buf = []
            tid = _get_prop(block, "tool_use_id")
            out.append(
                Message(
                    role="tool",
                    content=_tool_result_content_to_str(block),
                    tool_call_id=str(tid) if tid is not None else None,
                )
            )
    if text_buf:
        out.append(Message(role="user", content="".join(text_buf) or None))
    return out


def _api_message_to_messages(msg: Any) -> list[Message]:
    role = _get_prop(msg, "role")
    content = _get_prop(msg, "content")
    if role is None:
        return []
    if role == "assistant":
        if isinstance(content, str):
            return [Message(role="assistant", content=content)]
        if isinstance(content, list):
            text_part, tc = _parse_assistant_content_blocks(content)
            return [Message(role="assistant", content=text_part, tool_calls=tc)]
        return []
    if role == "user":
        if isinstance(content, str):
            return [Message(role="user", content=content)]
        if isinstance(content, list):
            return _expand_user_content_blocks(content)
        return []
    if role == "tool":
        return [
            Message(
                role="tool",
                content=content if isinstance(content, str) else str(content),
                tool_call_id=_get_prop(msg, "tool_call_id"),
            )
        ]
    return []


def system_param_to_messages(system: Any) -> list[Message]:
    if not is_given(system):
        return []
    if isinstance(system, str):
        return [Message(role="system", content=system)]
    parts: list[str] = []
    try:
        for block in system:
            if _get_prop(block, "type") == "text":
                parts.append(str(_get_prop(block, "text") or ""))
    except TypeError:
        return []
    joined = "".join(parts)
    return [Message(role="system", content=joined or None)]


def build_prompt_messages(kwargs: dict[str, Any]) -> list[Message]:
    out: list[Message] = []
    out.extend(system_param_to_messages(kwargs.get("system")))
    for msg in kwargs.get("messages") or []:
        out.extend(_api_message_to_messages(msg))
    return out


def _tools_request_attributes(tools: Any) -> dict[str, Any]:
    attributes: dict[str, Any] = {}
    if tools is None or not is_given(tools):
        return attributes
    try:
        tool_list = list(tools)
    except TypeError:
        return attributes
    for index, tool in enumerate(tool_list):
        if not isinstance(tool, Mapping):
            continue
        name = tool.get("name")
        desc = tool.get("description")
        input_schema = tool.get("input_schema")
        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_TYPE.format(tool_index=index)
        ] = "function"
        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_NAME.format(
                tool_index=index
            )
        ] = name
        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_DESCRIPTION.format(
                tool_index=index
            )
        ] = desc
        if input_schema is not None:
            attributes[
                ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_PARAMETERS.format(
                    tool_index=index
                )
            ] = json.dumps(input_schema)
    return attributes


@attribute_generator
def get_messages_request_attributes(
    kwargs: dict[str, Any],
    client_instance: Any,
    capture_content: bool,
) -> dict[str, Any]:
    req_kwargs: dict[str, Any] = {
        "model": kwargs.get("model"),
    }
    if is_given(kwargs.get("temperature")):
        req_kwargs["temperature"] = kwargs.get("temperature")
    if is_given(kwargs.get("top_p")):
        req_kwargs["top_p"] = kwargs.get("top_p")
    if is_given(kwargs.get("top_k")):
        req_kwargs["top_k"] = kwargs.get("top_k")
    if is_given(kwargs.get("max_tokens")):
        req_kwargs["max_tokens"] = kwargs.get("max_tokens")

    attributes: dict[str, Any] = {
        **generate_base_attributes(system=GenAIAttributes.GenAiSystemValues.ANTHROPIC),
        **generate_request_attributes(**req_kwargs),
        **generate_message_attributes(
            messages=build_prompt_messages(kwargs),
            capture_content=capture_content,
        ),
        **_tools_request_attributes(kwargs.get("tools")),
    }

    metadata = kwargs.get("metadata")
    if isinstance(metadata, Mapping):
        uid = metadata.get("user_id")
        if uid is not None:
            attributes[ExtendedGenAIAttributes.GEN_AI_REQUEST_USER] = uid

    attributes.update(generate_server_address_and_port_attributes(client_instance))
    return attributes


def anthropic_message_to_choice(message: Any) -> Choice:
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for block in getattr(message, "content", None) or []:
        bt = _get_prop(block, "type")
        if bt == "text":
            text_parts.append(str(_get_prop(block, "text") or ""))
        elif bt == "tool_use":
            inp = _get_prop(block, "input")
            if inp is None:
                args = None
            elif isinstance(inp, str):
                args = inp
            else:
                args = json.dumps(inp)
            tool_calls.append(
                ToolCall(
                    id=str(_get_prop(block, "id") or ""),
                    type="function",
                    function_name=str(_get_prop(block, "name") or ""),
                    function_arguments=args,
                )
            )
    content = "".join(text_parts) if text_parts else None
    stop_reason = getattr(message, "stop_reason", None)
    finish = str(stop_reason) if stop_reason is not None else "error"
    return Choice(
        finish_reason=finish,
        role="assistant",
        content=content,
        tool_calls=tool_calls or None,
    )


@attribute_generator
def get_message_response_attributes(
    result: Any, capture_content: bool
) -> dict[str, Any]:
    choice = anthropic_message_to_choice(result)
    usage = getattr(result, "usage", None)
    in_tok = getattr(usage, "input_tokens", None) if usage else None
    out_tok = getattr(usage, "output_tokens", None) if usage else None
    return {
        **generate_response_attributes(
            model=str(result.model) if getattr(result, "model", None) else None,
            finish_reasons=[choice.finish_reason] if choice.finish_reason else None,
            id=getattr(result, "id", None),
            usage_input_tokens=in_tok,
            usage_output_tokens=out_tok,
        ),
        **generate_choice_attributes([choice], capture_content),
    }


def is_streaming(kwargs: dict[str, Any]) -> bool:
    return kwargs.get("stream") is True


def stop_reason_to_finish_reason(stop_reason: Any) -> str:
    if stop_reason is None:
        return "error"
    return str(stop_reason)
