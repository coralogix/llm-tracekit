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

import json
from typing import Optional

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.semconv.attributes import error_attributes as ErrorAttributes

from llm_tracekit.instruments import Instruments


def record_metrics(
    instruments: Instruments,
    duration: float,
    request_model: Optional[str] = None,
    response_model: Optional[str] = None,
    usage_input_tokens: Optional[int] = None,
    usage_output_tokens: Optional[int] = None,
    error_type: Optional[str] = None,
):
    common_attributes = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: GenAIAttributes.GenAiOperationNameValues.CHAT.value,
        GenAIAttributes.GEN_AI_SYSTEM: GenAIAttributes.GenAiSystemValues.AWS_BEDROCK.value,
    }

    if request_model is not None:
        common_attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL] = request_model
    if response_model is not None:
        common_attributes[GenAIAttributes.GEN_AI_RESPONSE_MODEL] = response_model

    if error_type:
        common_attributes[ErrorAttributes.ERROR_TYPE] = error_type

    instruments.operation_duration_histogram.record(
        duration,
        attributes=common_attributes,
    )

    if usage_input_tokens is not None:
        input_attributes = {
            **common_attributes,
            GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.INPUT.value,
        }
        instruments.token_usage_histogram.record(
            usage_input_tokens,
            attributes=input_attributes,
        )

    if usage_output_tokens is not None:
        completion_attributes = {
            **common_attributes,
            GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.COMPLETION.value,
        }
        instruments.token_usage_histogram.record(
            usage_output_tokens,
            attributes=completion_attributes,
        )


def decode_tool_use_in_stream(tool_use):
    # input get sent encoded in json
    if "input" in tool_use:
        try:
            tool_use["input"] = json.loads(tool_use["input"])
        except json.JSONDecodeError:
            pass
    return tool_use
