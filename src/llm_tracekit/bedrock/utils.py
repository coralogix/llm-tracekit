from typing import Any, List, Dict, Optional
import json

from llm_tracekit.span_builder import Message, ToolCall


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


def parse_converse_message(role: Optional[str], content_parts: Optional[List[Dict[str, Any]]]) -> Message:
    """Attempts to combine the content parts of a `converse` API message to a single message."""
    if content_parts is None:
        return Message(role=role)

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

    # Theoretically, in the cases we support we don't expect to see multiple types of content
    # in the same message, but in case that happens we follow the hierarchy
    # of text > tool_calls > tool_call_result
    if len(text_parts) > 0:
        return Message(
            role=role,
            content='\n'.join(text_parts)
        )
    elif len(tool_calls) > 0:
        message_tool_calls = []
        for tool_call in tool_calls:
            arguments = None
            if "input" in tool_call:
                arguments = json.dumps(tool_call["input"])

            message_tool_calls.append(ToolCall(
                id=tool_call.get("toolUseId"),
                type="function",
                function_name=tool_call.get("name"),
                function_arguments=arguments,
            ))
        
        return Message(
            role=role,
            tool_calls=message_tool_calls,
        )
    # We don't support multiple tool call results, so we take the first one
    elif len(tool_call_results) > 0:
        content = None
        if "content" in tool_call_results[0]:
            content = _combine_tool_call_content_parts(tool_call_results[0]["content"])

        return Message(
            role=role,
            tool_call_id=tool_call_results[0].get("toolUseId"),
            content=content,
        )
    
    return Message(role=role)
