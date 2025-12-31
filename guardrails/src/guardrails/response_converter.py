"""Converters to transform SDK-specific message formats to guardrails Messages."""

import json
from typing import List, Any, TYPE_CHECKING, Optional, Union, Dict

if TYPE_CHECKING:
    from google.genai.types import (  # type: ignore[import-untyped]
        GenerateContentResponse,
        ContentListUnion,
        ContentListUnionDict,
    )
    from langchain_core.messages import AIMessage, BaseMessage

from .models.request import Message
from .models.enums import Role


# Extended role mapping for various SDK conventions
ROLE_MAP = {
    "user": "user",
    "human": "user",
    "model": "assistant",
    "assistant": "assistant", 
    "ai": "assistant",
    "system": "system",
    "tool": "tool",
    "function": "tool",
}


def _get_role(role: Optional[str], default: str = "user") -> str:
    """Normalize a role string to standard format."""
    if role is None:
        return default
    return ROLE_MAP.get(role.lower(), default)


def convert_gemini(
    response: "GenerateContentResponse",
    history: Optional[Union["ContentListUnion", "ContentListUnionDict"]] = None,
) -> List[Message]:
    """Convert Gemini contents and response to guardrails Messages.

    Args:
        response: A google.genai.types.GenerateContentResponse object
        history: The original contents/prompt passed to generate_content

    Returns:
        A list of Messages containing both the prompt and response
    """
    def extract_text(parts: Any) -> str:
        content_parts = []
        for part in parts:
            if hasattr(part, "text") and part.text:
                content_parts.append(part.text)
            elif isinstance(part, dict) and part.get("text"):
                content_parts.append(part["text"])
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                content_parts.append(json.dumps({"function_call": {"name": fc.name, "arguments": fc.args}}))
            elif isinstance(part, dict) and part.get("functionCall"):
                fc = part["functionCall"]
                content_parts.append(json.dumps({"function_call": {"name": fc.get("name"), "arguments": fc.get("args")}}))
        return "".join(content_parts)

    messages: List[Message] = []

    # Process history
    if history:
        if isinstance(history, str):
            messages.append(Message(role="user", content=history))
        elif isinstance(history, list):
            for content in history:
                if hasattr(content, "parts") and hasattr(content, "role"):
                    text = extract_text(content.parts)
                    if text:
                        messages.append(Message(role=_get_role(content.role), content=text))
                elif isinstance(content, dict):
                    # Support simple {"role": ..., "content": ...} dicts
                    if "content" in content and "parts" not in content:
                        messages.append(Message(role=_get_role(content.get("role")), content=content["content"]))
                    else:
                        text = extract_text(content.get("parts", []))
                        if text:
                            messages.append(Message(role=_get_role(content.get("role")), content=text))
                elif isinstance(content, str):
                    messages.append(Message(role="user", content=content))

    # Process response
    if hasattr(response, "candidates") and isinstance(response.candidates, list):
        for candidate in response.candidates:
            if candidate.content:
                text = extract_text(candidate.content.parts)
                if text:
                    messages.append(Message(role=_get_role(candidate.content.role, "assistant"), content=text))

    return messages


def convert_langchain(
    response: "AIMessage",
    history: Optional[List["BaseMessage"]] = None,
) -> List[Message]:
    """Convert LangChain messages to guardrails Messages.

    Args:
        response: LangChain AIMessage response
        history: Optional list of LangChain BaseMessage objects

    Returns:
        A list of Messages
    """
    def infer_role(msg: Any) -> str:
        if isinstance(msg, dict):
            return _get_role(msg.get("role"))
        if hasattr(msg, "type"):
            return _get_role(msg.type)
        # Fallback to class name heuristics
        name = msg.__class__.__name__.lower()
        if "human" in name or "user" in name:
            return "user"
        if "ai" in name or "assistant" in name:
            return "assistant"
        if "system" in name:
            return "system"
        if "tool" in name or "function" in name:
            return "tool"
        return "user"

    def get_content(msg: Any) -> Any:
        return msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)

    return [Message(role=infer_role(m), content=get_content(m)) for m in list(history or []) + [response]]


