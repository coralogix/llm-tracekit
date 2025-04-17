from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

from llm_tracekit import extended_gen_ai_attributes as ExtendedGenAIAttributes


@dataclass
class ToolCall:
    id: Optional[str] = None
    type: Optional[str] = None
    function_name: Optional[str] = None
    function_arguments: Optional[str] = None


@dataclass
class Message:
    role: Optional[str] = None
    content: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


@dataclass
class Choice:
    finish_reason: Optional[str] = None
    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


def remove_attributes_with_null_values(attributes: dict[str, Any]) -> dict[str, Any]:
    return {attr: value for attr, value in attributes.items() if value is not None}


def generate_base_attributes(
    system: GenAIAttributes.GenAiSystemValues,
    operation: GenAIAttributes.GenAiOperationNameValues = GenAIAttributes.GenAiOperationNameValues.CHAT,
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
    frequency_penalty: Optional[float] = None,
) -> Dict[str, Any]:
    attributes = {
        GenAIAttributes.GEN_AI_REQUEST_MODEL: model,
        GenAIAttributes.GEN_AI_REQUEST_TEMPERATURE: temperature,
        GenAIAttributes.GEN_AI_REQUEST_TOP_P: top_p,
        GenAIAttributes.GEN_AI_REQUEST_MAX_TOKENS: max_tokens,
        GenAIAttributes.GEN_AI_REQUEST_PRESENCE_PENALTY: presence_penalty,
        GenAIAttributes.GEN_AI_REQUEST_FREQUENCY_PENALTY: frequency_penalty,
    }
    return remove_attributes_with_null_values(attributes)


def generate_message_attributes(
    messages: List[Message], capture_content: bool
) -> Dict[str, Any]:
    attributes = {}
    for index, message in enumerate(messages):
        attributes[
            ExtendedGenAIAttributes.GEN_AI_PROMPT_ROLE.format(prompt_index=index)
        ] = message.role

        if capture_content and message.content is not None:
            attributes[
                ExtendedGenAIAttributes.GEN_AI_PROMPT_CONTENT.format(prompt_index=index)
            ] = message.content

        attributes[
            ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALL_ID.format(
                prompt_index=index
            )
        ] = message.tool_call_id
        if message.tool_calls is not None:
            for tool_index, tool_call in enumerate(message.tool_calls):
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_ID.format(
                        prompt_index=index, tool_call_index=tool_index
                    )
                ] = tool_call.id
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_TYPE.format(
                        prompt_index=index, tool_call_index=tool_index
                    )
                ] = tool_call.type
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_FUNCTION_NAME.format(
                        prompt_index=index, tool_call_index=tool_index
                    )
                ] = tool_call.function_name
                if capture_content:
                    attributes[
                        ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_FUNCTION_ARGUMENTS.format(
                            prompt_index=index, tool_call_index=tool_index
                        )
                    ] = tool_call.function_arguments

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


def generate_choice_attributes(
    choices: List[Choice], capture_content: bool
) -> Dict[str, Any]:
    attributes = {}
    for index, choice in enumerate(choices):
        attributes[
            ExtendedGenAIAttributes.GEN_AI_COMPLETION_FINISH_REASON.format(
                completion_index=index
            )
        ] = choice.finish_reason
        attributes[
            ExtendedGenAIAttributes.GEN_AI_COMPLETION_ROLE.format(completion_index=index)
        ] = choice.role

        if capture_content and choice.content is not None:
            attributes[
                ExtendedGenAIAttributes.GEN_AI_COMPLETION_CONTENT.format(
                    completion_index=index
                )
            ] = choice.content

        if choice.tool_calls is not None:
            for tool_index, tool_call in enumerate(choice.tool_calls):
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_ID.format(
                        completion_index=index, tool_call_index=tool_index
                    )
                ] = tool_call.id
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_TYPE.format(
                        completion_index=index, tool_call_index=tool_index
                    )
                ] = tool_call.type
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_FUNCTION_NAME.format(
                        completion_index=index, tool_call_index=tool_index
                    )
                ] = tool_call.function_name
                if capture_content:
                    attributes[
                        ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_FUNCTION_ARGUMENTS.format(
                            completion_index=index, tool_call_index=tool_index
                        )
                    ] = tool_call.function_arguments

    return remove_attributes_with_null_values(attributes)
