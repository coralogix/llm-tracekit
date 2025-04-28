from typing import Optional, Iterable
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

from opentelemetry.semconv.attributes import error_attributes as ErrorAttributes
import llm_tracekit.extended_gen_ai_attributes as ExtendedGenAIAttributes


def assert_attributes_in_span(
    span: ReadableSpan,
    span_name: str,
    request_model: Optional[str] = None,
    response_model: Optional[str] = None,
    usage_input_tokens: Optional[int] = None,
    usage_output_tokens: Optional[int] = None,
    finish_reasons: Optional[Iterable[str]] = None,
    error: Optional[str] = None,
):
    assert span.name == span_name
    assert span.attributes is not None

    attributes_to_expected_values = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: GenAIAttributes.GenAiOperationNameValues.CHAT.value,
        GenAIAttributes.GEN_AI_SYSTEM: GenAIAttributes.GenAiSystemValues.AWS_BEDROCK.value,
        GenAIAttributes.GEN_AI_REQUEST_MODEL: request_model,
        GenAIAttributes.GEN_AI_RESPONSE_MODEL: response_model,
        GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS: usage_input_tokens,
        GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS: usage_output_tokens,
        GenAIAttributes.GEN_AI_RESPONSE_FINISH_REASONS: finish_reasons,
        ErrorAttributes.ERROR_TYPE: error,
    }
    for attribute, expected_value in attributes_to_expected_values.items():
        if expected_value is not None:
            assert span.attributes[attribute] == expected_value
        else:
            assert attribute not in span.attributes
