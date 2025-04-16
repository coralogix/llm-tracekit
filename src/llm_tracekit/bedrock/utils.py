from typing import Any, List, Dict, Union, Optional
from dataclasses import dataclass
import json


@dataclass
class TextMessage:
    content: str


@dataclass
class ToolCall:
    tool_call_id: Optional[str]
    function: Optional[str]
    arguments: Optional[str]


@dataclass
class ToolCallMessage:
    tool_calls: List[ToolCall]


@dataclass
class ToolCallResultMessage:
    tool_call_id: Optional[str]
    content: Optional[str]


def _combine_tool_call_content_parts(content_parts: List[Dict[str, Any]]) -> Optional[str]:
    text_parts = []
    for content_part in content_parts:
        if "text" in content_part:
            text_parts.append(content_part["text"])

        if "json" in content_part:
            return json.dumps(content_part["json"])

    if len(text_parts) > 0:
        return '\n'.join(text_parts)
    
    return None


def combine_message_content_parts(content_parts: List[Dict[str, Any]]) -> Optional[Union[TextMessage, ToolCallMessage, ToolCallResultMessage]]:
    # TODO: this is best-effort to extract anything possible, document it
    text_parts = []
    tool_calls = []
    tool_call_results = []

    # Get all the content parts we support
    for content_part in content_parts:
        if "text" in content_part:
            text_parts.append(content_part["text"])

        if "toolUse" in content_part:
            tool_calls.append(content_part["toolUse"])

        if "toolResult" in content_part:
            tool_call_results.append(content_part["toolResult"])

    message = None
    if len(text_parts) > 0:
        message = TextMessage(content='\n'.join(text_parts))
    elif len(tool_calls) > 0:
        message = ToolCallMessage(tool_calls=[])
        for tool_call in tool_calls:
            arguments = None
            if "input" in tool_call:
                arguments = json.dumps(tool_call["input"])
            message.tool_calls.append(ToolCall(
                tool_call_id=tool_call.get("toolUseId"),
                function=tool_call.get("name"),
                arguments=arguments,
            ))
    # We don't support multiple tool call results, so we take the first one
    elif len(tool_call_results) > 0:
        content = None
        if "content" in tool_call_results[0]:
            content = _combine_tool_call_content_parts(tool_call_results[0]["content"])

        message = ToolCallResultMessage(
            tool_call_id=tool_call_results[0].get("toolUseId"),
            content=content,
        )
    
    return message
