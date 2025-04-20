from typing import Optional

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

from llm_tracekit.instruments import Instruments


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
