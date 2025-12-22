from guardrails_sdk.models import GuardrailType, GuardrailsResponse
from typing import Any, Dict, Optional
from guardrails_sdk.guardrails_span_attributes import (
    LABEL,
    NAME,
    SCORE,
    EXPLANATION,
    DETECTION_THRESHOLD,
    CUSTOM_GUARDRAIL_NAME,
    PROMPT,
    RESPONSE,
    APPLICATION_NAME,
    SUBSYSTEM_NAME,
)
from common_utils.span_utils import attribute_generator


@attribute_generator
def generate_base_attributes(
    application_name: str,
    subsystem_name: str,
    prompt: Optional[str] = None,
    response: Optional[str] = None,
):
    return {
        PROMPT: prompt,
        RESPONSE: response,
        APPLICATION_NAME: application_name,
        SUBSYSTEM_NAME: subsystem_name,
    }


@attribute_generator
def generate_guardrail_response_attributes(
    guardrail_response: GuardrailsResponse,
    target: str,
) -> Dict[str, Any]:
    span_attributes: dict[str, Any] = {}
    for result in guardrail_response.results:
        guardrail_type = result.detection_type.value
        result_attributes: dict[str, Any] = {
            LABEL.format(
                target=target, guardrail_type=guardrail_type
            ): result.label.value if result.label else None,
            NAME.format(target=target, guardrail_type=guardrail_type): result.name,
            SCORE.format(target=target, guardrail_type=guardrail_type): result.score,
            EXPLANATION.format(
                target=target, guardrail_type=guardrail_type
            ): result.explanation,
            DETECTION_THRESHOLD.format(
                target=target, guardrail_type=guardrail_type
            ): result.threshold,
        }
        if result.detection_type.value == GuardrailType.custom.value and result.name:
                result_attributes[
                CUSTOM_GUARDRAIL_NAME.format(
                    target=target, guardrail_type=guardrail_type
                )] = result.name

        span_attributes.update(result_attributes)

    return span_attributes

    
    