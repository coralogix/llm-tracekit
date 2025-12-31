from guardrails.models.enums import GuardrailType
from guardrails.models.response import GuardrailsResponse
from typing import Any, Dict, List, Optional
from guardrails.guardrails_span_attributes import (
    LABEL,
    NAME,
    SCORE,
    DETECTION_THRESHOLD,
    CUSTOM_GUARDRAIL_NAME,
    PROMPT,
    RESPONSE,
    APPLICATION_NAME,
    SUBSYSTEM_NAME,
)
from llm_tracekit_core import attribute_generator


@attribute_generator
def generate_base_attributes(
    application_name: str,
    subsystem_name: str,
    prompts: Optional[List[str]] = None,
    responses: Optional[List[str]] = None,
):
    attributes: Dict[str, Any] = {
        APPLICATION_NAME: application_name,
        SUBSYSTEM_NAME: subsystem_name,
    }
    if prompts:
        for index, prompt in enumerate(prompts):
            attributes[PROMPT.format(index=index)] = prompt
    if responses:
        for index, response in enumerate(responses):
            attributes[RESPONSE.format(index=index)] = response
    return attributes


@attribute_generator
def generate_guardrail_response_attributes(
    guardrail_response: GuardrailsResponse,
    target: str,
) -> Dict[str, Any]:
    span_attributes: dict[str, Any] = {}
    for result in guardrail_response.results:
        guardrail_type = result.type.value
        result_attributes: dict[str, Any] = {
            LABEL.format(
                target=target, guardrail_type=guardrail_type
            ): result.label.value if result.label else None,
            NAME.format(target=target, guardrail_type=guardrail_type): getattr(
                result, "name", None
            ),
            SCORE.format(target=target, guardrail_type=guardrail_type): result.score,
            DETECTION_THRESHOLD.format(
                target=target, guardrail_type=guardrail_type
            ): result.threshold,
        }
        result_name = getattr(result, "name", None)
        if result.type.value == GuardrailType.custom.value and result_name:
            result_attributes[
                CUSTOM_GUARDRAIL_NAME.format(
                    target=target, guardrail_type=guardrail_type
                )
            ] = result_name

        span_attributes.update(result_attributes)

    return span_attributes
