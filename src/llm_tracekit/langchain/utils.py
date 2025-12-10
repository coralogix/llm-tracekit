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
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from langchain_core.messages import BaseMessage  # type: ignore
from langchain_core.outputs import Generation  # type: ignore

from llm_tracekit.span_builder import Choice, Message, ToolCall


def flatten_message_batches(
    message_batches: Sequence[Sequence[BaseMessage]],
) -> List[BaseMessage]:
    flattened: List[BaseMessage] = []
    for batch in message_batches:
        flattened.extend(batch)
    return flattened


def build_prompt_history(messages: Iterable[BaseMessage]) -> List[Message]:
    history: List[Message] = []
    for message in messages:
        history.append(
            Message(
                role=_get_message_role(message),
                content=_stringify_content(getattr(message, "content", None)),
                tool_call_id=_get_tool_call_id(message),
                tool_calls=_parse_tool_calls(message),
            )
        )
    return history


def build_response_choices(
    generations: Sequence[Sequence[Generation]],
) -> Tuple[List[Choice], List[str], Optional[int], Optional[int]]:
    choices: List[Choice] = []
    finish_reasons: List[str] = []
    input_tokens_total = 0
    output_tokens_total = 0
    has_input_usage = False
    has_output_usage = False

    for generation_list in generations:
        for generation in generation_list:
            message = getattr(generation, "message", None)
            if message is None:
                continue

            finish_reason = _extract_finish_reason(generation, message)
            if finish_reason is not None:
                finish_reasons.append(str(finish_reason))

            choices.append(
                Choice(
                    finish_reason=finish_reason,
                    role=_get_message_role(message) or "assistant",
                    content=_stringify_content(getattr(message, "content", None)),
                    tool_calls=_parse_tool_calls(message),
                )
            )

            usage_metadata = getattr(message, "usage_metadata", None)
            if isinstance(usage_metadata, dict):
                input_tokens = usage_metadata.get("input_tokens")
                if isinstance(input_tokens, (int, float)):
                    has_input_usage = True
                    input_tokens_total += int(input_tokens)
                output_tokens = usage_metadata.get("output_tokens")
                if isinstance(output_tokens, (int, float)):
                    has_output_usage = True
                    output_tokens_total += int(output_tokens)

    return (
        choices,
        finish_reasons,
        input_tokens_total if has_input_usage else None,
        output_tokens_total if has_output_usage else None,
    )


def _parse_tool_calls(message: BaseMessage) -> Optional[List[ToolCall]]:
    tool_calls = getattr(message, "tool_calls", None)
    if not tool_calls and isinstance(getattr(message, "additional_kwargs", None), dict):
        tool_calls = message.additional_kwargs.get("tool_calls")  # type: ignore[assignment]

    if not tool_calls:
        return None

    parsed_calls: List[ToolCall] = []
    for tool_call in tool_calls:  # type: ignore[assignment]
        if isinstance(tool_call, dict):
            function = tool_call.get("function") or {}
            function_name = function.get("name") or tool_call.get("name")
            function_arguments = function.get("arguments")
            if function_arguments is None and "args" in tool_call:
                function_arguments = tool_call.get("args")

            parsed_calls.append(
                ToolCall(
                    id=tool_call.get("id"),
                    type=tool_call.get("type"),
                    function_name=function_name,
                    function_arguments=_stringify_arguments(function_arguments),
                )
            )
        else:
            function = getattr(tool_call, "function", None)
            function_name = _safe_getattr(function, "name") or getattr(tool_call, "name", None)
            function_arguments = _safe_getattr(function, "arguments")
            if function_arguments is None:
                function_arguments = getattr(tool_call, "args", None)

            parsed_calls.append(
                ToolCall(
                    id=getattr(tool_call, "id", None),
                    type=getattr(tool_call, "type", None),
                    function_name=function_name,
                    function_arguments=_stringify_arguments(function_arguments),
                )
            )

    return parsed_calls or None


def _get_tool_call_id(message: BaseMessage) -> Optional[str]:
    tool_call_id = getattr(message, "tool_call_id", None)
    if tool_call_id is not None:
        return tool_call_id

    additional_kwargs = getattr(message, "additional_kwargs", None)
    if isinstance(additional_kwargs, dict):
        tool_call_id = additional_kwargs.get("tool_call_id")
    return tool_call_id


def _extract_finish_reason(generation: Generation, message: BaseMessage) -> Optional[str]:
    generation_info = getattr(generation, "generation_info", None)
    if isinstance(generation_info, dict):
        finish_reason = generation_info.get("finish_reason")
        if finish_reason is not None:
            return str(finish_reason)

    response_metadata = getattr(message, "response_metadata", None)
    if isinstance(response_metadata, dict):
        for key in ("finish_reason", "stopReason", "stop_reason"):
            if key in response_metadata:
                return str(response_metadata[key])
    return None


def _stringify_arguments(arguments: Any) -> Optional[str]:
    if arguments is None:
        return None
    if isinstance(arguments, str):
        return arguments.replace("\n", " ")
    try:
        return json.dumps(arguments)
    except (TypeError, ValueError):
        return str(arguments)


def _stringify_content(content: Any) -> Optional[str]:
    """Convert heterogeneous LangChain message content into a plain string.

    The helper accepts provider-specific payloads (strings, dicts, lists of
    content blocks, etc.) and returns a trimmed string representation suitable
    for span attributes. Empty strings resolve to ``None`` so callers can skip
    storing meaningless values.

    Examples:
        >>> _stringify_content("Hello world")
        'Hello world'
        >>> _stringify_content([{"text": "part one"}, "part two"])
        'part one part two'
        >>> _stringify_content({"json": [1, 2]})
        '{"json": [1, 2]}'
        >>> _stringify_content("   ") is None
        True
    """
    if content is None:
        return None
    if isinstance(content, str):
        return content if content.strip() else None
    if isinstance(content, (list, tuple)):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        joined = " ".join(parts).strip()
        return joined or None
    if isinstance(content, dict):
        try:
            dumped = json.dumps(content)
            return dumped if dumped.strip() else None
        except (TypeError, ValueError):
            fallback = str(content)
            return fallback if fallback.strip() else None
    string_content = str(content)
    return string_content if string_content.strip() else None


def _get_message_role(message: BaseMessage) -> Optional[str]:
    role = getattr(message, "role", None)
    if role:
        return role

    msg_type = getattr(message, "type", None)
    if msg_type == "human":
        return "user"
    if msg_type == "ai":
        return "assistant"
    return msg_type


def _safe_getattr(obj: Any, name: str) -> Any:
    return getattr(obj, name, None)
