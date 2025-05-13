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

from typing import Iterable, List, Optional

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.semconv._incubating.metrics import gen_ai_metrics
from opentelemetry.semconv.attributes import error_attributes as ErrorAttributes

from llm_tracekit import extended_gen_ai_attributes as ExtendedGenAIAttributes
from llm_tracekit.instruments import (
    GEN_AI_CLIENT_OPERATION_DURATION_BUCKETS,
    GEN_AI_CLIENT_TOKEN_USAGE_BUCKETS,
)

# This is a PNG of a single black pixel
IMAGE_DATA = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x01\x00\x00\x00\x007n\xf9$\x00\x00\x00\nIDATx\x01c`\x00\x00\x00\x02\x00\x01su\x01\x18\x00\x00\x00\x00IEND\xaeB`\x82"


def assert_tool_definitions_in_span(span: ReadableSpan, tools: List[dict]):
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
    request_model: Optional[str] = None,
    response_model: Optional[str] = None,
    usage_input_tokens: Optional[int] = None,
    usage_output_tokens: Optional[int] = None,
    finish_reasons: Optional[Iterable[str]] = None,
    error: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    agent_id: Optional[str] = None,
    agent_alias_id: Optional[str] = None,
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
        GenAIAttributes.GEN_AI_REQUEST_MAX_TOKENS: max_tokens,
        GenAIAttributes.GEN_AI_REQUEST_TEMPERATURE: temperature,
        GenAIAttributes.GEN_AI_REQUEST_TOP_P: top_p,
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
    usage_input_tokens: Optional[int] = None,
    usage_output_tokens: Optional[int] = None,
    error: Optional[str] = None,
    request_model: Optional[str] = None,
    response_model: Optional[str] = None,
):
    attributes = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: GenAIAttributes.GenAiOperationNameValues.CHAT.value,
        GenAIAttributes.GEN_AI_SYSTEM: GenAIAttributes.GenAiSystemValues.AWS_BEDROCK.value,
        GenAIAttributes.GEN_AI_REQUEST_MODEL: request_model,
        GenAIAttributes.GEN_AI_RESPONSE_MODEL: response_model,
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
