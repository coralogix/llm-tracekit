# Copyright Coralogix Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Iterable

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.semconv._incubating.metrics import gen_ai_metrics
from opentelemetry.semconv.attributes import error_attributes as ErrorAttributes

from llm_tracekit.core import _extended_gen_ai_attributes as ExtendedGenAIAttributes
from llm_tracekit.core import (
    GEN_AI_CLIENT_OPERATION_DURATION_BUCKETS,
    GEN_AI_CLIENT_TOKEN_USAGE_BUCKETS,
)

# This is a PNG of a single black pixel
IMAGE_DATA = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x01\x00\x00\x00\x007n\xf9$\x00\x00\x00\nIDATx\x01c`\x00\x00\x00\x02\x00\x01su\x01\x18\x00\x00\x00\x00IEND\xaeB`\x82"


def assert_tool_definitions_in_span(span: ReadableSpan, tools: list[dict]):
    assert span.attributes is not None

    for index, tool in enumerate(tools):
        assert (
            span.attributes[
                ExtendedGenAIAttributes.GEN_AI_BEDROCK_REQUEST_TOOLS_FUNCTION_NAME.format(
                    tool_index=index
                )
            ]
            == tool["name"]
        )
        assert (
            span.attributes[
                ExtendedGenAIAttributes.GEN_AI_BEDROCK_REQUEST_TOOLS_FUNCTION_DESCRIPTION.format(
                    tool_index=index
                )
            ]
            == tool["description"]
        )
        assert (
            span.attributes[
                ExtendedGenAIAttributes.GEN_AI_BEDROCK_REQUEST_TOOLS_FUNCTION_PARAMETERS.format(
                    tool_index=index
                )
            ]
            == tool["parameters"]
        )


def assert_attributes_in_span(
    span: ReadableSpan,
    span_name: str,
    request_model: str | None = None,
    response_model: str | None = None,
    usage_input_tokens: int | None = None,
    usage_output_tokens: int | None = None,
    finish_reasons: Iterable[str] | None = None,
    error: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    agent_id: str | None = None,
    agent_alias_id: str | None = None,
    foundation_model: str | None = None,
):
    assert span.name == span_name
    assert span.attributes is not None

    attributes_to_expected_values = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: GenAIAttributes.GenAiOperationNameValues.CHAT.value,
        GenAIAttributes.GEN_AI_SYSTEM: GenAIAttributes.GenAiSystemValues.AWS_BEDROCK.value,
        GenAIAttributes.GEN_AI_REQUEST_MODEL: request_model or foundation_model,
        GenAIAttributes.GEN_AI_RESPONSE_MODEL: response_model or foundation_model,
        GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS: usage_input_tokens,
        GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS: usage_output_tokens,
        GenAIAttributes.GEN_AI_RESPONSE_FINISH_REASONS: finish_reasons,
        ErrorAttributes.ERROR_TYPE: error,
        GenAIAttributes.GEN_AI_REQUEST_MAX_TOKENS: max_tokens,
        GenAIAttributes.GEN_AI_REQUEST_TEMPERATURE: temperature,
        GenAIAttributes.GEN_AI_REQUEST_TOP_P: top_p,
        GenAIAttributes.GEN_AI_REQUEST_TOP_K: top_k,
        GenAIAttributes.GEN_AI_AGENT_ID: agent_id,
        ExtendedGenAIAttributes.GEN_AI_BEDROCK_AGENT_ALIAS_ID: agent_alias_id,
    }
    for attribute, expected_value in attributes_to_expected_values.items():
        if expected_value is not None:
            assert span.attributes[attribute] == expected_value, attribute
        else:
            assert attribute not in span.attributes


def assert_expected_metrics(
    metrics,
    usage_input_tokens: int | None = None,
    usage_output_tokens: int | None = None,
    error: str | None = None,
    request_model: str | None = None,
    response_model: str | None = None,
    foundation_model: str | None = None,
):
    attributes = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: GenAIAttributes.GenAiOperationNameValues.CHAT.value,
        GenAIAttributes.GEN_AI_SYSTEM: GenAIAttributes.GenAiSystemValues.AWS_BEDROCK.value,
        GenAIAttributes.GEN_AI_REQUEST_MODEL: request_model,
        GenAIAttributes.GEN_AI_RESPONSE_MODEL: response_model or foundation_model,
        ErrorAttributes.ERROR_TYPE: error,
    }

    metric_data_points = []
    duration_metric = None
    usage_metric = None
    for metric in metrics:
        if metric.name == gen_ai_metrics.GEN_AI_CLIENT_OPERATION_DURATION:
            duration_metric = metric
        elif metric.name == gen_ai_metrics.GEN_AI_CLIENT_TOKEN_USAGE:
            usage_metric = metric

    assert duration_metric is not None
    assert duration_metric.data.data_points[0].sum > 0
    assert (
        list(duration_metric.data.data_points[0].explicit_bounds)
        == GEN_AI_CLIENT_OPERATION_DURATION_BUCKETS
    )
    metric_data_points.append(duration_metric.data.data_points[0])

    if usage_input_tokens is not None:
        assert usage_metric is not None
        input_token_usage = next(
            (
                data_point
                for data_point in usage_metric.data.data_points
                if data_point.attributes[GenAIAttributes.GEN_AI_TOKEN_TYPE]
                == GenAIAttributes.GenAiTokenTypeValues.INPUT.value
            ),
            None,
        )
        assert input_token_usage is not None
        assert input_token_usage.sum == usage_input_tokens
        assert (
            list(input_token_usage.explicit_bounds) == GEN_AI_CLIENT_TOKEN_USAGE_BUCKETS
        )
        metric_data_points.append(input_token_usage)

    if usage_output_tokens is not None:
        assert usage_metric is not None
        output_token_usage = next(
            (
                data_point
                for data_point in usage_metric.data.data_points
                if data_point.attributes[GenAIAttributes.GEN_AI_TOKEN_TYPE]
                == GenAIAttributes.GenAiTokenTypeValues.OUTPUT.value
            ),
            None,
        )
        assert output_token_usage is not None
        assert output_token_usage.sum == usage_output_tokens
        assert (
            list(output_token_usage.explicit_bounds)
            == GEN_AI_CLIENT_TOKEN_USAGE_BUCKETS
        )
        metric_data_points.append(output_token_usage)

    # Assert that all data points have all the expected attributes
    for data_point in metric_data_points:
        for attribute, expected_value in attributes.items():
            if expected_value is not None:
                assert data_point.attributes[attribute] == expected_value
            else:
                assert attribute not in data_point.attributes


