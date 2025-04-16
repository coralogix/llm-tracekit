from typing import Any, Dict, List, Optional

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from llm_tracekit import extended_gen_ai_attributes as ExtendedGenAIAttributes



def remove_attributes_with_null_values(attributes: dict[str, Any]) -> dict[str, Any]:
    return {attr: value for attr, value in attributes.items() if value is not None}


def generate_base_attributes(
        system: GenAIAttributes.GenAiSystemValues,
        operation: GenAIAttributes.GenAiOperationNameValues = GenAIAttributes.GenAiOperationNameValues.CHAT
    ) -> Dict[str, Any]:
    attributes = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: operation.value,
        GenAIAttributes.GEN_AI_SYSTEM: system.value,
    }
    return remove_attributes_with_null_values(attributes)


def generate_request_attributes(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None
) -> Dict[str, Any]:
    attributes = {
        GenAIAttributes.GEN_AI_REQUEST_MODEL: model,
        GenAIAttributes.GEN_AI_REQUEST_TEMPERATURE: temperature,
        GenAIAttributes.GEN_AI_REQUEST_TOP_P: top_p,
        GenAIAttributes.GEN_AI_REQUEST_MAX_TOKENS: max_tokens,
        GenAIAttributes.GEN_AI_REQUEST_PRESENCE_PENALTY: presence_penalty,
        GenAIAttributes.GEN_AI_REQUEST_FREQUENCY_PENALTY: frequency_penalty
    }
    return remove_attributes_with_null_values(attributes)

def get_tool_call_attributes(item, capture_content: bool, base_path: str) -> dict:
    attributes = {}

    tool_calls = get_property_value(item, "tool_calls")
    if tool_calls is None:
        return {}

    for index, tool_call in enumerate(tool_calls):
        call_id = get_property_value(tool_call, "id")
        if call_id:
            attributes[f"{base_path}.tool_calls.{index}.id"] = call_id

        tool_type = get_property_value(tool_call, "type")
        if tool_type:
            attributes[f"{base_path}.tool_calls.{index}.type"] = tool_type

        func = get_property_value(tool_call, "function")
        if func:
            name = get_property_value(func, "name")
            if name:
                attributes[f"{base_path}.tool_calls.{index}.function.name"] = name

            arguments = get_property_value(func, "arguments")
            if capture_content and arguments:
                if isinstance(arguments, str):
                    arguments = arguments.replace("\n", "")

                attributes[f"{base_path}.tool_calls.{index}.function.arguments"] = (
                    arguments
                )

    return attributes

# TODO: consider adding a dataclass / pydantic model for message
def generate_message_attributes(messages: List[Dict[str, Any]], capture_content: bool) -> Dict[str, Any]:
    attributes = {}
    for index, message in enumerate(messages):
        role = message.get("role")
        attributes[ExtendedGenAIAttributes.GEN_AI_PROMPT_ROLE.format(prompt_index=index)] = role
        
        content = message.get("content")
        if capture_content and isinstance(content, str) and content:
            attributes[
                ExtendedGenAIAttributes.GEN_AI_PROMPT_CONTENT.format(prompt_index=index)
            ] = content
        if role == "assistant":
            tool_call_attributes = get_tool_call_attributes(
                message, capture_content, f"gen_ai.prompt.{index}"
            )
            span_attributes.update(tool_call_attributes)
        elif role == "tool":
            tool_call_id = get_property_value(message, "tool_call_id")
            if tool_call_id:
                span_attributes[
                    ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALL_ID.format(
                        prompt_index=index
                    )
                ] = tool_call_id

    return remove_attributes_with_null_values(attributes)


def generate_response_attributes(
    model: Optional[str] = None,
    finish_reasons: Optional[List[str]] = None,
    id: Optional[str] = None,
    usage_input_tokens: Optional[int] = None,
    usage_output_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    attributes = {
        GenAIAttributes.GEN_AI_RESPONSE_MODEL: model,
        GenAIAttributes.GEN_AI_RESPONSE_FINISH_REASONS: finish_reasons,
        GenAIAttributes.GEN_AI_RESPONSE_ID: id,
        GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS: usage_input_tokens,
        GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS: usage_output_tokens,
    }
    return remove_attributes_with_null_values(attributes)


def generate_choice_attributes() -> Dict[str, Any]:
    attributes = {

    }
    return remove_attributes_with_null_values(attributes)