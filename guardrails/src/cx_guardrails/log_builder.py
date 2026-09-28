from typing import Any, cast

from opentelemetry.trace import SpanContext, format_span_id, format_trace_id

from .models._models import GuardrailType

from .models.response import CustomResult, GuardrailsResponse
from .log_attributes import (
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
            EVALUATION_POLICY_TYPE: result.policy_type.value,
        }
        if result.label is not None:
            attributes[EVALUATION_SCORE_LABEL] = result.label
        if user_id:
            attributes[EVALUATION_USER_ID] = user_id
        log_attributes.append(attributes)

    return log_attributes
