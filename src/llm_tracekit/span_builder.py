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

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from pydantic import BaseModel

from llm_tracekit import extended_gen_ai_attributes as ExtendedGenAIAttributes


class ToolCall(BaseModel):
    id: str | None = None
    type: str | None = None
    function_name: str | None = None
    function_arguments: str | None = None


@dataclass
class Message:
    role: str | None = None
    content: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None


@dataclass
class Choice:
    finish_reason: str | None = None
    role: str | None = None
    content: str | None = None
    tool_calls: list[ToolCall] | None = None


def remove_attributes_with_null_values(attributes: dict[str, Any]) -> dict[str, Any]:
    return {attr: value for attr, value in attributes.items() if value is not None}


def attribute_generator(
    original_function: Callable[..., dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    @wraps(original_function)
    def wrapper(*args, **kwargs) -> dict[str, Any]:
        attributes = original_function(*args, **kwargs)

        return remove_attributes_with_null_values(attributes)

    return wrapper


@attribute_generator
def generate_base_attributes(
    system: GenAIAttributes.GenAiSystemValues | str,
    operation: GenAIAttributes.GenAiOperationNameValues = GenAIAttributes.GenAiOperationNameValues.CHAT,
) -> dict[str, Any]:
    if isinstance(system, GenAIAttributes.GenAiSystemValues):
        system = system.value
    attributes = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: operation.value,
        GenAIAttributes.GEN_AI_SYSTEM: system,
    }
    return attributes


@attribute_generator
def generate_request_attributes(
    model: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    max_tokens: int | None = None,
    presence_penalty: float | None = None,
    frequency_penalty: float | None = None,
) -> dict[str, Any]:
    attributes = {
        GenAIAttributes.GEN_AI_REQUEST_MODEL: model,
        GenAIAttributes.GEN_AI_REQUEST_TEMPERATURE: temperature,
        GenAIAttributes.GEN_AI_REQUEST_TOP_P: top_p,
        GenAIAttributes.GEN_AI_REQUEST_TOP_K: top_k,
        GenAIAttributes.GEN_AI_REQUEST_MAX_TOKENS: max_tokens,
        GenAIAttributes.GEN_AI_REQUEST_PRESENCE_PENALTY: presence_penalty,
        GenAIAttributes.GEN_AI_REQUEST_FREQUENCY_PENALTY: frequency_penalty,
    }
    return attributes


@attribute_generator
def generate_message_attributes(
    messages: list[Message], capture_content: bool
) -> dict[str, Any]:
    attributes = {}
    for index, message in enumerate(messages):
        attributes[
            ExtendedGenAIAttributes.GEN_AI_PROMPT_ROLE.format(prompt_index=index)
        ] = message.role

        if capture_content and message.content is not None:
            attributes[
                ExtendedGenAIAttributes.GEN_AI_PROMPT_CONTENT.format(prompt_index=index)
            ] = message.content

        attributes[
            ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALL_ID.format(
                prompt_index=index
            )
        ] = message.tool_call_id
        if message.tool_calls is not None:
            for tool_index, tool_call in enumerate(message.tool_calls):
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_ID.format(
                        prompt_index=index, tool_call_index=tool_index
                    )
                ] = tool_call.id
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_TYPE.format(
                        prompt_index=index, tool_call_index=tool_index
                    )
                ] = tool_call.type
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_FUNCTION_NAME.format(
                        prompt_index=index, tool_call_index=tool_index
                    )
                ] = tool_call.function_name
                if capture_content:
                    attributes[
                        ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_FUNCTION_ARGUMENTS.format(
                            prompt_index=index, tool_call_index=tool_index
                        )
                    ] = tool_call.function_arguments

    return attributes


@attribute_generator
def generate_response_attributes(
    model: str | None = None,
    finish_reasons: list[str] | None = None,
    id: str | None = None,
    usage_input_tokens: int | None = None,
    usage_output_tokens: int | None = None,
) -> dict[str, Any]:
    attributes = {
        GenAIAttributes.GEN_AI_RESPONSE_MODEL: model,
        GenAIAttributes.GEN_AI_RESPONSE_FINISH_REASONS: finish_reasons,
        GenAIAttributes.GEN_AI_RESPONSE_ID: id,
        GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS: usage_input_tokens,
        GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS: usage_output_tokens,
    }
    return attributes


@attribute_generator
def generate_choice_attributes(
    choices: list[Choice], capture_content: bool
) -> dict[str, Any]:
    attributes = {}
    for index, choice in enumerate(choices):
        attributes[
            ExtendedGenAIAttributes.GEN_AI_COMPLETION_FINISH_REASON.format(
                completion_index=index
            )
        ] = choice.finish_reason
        attributes[
            ExtendedGenAIAttributes.GEN_AI_COMPLETION_ROLE.format(
                completion_index=index
            )
        ] = choice.role

        if capture_content and choice.content is not None:
            attributes[
                ExtendedGenAIAttributes.GEN_AI_COMPLETION_CONTENT.format(
                    completion_index=index
                )
            ] = choice.content

        if choice.tool_calls is not None:
            for tool_index, tool_call in enumerate(choice.tool_calls):
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_ID.format(
                        completion_index=index, tool_call_index=tool_index
                    )
                ] = tool_call.id
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_TYPE.format(
                        completion_index=index, tool_call_index=tool_index
                    )
                ] = tool_call.type
                attributes[
                    ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_FUNCTION_NAME.format(
                        completion_index=index, tool_call_index=tool_index
                    )
                ] = tool_call.function_name
                if capture_content:
                    attributes[
                        ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_FUNCTION_ARGUMENTS.format(
                            completion_index=index, tool_call_index=tool_index
                        )
                    ] = tool_call.function_arguments

    return attributes


@dataclass
class Agent:
    id: str | None = None
    name: str | None = None
    description: str | None = None

    @attribute_generator
    def generate_attributes(self) -> dict[str, Any]:
        attributes = {
            GenAIAttributes.GEN_AI_AGENT_NAME: self.name,
            GenAIAttributes.GEN_AI_AGENT_ID: self.id,
            GenAIAttributes.GEN_AI_AGENT_DESCRIPTION: self.description,
        }
        return attributes