def assert_messages_in_span(
    span: ReadableSpan, expected_messages: list, expect_content: bool
):
    assert span.attributes is not None

    for index, message in enumerate(expected_messages):
        assert (
            span.attributes[
                ExtendedGenAIAttributes.GEN_AI_PROMPT_ROLE.format(prompt_index=index)
            ]
            == message["role"]
        )

        if "content" in message:
            if expect_content:
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_PROMPT_CONTENT.format(
                            prompt_index=index
                        )
                    ]
                    == message["content"]
                )
            else:
                assert (
                    ExtendedGenAIAttributes.GEN_AI_PROMPT_CONTENT.format(
                        prompt_index=index
                    )
                    not in span.attributes
                )

        if "tool_calls" in message:
            for tool_index, tool_call in enumerate(message["tool_calls"]):
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_ID.format(
                            prompt_index=index, tool_call_index=tool_index
                        )
                    ]
                    == tool_call["id"]
                )
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_TYPE.format(
                            prompt_index=index, tool_call_index=tool_index
                        )
                    ]
                    == tool_call["type"]
                )
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_FUNCTION_NAME.format(
                            prompt_index=index, tool_call_index=tool_index
                        )
                    ]
                    == tool_call["function"]["name"]
                )
                if expect_content:
                    assert (
                        span.attributes[
                            ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_FUNCTION_ARGUMENTS.format(
                                prompt_index=index, tool_call_index=tool_index
                            )
                        ]
                        == tool_call["function"]["arguments"]
                    )
                else:
                    assert (
                        ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_FUNCTION_ARGUMENTS.format(
                            prompt_index=index, tool_call_index=tool_index
                        )
                        not in span.attributes
                    )
        else:
            assert (
                ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_ID.format(
                    prompt_index=index, tool_call_index=0
                )
                not in span.attributes
            )

        if "tool_call_id" in message:
            assert (
                span.attributes[
                    ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALL_ID.format(
                        prompt_index=index
                    )
                ]
                == message["tool_call_id"]
            )
        else:
            assert (
                ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALL_ID.format(
                    prompt_index=index
                )
                not in span.attributes
            )

    # Check that there aren't any additional messages
    assert (
        ExtendedGenAIAttributes.GEN_AI_PROMPT_ROLE.format(prompt_index=index + 1)
        not in span.attributes
    )


def assert_choices_in_span(
    span: ReadableSpan, expected_choices: list, expect_content: bool
):
    assert span.attributes is not None

    for index, choice in enumerate(expected_choices):
        assert (
            span.attributes[
                ExtendedGenAIAttributes.GEN_AI_COMPLETION_ROLE.format(
                    completion_index=index
                )
            ]
            == choice["message"]["role"]
        )
        if "finish_reason" in choice:
            assert (
                span.attributes[
                    ExtendedGenAIAttributes.GEN_AI_COMPLETION_FINISH_REASON.format(
                        completion_index=index
                    )
                ]
                == choice["finish_reason"]
            )
        if "content" in choice["message"]:
            if expect_content:
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_COMPLETION_CONTENT.format(
                            completion_index=index
                        )
                    ]
                    == choice["message"]["content"]
                )
            else:
                assert (
                    ExtendedGenAIAttributes.GEN_AI_COMPLETION_CONTENT.format(
                        completion_index=index
                    )
                    not in span.attributes
                )

        if "tool_calls" in choice["message"]:
            for tool_index, tool_call in enumerate(choice["message"]["tool_calls"]):
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_ID.format(
                            completion_index=index, tool_call_index=tool_index
                        )
                    ]
                    == tool_call["id"]
                )
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_TYPE.format(
                            completion_index=index, tool_call_index=tool_index
                        )
                    ]
                    == tool_call["type"]
                )
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_FUNCTION_NAME.format(
                            completion_index=index, tool_call_index=tool_index
                        )
                    ]
                    == tool_call["function"]["name"]
                )
                if expect_content:
                    assert (
                        span.attributes[
                            ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_FUNCTION_ARGUMENTS.format(
                                completion_index=index, tool_call_index=tool_index
                            )
                        ]
                        == tool_call["function"]["arguments"]
                    )
                else:
                    assert (
                        ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_FUNCTION_ARGUMENTS.format(
                            completion_index=index, tool_call_index=tool_index
                        )
                        not in span.attributes
                    )
        else:
            assert (
                ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_ID.format(
                    completion_index=index, tool_call_index=0
                )
                not in span.attributes
            )

    # Check that there aren't any additional choices
    assert (
        ExtendedGenAIAttributes.GEN_AI_COMPLETION_ROLE.format(
            completion_index=index + 1
        )
        not in span.attributes
    )