def convert_litellm(
    response: Dict[str, Any],
    messages: Optional[List[Dict[str, Any]]] = None,
) -> List[Message]:
    """Convert LiteLLM response and messages to guardrails Messages.

    Args:
        response: LiteLLM response dict with 'choices' containing the response
        messages: Original messages list passed to LiteLLM

    Returns:
        A list of Messages containing both input messages and the response
    
    Example:
        response = litellm.completion(model="gpt-4", messages=messages)
        guard_messages = convert_litellm(response.model_dump(), messages)
    """
    result: List[Message] = []

    # Add input messages
    if messages:
        for msg in messages:
            result.append(Message(role=_get_role(msg.get("role")), content=msg.get("content")))

    # Add response choices
    for choice in response.get("choices", []):
        msg = choice.get("message", {})
        result.append(Message(role=_get_role(msg.get("role"), "assistant"), content=msg.get("content")))

    return result


def convert_openai_agents(
    response: Any,
    input_items: Optional[List[Dict[str, Any]]] = None,
) -> List[Message]:
    """Convert OpenAI Agents SDK response and input items to guardrails Messages.

    Args:
        response: Response object from OpenAI Agents SDK
        input_items: List of input items (ResponseInputItemParam dicts)

    Returns:
        A list of Messages containing both input and response
    
    Example:
        result = await Runner.run(agent, input_items)
        guard_messages = convert_openai_agents(result.response, input_items)
    """
    result: List[Message] = []

    # Add system instructions
    if response and hasattr(response, "instructions") and response.instructions:
        result.append(Message(role="system", content=response.instructions))

    # Process input items
    for item in (input_items or []):
        item_type = item.get("type")
        item_role = item.get("role")

        # Support simple {"role": ..., "content": ...} dicts
        if item_type is None and "content" in item and isinstance(item.get("content"), str):
            result.append(Message(role=_get_role(item_role), content=item["content"]))
            continue

        if item_role == "user":
            content = item.get("content")
            if isinstance(content, str):
                result.append(Message(role="user", content=content))
            elif isinstance(content, list):
                text = "".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "input_text")
                if text:
                    result.append(Message(role="user", content=text))

        elif item_role == "assistant" and item_type == "message":
            content = item.get("content", [])
            if content:
                result.append(Message(role="assistant", content=content[0].get("text", "")))

        elif item_type == "function_call_output":
            result.append(Message(role="tool", content=str(item.get("output", ""))))

    # Add response output
    if response and hasattr(response, "output") and response.output:
        for output_item in response.output:
            if hasattr(output_item, "content") and output_item.content:
                text = " ".join(cp.text for cp in output_item.content if hasattr(cp, "text") and cp.text)
                if text:
                    result.append(Message(role="assistant", content=text))

    return result


def convert_bedrock_converse(
    response: Dict[str, Any],
    messages: Optional[List[Dict[str, Any]]] = None,
    system: Optional[List[Dict[str, Any]]] = None,
) -> List[Message]:
    """Convert Bedrock converse API response and messages to guardrails Messages.

    Args:
        response: Bedrock converse API response dict
        messages: Original messages list passed to converse API
        system: Optional system messages list

    Returns:
        A list of Messages containing system, input messages and the response
    
    Example:
        response = bedrock.converse(modelId=model, messages=messages, system=system)
        guard_messages = convert_bedrock_converse(response, messages, system)
    """
    result: List[Message] = []

    # Add system messages
    for sys_msg in (system or []):
        if sys_msg.get("text"):
            result.append(Message(role="system", content=sys_msg["text"]))

    # Process input messages
    for msg in (messages or []):
        role = msg.get("role")
        content = msg.get("content")
        
        # Support simple {"role": ..., "content": ...} dicts with string content
        if isinstance(content, str):
            result.append(Message(role=_get_role(role), content=content))
            continue
        
        text_parts = []
        
        for block in (content or []):
            if "text" in block:
                text_parts.append(block["text"])
            elif "toolResult" in block:
                # Tool results are separate messages
                tool_result = block["toolResult"]
                tool_text = []
                for tc in tool_result.get("content", []):
                    if "text" in tc:
                        tool_text.append(tc["text"])
                    elif "json" in tc:
                        tool_text.append(json.dumps(tc["json"]))
                if tool_text:
                    result.append(Message(role="tool", content="".join(tool_text)))
        
        if text_parts:
            result.append(Message(role=_get_role(role), content="".join(text_parts)))

    # Add response
    response_msg = response.get("output", {}).get("message", {})
    if response_msg:
        text = "".join(b["text"] for b in response_msg.get("content", []) if "text" in b)
        if text:
            result.append(Message(role=_get_role(response_msg.get("role"), "assistant"), content=text))

    return result
