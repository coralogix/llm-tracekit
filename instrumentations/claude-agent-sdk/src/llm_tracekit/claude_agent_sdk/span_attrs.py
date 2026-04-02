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

"""Build gen_ai.* span attributes from Claude Agent SDK types."""

from __future__ import annotations

import json
from typing import Any

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

from llm_tracekit.core import (
    Choice,
    Message,
    ToolCall,
    generate_base_attributes,
    generate_choice_attributes,
    generate_message_attributes,
    generate_request_attributes,
    generate_response_attributes,
)
from llm_tracekit.core import _extended_gen_ai_attributes as ExtendedGenAIAttributes

# Library-specific attribute prefixes
GEN_AI_CLAUDE_AGENT_SDK_RESULT_DURATION_MS = (
    "gen_ai.claude_agent_sdk.result.duration_ms"
)
GEN_AI_CLAUDE_AGENT_SDK_RESULT_DURATION_API_MS = (
    "gen_ai.claude_agent_sdk.result.duration_api_ms"
)
GEN_AI_CLAUDE_AGENT_SDK_RESULT_NUM_TURNS = "gen_ai.claude_agent_sdk.result.num_turns"
GEN_AI_CLAUDE_AGENT_SDK_RESULT_TOTAL_COST_USD = (
    "gen_ai.claude_agent_sdk.result.total_cost_usd"
)
GEN_AI_CLAUDE_AGENT_SDK_RESULT_SESSION_ID = "gen_ai.claude_agent_sdk.result.session_id"

DEFAULT_SYSTEM = "claude.agent_sdk"


def _extract_system_prompt(options: Any) -> str | None:
    """Extract system prompt string from ClaudeAgentOptions."""
    if options is None:
        return None
    raw = getattr(options, "system_prompt", None)
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    # SystemPromptPreset is a TypedDict with "type": "preset", "preset": "claude_code", "append"?
    if isinstance(raw, dict) and raw.get("type") == "preset":
        append = raw.get("append")
        return str(append) if append else None
    return str(raw) if raw else None


def _blocks_to_content_and_tool_calls(
    blocks: list[Any], capture_content: bool
) -> tuple[str | None, list[ToolCall] | None]:
    """Extract merged text content and tool_calls from AssistantMessage content blocks."""
    text_parts = []
    tool_calls: list[ToolCall] = []
    for block in blocks:
        cls_name = type(block).__name__
        if cls_name == "TextBlock":
            if capture_content:
                text_parts.append(block.text)
        elif cls_name == "ToolUseBlock":
            args_str = None
            if capture_content and getattr(block, "input", None):
                args_str = (
                    json.dumps(block.input)
                    if isinstance(block.input, dict)
                    else str(block.input)
                )
            tool_calls.append(
                ToolCall(
                    id=getattr(block, "id", None),
                    type="function",
                    function_name=getattr(block, "name", None),
                    function_arguments=args_str,
                )
            )
        elif isinstance(block, dict):
            if block.get("type") == "text":
                if capture_content:
                    text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                inp = block.get("input", {})
                args_str = json.dumps(inp) if capture_content and inp else None
                tool_calls.append(
                    ToolCall(
                        id=block.get("id"),
                        type="function",
                        function_name=block.get("name"),
                        function_arguments=args_str,
                    )
                )
    content = "\n".join(text_parts) if text_parts else None
    return content, tool_calls if tool_calls else None


def build_request_attributes_from_options(options: Any | None) -> dict[str, Any]:
    """Build request-level attributes (model, user, base) from ClaudeAgentOptions."""
    attrs: dict[str, Any] = {}
    attrs.update(
        generate_base_attributes(
            DEFAULT_SYSTEM,
            GenAIAttributes.GenAiOperationNameValues.CHAT,
        )
    )
    if options is not None:
        model = getattr(options, "model", None)
        if model:
            attrs.update(generate_request_attributes(model=model))
        user = getattr(options, "user", None)
        if user:
            attrs[ExtendedGenAIAttributes.GEN_AI_REQUEST_USER] = user
    return attrs


