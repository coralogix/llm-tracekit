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

"""Patches for Strands Agents SDK to add semantic convention attributes to LLM spans."""

from __future__ import annotations

import json
from typing import Any

from opentelemetry.trace import Span

from llm_tracekit.core import (
    Choice,
    Message,
    ToolCall,
    generate_choice_attributes,
    generate_message_attributes,
)
from llm_tracekit.core import _extended_gen_ai_attributes as ExtendedGenAIAttributes


def _extract_text_from_content_blocks(content_blocks: list[dict]) -> str | None:
    """Extract text content from Strands content blocks."""
    text_parts: list[str] = []

    for block in content_blocks:
        if "text" in block and block["text"]:
            text_parts.append(block["text"])

    return " ".join(text_parts) if text_parts else None


def _extract_tool_calls_from_content_blocks(
    content_blocks: list[dict],
) -> list[ToolCall]:
    """Extract tool calls from Strands content blocks."""
    tool_calls: list[ToolCall] = []

    for block in content_blocks:
        if "toolUse" in block:
            tool_use = block["toolUse"]
            tool_input = tool_use.get("input")
            if isinstance(tool_input, dict):
                try:
                    tool_input = json.dumps(tool_input)
                except (TypeError, ValueError):
                    tool_input = str(tool_input)
            elif tool_input is not None:
                tool_input = str(tool_input)

            tool_call = ToolCall(
                id=tool_use.get("toolUseId"),
                type="function",
                function_name=tool_use.get("name"),
                function_arguments=tool_input,
            )
            tool_calls.append(tool_call)

    return tool_calls


def _extract_tool_call_id_from_content_blocks(content_blocks: list[dict]) -> str | None:
    """Extract tool call ID from tool result content blocks."""
    for block in content_blocks:
        if "toolResult" in block:
            tool_result = block["toolResult"]
            return tool_result.get("toolUseId")
    return None


def _extract_tool_result_content(content_blocks: list[dict]) -> str | None:
    """Extract tool result content as text."""
    for block in content_blocks:
        if "toolResult" in block:
            tool_result = block["toolResult"]
            result_content = tool_result.get("content")
            if isinstance(result_content, list):
                text_parts = []
                for item in result_content:
                    if isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                return " ".join(text_parts) if text_parts else None
            elif isinstance(result_content, str):
                return result_content
    return None


def _extract_single_tool_result(
    tool_result_block: dict,
) -> tuple[str | None, str | None]:
    """Extract content and tool_call_id from a single toolResult block."""
    tool_result = tool_result_block.get("toolResult", {})
    tool_call_id = tool_result.get("toolUseId")
    result_content = tool_result.get("content")

    content = None
    if isinstance(result_content, list):
        text_parts = []
        for item in result_content:
            if isinstance(item, dict) and "text" in item:
                text_parts.append(item["text"])
        content = " ".join(text_parts) if text_parts else None
    elif isinstance(result_content, str):
        content = result_content

    return content, tool_call_id


def _parse_strands_messages(messages: list[dict]) -> list[Message]:
    """Parse Strands messages format to our Message objects."""
    parsed_messages: list[Message] = []

    for msg in messages:
        role = msg.get("role", "")
        content_blocks = msg.get("content", [])

        # Collect all tool result blocks
        tool_result_blocks = [b for b in content_blocks if "toolResult" in b]

        if tool_result_blocks:
            # Create a separate Message for each tool result
            for block in tool_result_blocks:
                content, tool_call_id = _extract_single_tool_result(block)
                message = Message(
                    role="tool",
                    content=content,
                    tool_call_id=tool_call_id,
                    tool_calls=None,
                )
                parsed_messages.append(message)
        else:
            # Regular messages (user, assistant, system)
            mapped_role = _map_role(role)
            content = _extract_text_from_content_blocks(content_blocks)
            extracted_tool_calls = _extract_tool_calls_from_content_blocks(
                content_blocks
            )

            message = Message(
                role=mapped_role,
                content=content,
                tool_call_id=None,
                tool_calls=extracted_tool_calls if extracted_tool_calls else None,
            )
            parsed_messages.append(message)

    return parsed_messages


def _parse_strands_response(message: dict, stop_reason: str) -> Choice:
    """Parse Strands response message to a Choice object."""
    role = message.get("role", "assistant")
    content_blocks = message.get("content", [])

    content = _extract_text_from_content_blocks(content_blocks)
    extracted_tool_calls = _extract_tool_calls_from_content_blocks(content_blocks)
    tool_calls = extracted_tool_calls if extracted_tool_calls else None

    finish_reason = _map_stop_reason(stop_reason)

    return Choice(
        finish_reason=finish_reason,
        role=_map_role(role),
        content=content,
        tool_calls=tool_calls,
    )


def _map_role(role: str) -> str:
    """Map Strands roles to standard semantic convention roles."""
    role_mapping = {
        "user": "user",
        "assistant": "assistant",
        "system": "system",
        "model": "assistant",
    }
    return role_mapping.get(role.lower() if role else "", role or "user")


def _map_stop_reason(stop_reason: str | None) -> str:
    """Map Strands stop reasons to standard semantic convention finish reasons."""
    if stop_reason is None:
        return "stop"

    reason_mapping = {
        "end_turn": "stop",
        "tool_use": "tool_calls",
        "stop": "stop",
        "max_tokens": "length",
        "cancelled": "stop",
        "interrupt": "stop",
        "error": "error",
    }
    return reason_mapping.get(stop_reason.lower(), stop_reason)


