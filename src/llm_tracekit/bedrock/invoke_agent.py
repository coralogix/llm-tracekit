import json
from enum import Enum
from timeit import default_timer
from typing import Any, Dict, Optional, Union

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.trace import Span

from llm_tracekit.bedrock.utils import record_metrics
from llm_tracekit.instruments import Instruments
from llm_tracekit.span_builder import (
    Choice,
    Message,
    ToolCall,
    generate_base_attributes,
    generate_choice_attributes,
    generate_message_attributes,
    generate_request_attributes,
    generate_response_attributes,
)


def generate_attributes_from_invoke_agent_input(
    kwargs: Dict[str, Any], capture_content: bool
) -> Dict[str, Any]:
    base_attributes = generate_base_attributes(
        system=GenAIAttributes.GenAiSystemValues.AWS_BEDROCK
    )
    # TODO: message attributes

    return {
        **base_attributes
    }


def record_invoke_agent_result_attributes(
    result: Dict[str, Any],
    span: Span,
    start_time: float,
    instruments: Instruments,
    capture_content: bool,
):
    usage_input_tokens = None
    usage_output_tokens = None
    try:
        model_type = _get_model_type_from_model_id(model_id)
        if model_type is None:
            return

        parsed_body = result_body
        if isinstance(result_body, str):
            try:
                parsed_body = json.loads(result_body)
            except json.JSONDecodeError:
                return

        if model_type is _ModelType.LLAMA3:
            span.set_attributes(
                _generate_llama_response_and_choice_attributes(
                    model_id=model_id,
                    parsed_body=parsed_body,
                    capture_content=capture_content,
                )
            )
        elif model_type is _ModelType.CLAUDE:
            span.set_attributes(
                _generate_claude_response_and_choice_attributes(
                    parsed_body=parsed_body, capture_content=capture_content
                )
            )

    finally:
        duration = max((default_timer() - start_time), 0)
        span.end()
        record_metrics(
            instruments=instruments,
            duration=duration,
            usage_input_tokens=usage_input_tokens,
            usage_output_tokens=usage_output_tokens,
        )