def build_prompt_attributes_for_turn(
    user_prompt: str | None,
    system_prompt: str | None,
    capture_content: bool,
) -> dict[str, Any]:
    """Build gen_ai.prompt.* for the current turn (system at 0 if present, then user)."""
    messages: list[Message] = []
    if system_prompt:
        messages.append(Message(role="system", content=system_prompt))
    if user_prompt is not None:
        content = user_prompt if capture_content else None
        messages.append(Message(role="user", content=content or None))
    if not messages:
        return {}
    return generate_message_attributes(messages, capture_content)


def build_tools_attributes_from_options(options: Any | None) -> dict[str, Any]:
    """Build gen_ai.request.tools.* from options.allowed_tools (names only)."""
    if options is None:
        return {}
    allowed = getattr(options, "allowed_tools", None)
    if not allowed or not isinstance(allowed, (list, tuple)):
        return {}
    attrs: dict[str, Any] = {}
    for i, name in enumerate(allowed):
        if not isinstance(name, str):
            continue
        attrs[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_TYPE.format(tool_index=i)
        ] = "function"
        attrs[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_NAME.format(
                tool_index=i
            )
        ] = name
        attrs[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_DESCRIPTION.format(
                tool_index=i
            )
        ] = ""
    return attrs


def build_completion_attributes(
    assistant_messages: list[Any],
    result_message: Any | None,
    capture_content: bool,
) -> dict[str, Any]:
    """Build gen_ai.completion.0.* from collected AssistantMessage(s) and ResultMessage."""
    merged_content_parts: list[str] = []
    merged_tool_calls: list[ToolCall] = []
    for msg in assistant_messages:
        content_blocks = getattr(msg, "content", None) or []
        text, tool_calls = _blocks_to_content_and_tool_calls(
            content_blocks, capture_content
        )
        if text:
            merged_content_parts.append(text)
        if tool_calls:
            merged_tool_calls.extend(tool_calls)
    content = "\n".join(merged_content_parts) if merged_content_parts else None
    finish_reason = "stop"
    if result_message is not None:
        is_error = getattr(result_message, "is_error", False)
        finish_reason = "error" if is_error else "stop"
        if merged_tool_calls and not is_error:
            finish_reason = "tool_calls"
    choice = Choice(
        finish_reason=finish_reason,
        role="assistant",
        content=content,
        tool_calls=merged_tool_calls if merged_tool_calls else None,
    )
    return generate_choice_attributes([choice], capture_content)


def build_response_attributes(result_message: Any | None) -> dict[str, Any]:
    """Build gen_ai response and usage attributes from ResultMessage."""
    if result_message is None:
        return {}
    usage = getattr(result_message, "usage", None) or {}
    if isinstance(usage, dict):
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
    else:
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
    model = getattr(result_message, "model", None)
    return generate_response_attributes(
        model=model,
        usage_input_tokens=input_tokens,
        usage_output_tokens=output_tokens,
    )


def build_library_specific_attributes(result_message: Any | None) -> dict[str, Any]:
    """Build gen_ai.claude_agent_sdk.result.* from ResultMessage."""
    if result_message is None:
        return {}
    attrs: dict[str, Any] = {}
    for key, attr_name in [
        ("duration_ms", GEN_AI_CLAUDE_AGENT_SDK_RESULT_DURATION_MS),
        ("duration_api_ms", GEN_AI_CLAUDE_AGENT_SDK_RESULT_DURATION_API_MS),
        ("num_turns", GEN_AI_CLAUDE_AGENT_SDK_RESULT_NUM_TURNS),
        ("total_cost_usd", GEN_AI_CLAUDE_AGENT_SDK_RESULT_TOTAL_COST_USD),
        ("session_id", GEN_AI_CLAUDE_AGENT_SDK_RESULT_SESSION_ID),
    ]:
        val = getattr(result_message, key, None)
        if val is not None:
            attrs[attr_name] = val
    return attrs
