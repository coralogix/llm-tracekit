from typing import Any

from llm_tracekit.core import attribute_generator

from .models.response import GuardrailsResponse
from .span_attributes import (
    NAME,
    SCORE,
    DETECTION_THRESHOLD,
    PROMPT,
    RESPONSE,
    APPLICATION_NAME,
    SUBSYSTEM_NAME,
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
    for result in guardrail_response.results:
        name = getattr(result, "name", None)
        guardrail_type = result.type.value
        result_attributes: dict[str, Any] = {
            SCORE.format(target=target, guardrail_type=guardrail_type): result.score,
            DETECTION_THRESHOLD.format(
                target=target, guardrail_type=guardrail_type
            ): result.threshold,
        }
        if name is not None:
            result_attributes[
                NAME.format(target=target, guardrail_type=guardrail_type)
            ] = name

        span_attributes.update(result_attributes)

    return span_attributes
