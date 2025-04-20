import json
from typing import Any, Dict, List, Optional

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

from llm_tracekit.instruments import Instruments
from llm_tracekit.span_builder import Message, ToolCall


def _combine_tool_call_content_parts(
    content_parts: List[Dict[str, Any]],
) -> Optional[str]:
    text_parts = []
    for content_part in content_parts:
        if "text" in content_part:
            text_parts.append(content_part["text"])

        if "json" in content_part:
            return json.dumps(content_part["json"])

    if len(text_parts) > 0:
        return "\n".join(text_parts)

    return None


def parse_converse_message(
    role: Optional[str], content_parts: Optional[List[Dict[str, Any]]]
) -> Message:
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
        return Message(role=role, content="\n".join(text_parts))
    elif len(tool_calls) > 0:
        message_tool_calls = []
        for tool_call in tool_calls:
            arguments = None
            if "input" in tool_call:
                arguments = json.dumps(tool_call["input"])

            message_tool_calls.append(
                ToolCall(
                    id=tool_call.get("toolUseId"),
                    type="function",
                    function_name=tool_call.get("name"),
                    function_arguments=arguments,
                )
            )

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


def record_metrics(
    instruments: Instruments,
    duration: float,
    model: Optional[str] = None,
    usage_input_tokens: Optional[int] = None,
    usage_output_tokens: Optional[int] = None,
    error_type: Optional[str] = None,
):
    common_attributes = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: GenAIAttributes.GenAiOperationNameValues.CHAT.value,
        GenAIAttributes.GEN_AI_SYSTEM: GenAIAttributes.GenAiSystemValues.AWS_BEDROCK.value,
    }

    if model is not None:
        common_attributes.update(
            {
                GenAIAttributes.GEN_AI_REQUEST_MODEL: model,
                GenAIAttributes.GEN_AI_RESPONSE_MODEL: model,
            }
        )

    if error_type:
        common_attributes["error.type"] = error_type

    instruments.operation_duration_histogram.record(
        duration,
        attributes=common_attributes,
    )

    if usage_input_tokens is not None:
        input_attributes = {
            **common_attributes,
            GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.INPUT.value,
        }
        instruments.token_usage_histogram.record(
            usage_input_tokens,
            attributes=input_attributes,
        )

    if usage_output_tokens is not None:
        completion_attributes = {
            **common_attributes,
            GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.COMPLETION.value,
        }
        instruments.token_usage_histogram.record(
            usage_output_tokens,
            attributes=completion_attributes,
        )