def _process_tool_specs(tool_specs: list[dict]) -> dict[str, Any]:
    """Process tool specifications to extract tool definition attributes."""
    attributes: dict[str, Any] = {}

    for index, tool in enumerate(tool_specs):
        tool_type = "function"
        tool_name = tool.get("name")
        tool_description = tool.get("description")
        input_schema = tool.get("inputSchema")

        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_TYPE.format(tool_index=index)
        ] = tool_type

        if tool_name is not None:
            attributes[
                ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_NAME.format(
                    tool_index=index
                )
            ] = tool_name

        if tool_description is not None:
            attributes[
                ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_DESCRIPTION.format(
                    tool_index=index
                )
            ] = tool_description

        if input_schema is not None:
            # Strands wraps the JSON schema in {"json": <schema>}, extract the inner schema
            if isinstance(input_schema, dict) and "json" in input_schema:
                tool_parameters = input_schema["json"]
            else:
                tool_parameters = input_schema

            try:
                params_str = json.dumps(tool_parameters)
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_PARAMETERS.format(
                        tool_index=index
                    )
                ] = params_str
            except (TypeError, ValueError):
                pass

    return attributes


def create_wrapped_start_model_invoke_span(original_func, capture_content: bool):
    """Create a wrapped version of start_model_invoke_span."""

    def wrapped_start_model_invoke_span(
        self,
        messages,
        parent_span=None,
        model_id=None,
        custom_trace_attributes=None,
        **kwargs,
    ) -> Span:
        return original_func(
            self,
            messages,
            parent_span=parent_span,
            model_id=model_id,
            custom_trace_attributes=custom_trace_attributes,
            **kwargs,
        )

    return wrapped_start_model_invoke_span


def create_wrapped_end_model_invoke_span(original_func, capture_content: bool):
    """Create a wrapped version of end_model_invoke_span that adds completion attributes."""

    def wrapped_end_model_invoke_span(
        self, span: Span, message, usage, metrics, stop_reason
    ):
        if span is not None and span.is_recording() and _is_model_invoke_span(span):
            try:
                choice = _parse_strands_response(message, str(stop_reason))
                attributes = generate_choice_attributes(
                    choices=[choice], capture_content=capture_content
                )
                span.set_attributes(attributes)
            except Exception:
                pass

        original_func(self, span, message, usage, metrics, stop_reason)

    return wrapped_end_model_invoke_span


def _build_system_prompt_text(
    system_prompt: str | None,
    system_prompt_content: list[dict] | None,
) -> str | None:
    """Extract system prompt text from Strands system prompt parameters."""
    if system_prompt_content:
        text_parts = []
        for block in system_prompt_content:
            if isinstance(block, dict) and "text" in block:
                text_parts.append(block["text"])
        if text_parts:
            return " ".join(text_parts)

    # Fall back to simple string system_prompt
    if system_prompt:
        return system_prompt

    return None


def _is_model_invoke_span(span: Span) -> bool:
    """Check if the span is a model_invoke span (LLM call span)."""
    if hasattr(span, "attributes") and span.attributes:
        operation_name = span.attributes.get("gen_ai.operation.name")
        if operation_name == "chat":
            return True

    span_name = span.name if hasattr(span, "name") else ""
    return span_name == "chat"


def _extract_user_from_model(model) -> str | None:
    """Extract user ID from model configuration if available."""
    try:
        if hasattr(model, "config") and model.config:
            params = model.config.get("params")
            if params and isinstance(params, dict):
                user = params.get("user")
                if user:
                    return str(user)
    except Exception:
        pass
    return None


def create_wrapped_stream_messages(original_func, capture_content: bool):
    """Create a wrapped version of stream_messages that adds prompt and tool attributes."""

    async def wrapped_stream_messages(
        model,
        system_prompt,
        messages,
        tool_specs,
        *,
        tool_choice=None,
        system_prompt_content=None,
        invocation_state=None,
        cancel_signal=None,
        **kwargs,
    ):
        from opentelemetry import trace

        span = trace.get_current_span()
        if span is not None and span.is_recording() and _is_model_invoke_span(span):
            try:
                system_text = _build_system_prompt_text(
                    system_prompt, system_prompt_content
                )
                parsed_messages = _parse_strands_messages(messages)

                if system_text:
                    system_message = Message(role="system", content=system_text)
                    all_messages = [system_message] + parsed_messages
                else:
                    all_messages = parsed_messages

                message_attributes = generate_message_attributes(
                    messages=all_messages, capture_content=capture_content
                )
                span.set_attributes(message_attributes)

                if tool_specs:
                    tool_attributes = _process_tool_specs(tool_specs)
                    span.set_attributes(tool_attributes)

                user_id = _extract_user_from_model(model)
                if user_id:
                    span.set_attribute(
                        ExtendedGenAIAttributes.GEN_AI_REQUEST_USER, user_id
                    )
            except Exception:
                pass

        async for event in original_func(
            model,
            system_prompt,
            messages,
            tool_specs,
            tool_choice=tool_choice,
            system_prompt_content=system_prompt_content,
            invocation_state=invocation_state,
            cancel_signal=cancel_signal,
            **kwargs,
        ):
            yield event

    return wrapped_stream_messages
