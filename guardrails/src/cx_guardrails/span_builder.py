from typing import Any

from .models._models import GuardrailType

from llm_tracekit.core import attribute_generator

from .models.response import GuardrailsResponse
from .span_attributes import (
    SCORE,
    THRESHOLD,
    TRIGGERED,
    CUSTOM_GUARDRAIL_SCORE,
    CUSTOM_GUARDRAIL_THRESHOLD,
    CUSTOM_GUARDRAIL_TRIGGERED,
    PROMPT,
    RESPONSE,
    APPLICATION_NAME,
    SUBSYSTEM_NAME,
    GUARDRAILS_TRIGGERED,
)


@attribute_generator
def generate_base_attributes(
    application_name: str,
    subsystem_name: str,
    prompts: list[str] | None = None,
    responses: list[str] | None = None,
):
    attributes: dict[str, Any] = {
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
) -> dict[str, Any]:
    span_attributes: dict[str, Any] = {}
    span_attributes[GUARDRAILS_TRIGGERED] = str(any(result.detected for result in guardrail_response.results))
    for result in guardrail_response.results:
        guardrail_type = result.type.value
        result_attributes: dict[str, Any]
        if result.type == GuardrailType.CUSTOM:
            name = getattr(result, "name", "unknown") 
            result_attributes = {
                CUSTOM_GUARDRAIL_SCORE.format(target=target, name=name): result.score,
                CUSTOM_GUARDRAIL_THRESHOLD.format(target=target, name=name): result.threshold,
                CUSTOM_GUARDRAIL_TRIGGERED.format(target=target, name=name): result.score > result.threshold
            }
        else:    
            result_attributes = {
                SCORE.format(target=target, guardrail_type=guardrail_type): result.score,
                THRESHOLD.format(target=target, guardrail_type=guardrail_type): result.threshold,
                TRIGGERED.format(target=target, guardrail_type=guardrail_type): result.score > result.threshold
            }        
        span_attributes.update(result_attributes)

    return span_attributes
