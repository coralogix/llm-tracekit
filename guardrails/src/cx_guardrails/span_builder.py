from typing import Any, cast

from opentelemetry.trace import SpanContext, format_span_id, format_trace_id

from .models._models import GuardrailCategory, GuardrailType

from llm_tracekit.core import attribute_generator

from .models.response import CustomResult, GuardrailsResponse, GuardrailsResponseType
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
    GEN_AI_PROVIDER_NAME,
    GEN_AI_OPERATION_NAME,
    EVENT_NAME,
    EVALUATION_RESULT_EVENT,
    EVALUATION_NAME,
    EVALUATION_SCORE_VALUE,
    EVALUATION_SCORE_LABEL,
    EVALUATION_TARGET,
    EVALUATION_TRACE_ID,
    EVALUATION_SPAN_ID,
    EVALUATION_POLICY_TYPE,
    EVALUATION_USER_ID,
)
PROVIDER_NAME = "coralogix"
OPERATION_NAME = "guardrails"

@attribute_generator
def generate_base_attributes(
    application_name: str,
    subsystem_name: str,
    prompts: list[str] | None = None,
    responses: list[str] | None = None,
):
    attributes: dict[str, Any] = {
        GEN_AI_PROVIDER_NAME: PROVIDER_NAME,
        GEN_AI_OPERATION_NAME: OPERATION_NAME,
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
    custom_guardrails_index = 0
    for result in guardrail_response.results:
        result_attributes: dict[str, Any]
        if result.type == GuardrailType.CUSTOM:
            custom_result = cast(CustomResult, result)
            result_attributes = {
                CUSTOM_GUARDRAIL_SCORE.format(target=target, index=custom_guardrails_index): result.score,
                CUSTOM_GUARDRAIL_THRESHOLD.format(target=target, index=custom_guardrails_index): result.threshold,
                CUSTOM_GUARDRAIL_TRIGGERED.format(target=target, index=custom_guardrails_index): str(result.score > result.threshold).lower(),
                CUSTOM_GUARDRAIL_NAME.format(target=target, index=custom_guardrails_index): custom_result.name or "unknown",
            }
            result_attributes[CUSTOM_GUARDRAIL_CATEGORY.format(target=target, index=custom_guardrails_index)] = custom_result.category
            custom_guardrails_index += 1
        else:
            guardrail_type = result.type.value
            result_attributes = {
                SCORE.format(target=target, guardrail_type=guardrail_type): result.score,
                THRESHOLD.format(target=target, guardrail_type=guardrail_type): result.threshold,
                TRIGGERED.format(target=target, guardrail_type=guardrail_type): str(result.score > result.threshold).lower()
            }
        span_attributes.update(result_attributes)

    return span_attributes


def guardrail_policy_type(result: GuardrailsResponseType) -> str:
    """Map a guardrail result to the evaluation policy category ai-span-tagger uses.

    PII and prompt injection are always security concerns; custom guardrails
    carry their own category (defaulting to quality); everything else
    (toxicity, test policy) is a quality concern.
    """
    if result.type in (GuardrailType.PII, GuardrailType.PROMPT_INJECTION):
        return GuardrailCategory.SECURITY.value
    if result.type == GuardrailType.CUSTOM:
        custom_result = cast(CustomResult, result)
        if custom_result.category is not None:
            return custom_result.category.value
        return GuardrailCategory.QUALITY.value
    return GuardrailCategory.QUALITY.value


def generate_evaluation_log_attributes(
    guardrail_response: GuardrailsResponse,
    target: str,
    span_context: SpanContext,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Build one gen_ai.evaluation.result log record attribute set per guardrail result.

    Mirrors what ai-span-tagger sends to the default/ai.evaluations dataset, so the
    Python guardrails SDK emits an equivalent log record alongside the guardrail span.
    """
    trace_id = format_trace_id(span_context.trace_id)
    span_id = format_span_id(span_context.span_id)

    log_attributes: list[dict[str, Any]] = []
    for result in guardrail_response.results:
        if result.type == GuardrailType.CUSTOM:
            evaluation_name = cast(CustomResult, result).name or "unknown"
        else:
            evaluation_name = result.type.value

        attributes: dict[str, Any] = {
            EVENT_NAME: EVALUATION_RESULT_EVENT,
            EVALUATION_NAME: evaluation_name,
            EVALUATION_SCORE_VALUE: result.score,
            EVALUATION_TARGET: target,
            EVALUATION_TRACE_ID: trace_id,
            EVALUATION_SPAN_ID: span_id,
            EVALUATION_POLICY_TYPE: guardrail_policy_type(result),
        }
        if result.label is not None:
            attributes[EVALUATION_SCORE_LABEL] = result.label
        if user_id:
            attributes[EVALUATION_USER_ID] = user_id
        log_attributes.append(attributes)

    return log_attributes
