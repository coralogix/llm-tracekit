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

"""Patches for Google ADK to add semantic convention attributes."""

from __future__ import annotations

import json
from typing import Any

from opentelemetry import trace

from llm_tracekit.span_builder import (
    Choice,
    Message,
    ToolCall,
    generate_choice_attributes,
    generate_message_attributes,
    generate_tools_attributes,
)


def create_wrapped_trace_call_llm(original_func, capture_content: bool):
    """Create a wrapped version of trace_call_llm that adds semantic convention attributes."""

    def wrapped_trace_call_llm(
        invocation_context,
        event_id: str,
        llm_request,
        llm_response,
    ):
        # Call the original function first
        original_func(invocation_context, event_id, llm_request, llm_response)

        # Now add our semantic convention attributes to the current span
        span = trace.get_current_span()
        if span is None or not span.is_recording():
            return

        try:
            attributes = _build_semantic_attributes(
                llm_request, llm_response, capture_content
            )
            span.set_attributes(attributes)
        except Exception:
            # Silently ignore errors to not break the application
            pass

    return wrapped_trace_call_llm


def _build_semantic_attributes(
    llm_request, llm_response, capture_content: bool
) -> dict[str, Any]:
    """Build semantic convention attributes from LLM request and response."""
    attributes: dict[str, Any] = {}

    # Process request
    if llm_request is not None:
        attributes.update(_process_request(llm_request, capture_content))

    # Process response
    if llm_response is not None:
        attributes.update(_process_response(llm_response, capture_content))

    return attributes


def _process_request(llm_request, capture_content: bool) -> dict[str, Any]:
    """Process the LLM request to extract prompt messages and tools."""
    attributes: dict[str, Any] = {}
    messages: list[Message] = []

    # Extract system_instruction from config (should be first message)
    config = llm_request.config if hasattr(llm_request, "config") else None
    if config:
        system_instruction = getattr(config, "system_instruction", None)
        if system_instruction:
            system_content = _extract_system_instruction_content(system_instruction)
            if system_content:
                messages.append(Message(role="system", content=system_content))

    # Extract messages from contents
    contents = llm_request.contents if hasattr(llm_request, "contents") else []
    messages.extend(_parse_contents_to_messages(contents))

    if messages:
        attributes.update(
            generate_message_attributes(
                messages=messages, capture_content=capture_content
            )
        )

    # Extract tools if present in config
    if config and hasattr(config, "tools") and config.tools:
        tool_attrs = _process_tools(config.tools)
        attributes.update(tool_attrs)

    return attributes


def _extract_system_instruction_content(system_instruction) -> str | None:
    """Extract text content from system_instruction."""
    # system_instruction can be a string or a Content object with parts
    if isinstance(system_instruction, str):
        return system_instruction

    # If it's a Content object, extract text from parts
    parts = getattr(system_instruction, "parts", None)
    if parts:
        text_parts = []
        for part in parts:
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)
        if text_parts:
            return " ".join(text_parts)

    return None


def _process_response(llm_response, capture_content: bool) -> dict[str, Any]:
    """Process the LLM response to extract completion choices."""
    attributes: dict[str, Any] = {}

    # The response has a 'content' field with the model's response
    content = getattr(llm_response, "content", None)
    finish_reason = getattr(llm_response, "finish_reason", None)

    if content is not None:
        choice = _parse_content_to_choice(content, finish_reason)
        if choice:
            attributes.update(
                generate_choice_attributes(
                    choices=[choice], capture_content=capture_content
                )
            )

    return attributes


def _parse_contents_to_messages(contents) -> list[Message]:
    """Parse Google ADK contents format to Message objects."""
    messages: list[Message] = []

    for content in contents:
        role = getattr(content, "role", "")
        parts = getattr(content, "parts", [])

        # Map Google ADK roles to standard roles
        mapped_role = _map_role(role)

        # Process parts to extract text and tool calls
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        tool_call_id: str | None = None

        for part in parts:
            # Text content
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)

            # Function call (tool call from model)
            elif hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                args = getattr(fc, "args", None)
                tool_call = ToolCall(
                    id=getattr(fc, "id", None),
                    type="function",
                    function_name=getattr(fc, "name", None),
                    function_arguments=json.dumps(dict(args)) if args else None,
                )
                tool_calls.append(tool_call)

            # Function response (tool result)
            elif hasattr(part, "function_response") and part.function_response:
                fr = part.function_response
                mapped_role = "tool"
                tool_call_id = getattr(fr, "id", None)
                response = getattr(fr, "response", {})
                if isinstance(response, dict):
                    text_parts.append(json.dumps(response))
                else:
                    text_parts.append(str(response))

        message = Message(
            role=mapped_role,
            content=" ".join(text_parts) if text_parts else None,
            tool_call_id=tool_call_id,
            tool_calls=tool_calls if tool_calls else None,
        )
        messages.append(message)

    return messages


def _parse_content_to_choice(content, finish_reason) -> Choice | None:
    """Parse Google ADK content to a Choice object."""
    parts = getattr(content, "parts", [])
    role = getattr(content, "role", "model")

    # Map finish reason
    if finish_reason is not None:
        if hasattr(finish_reason, "value"):
            finish_reason = finish_reason.value.lower()
        elif isinstance(finish_reason, str):
            finish_reason = finish_reason.lower()
    else:
        finish_reason = "stop"

    # Process parts
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []

    for part in parts:
        if hasattr(part, "text") and part.text:
            text_parts.append(part.text)
        elif hasattr(part, "function_call") and part.function_call:
            fc = part.function_call
            args = getattr(fc, "args", None)
            tool_call = ToolCall(
                id=getattr(fc, "id", None),
                type="function",
                function_name=getattr(fc, "name", None),
                function_arguments=json.dumps(dict(args)) if args else None,
            )
            tool_calls.append(tool_call)

    return Choice(
        finish_reason=finish_reason,
        role=_map_role(role),
        content=" ".join(text_parts) if text_parts else None,
        tool_calls=tool_calls if tool_calls else None,
    )


def _process_tools(tools) -> dict[str, Any]:
    """Process tools definition to extract tool attributes."""
    tool_definitions = []

    for tool in tools:
        # Google ADK tools are typically function declarations
        function_declarations = getattr(tool, "function_declarations", None)
        if function_declarations:
            for func in function_declarations:
                params = getattr(func, "parameters", None)
                # Convert Schema objects to dict safely
                params_dict = None
                if params is not None:
                    try:
                        if hasattr(params, "model_dump"):
                            params_dict = params.model_dump(exclude_none=True)
                        elif hasattr(params, "to_dict"):
                            params_dict = params.to_dict()
                        elif isinstance(params, dict):
                            params_dict = params
                        else:
                            # Try to convert to string representation
                            params_dict = str(params)
                    except Exception:
                        params_dict = None

                tool_def = {
                    "type": "function",
                    "function": {
                        "name": getattr(func, "name", None),
                        "description": getattr(func, "description", None),
                        "parameters": params_dict,
                    },
                }
                tool_definitions.append(tool_def)

    if tool_definitions:
        return generate_tools_attributes(tool_definitions)
    return {}


def _map_role(role: str) -> str:
    """Map Google ADK roles to standard semantic convention roles."""
    role_mapping = {
        "user": "user",
        "model": "assistant",
        "function": "tool",
        "system": "system",
    }
    return role_mapping.get(role.lower() if role else "", role or "")
