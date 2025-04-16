from typing import Any, Dict, List, Optional

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)


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


def generate_message_attributes() -> Dict[str, Any]:
    attributes = {

    }
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