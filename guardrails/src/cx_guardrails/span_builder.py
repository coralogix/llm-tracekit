from typing import Any, cast

from .models._models import GuardrailType

from llm_tracekit.core import attribute_generator

from .models.response import CustomResult, GuardrailsResponse
from .span_attributes import (
    SCORE,
    THRESHOLD,
    TRIGGERED,
    CUSTOM_GUARDRAIL_NAME,
    CUSTOM_GUARDRAIL_CATEGORY,
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
    custom_index = 0
    for result in guardrail_response.results:
        result_attributes: dict[str, Any]
        if result.type == GuardrailType.CUSTOM:
            custom_result = cast(CustomResult, result)
            name = custom_result.name or "unknown"
            triggered = result.score > result.threshold
            result_attributes = {
                CUSTOM_GUARDRAIL_NAME.format(target=target, index=custom_index): name,
                CUSTOM_GUARDRAIL_TRIGGERED.format(target=target, index=custom_index): str(triggered).lower(),
                CUSTOM_GUARDRAIL_THRESHOLD.format(target=target, index=custom_index): result.threshold,
                CUSTOM_GUARDRAIL_SCORE.format(target=target, index=custom_index): result.score,
            }
            category = custom_result.category
            if category:
                result_attributes[CUSTOM_GUARDRAIL_CATEGORY.format(target=target, index=custom_index)] = category
            custom_index += 1
        else:
            guardrail_type = result.type.value
            result_attributes = {
                SCORE.format(target=target, guardrail_type=guardrail_type): result.score,
                THRESHOLD.format(target=target, guardrail_type=guardrail_type): result.threshold,
                TRIGGERED.format(target=target, guardrail_type=guardrail_type): str(result.score > result.threshold).lower()
            }
        span_attributes.update(result_attributes)

    return span_attributes
