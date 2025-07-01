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
import logging
from dataclasses import dataclass, field
from timeit import default_timer
from typing import Any, Callable, Dict, List, Optional

from botocore.eventstream import EventStream, EventStreamError
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.trace import Span
from wrapt import ObjectProxy

from llm_tracekit import extended_gen_ai_attributes as ExtendedGenAIAttributes
from llm_tracekit.bedrock import parsing_utils
from llm_tracekit.bedrock.utils import record_metrics
from llm_tracekit.instruments import Instruments
from llm_tracekit.span_builder import (
    Choice,
    Message,
    ToolCall,
    attribute_generator,
    generate_base_attributes,
    generate_choice_attributes,
    generate_message_attributes,
    generate_request_attributes,
    generate_response_attributes,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentStreamResult:
    """
    A data transfer object that also serves as the state container for the stream wrapper.
    """

    content: Optional[str] = None
    usage_input_tokens: Optional[int] = None
    usage_output_tokens: Optional[int] = None
    foundation_model: Optional[str] = None
    inference_config_max_tokens: Optional[int] = None
    inference_config_temperature: Optional[float] = None
    inference_config_top_k: Optional[int] = None
    inference_config_top_p: Optional[float] = None
    prompt_history: Optional[List[Message]] = None
    completion_history: Optional[List[Choice]] = None
    tool_calls_buffer: List[ToolCall] = field(default_factory=list)


@attribute_generator
def generate_attributes_from_invoke_agent_input(
    kwargs: Dict[str, Any], capture_content: bool
) -> Dict[str, Any]:
    base_attributes = generate_base_attributes(
        system=GenAIAttributes.GenAiSystemValues.AWS_BEDROCK
    )
    message_attributes = generate_message_attributes(
        messages=[Message(role="user", content=kwargs.get("inputText"))],
        capture_content=capture_content,
    )

    attributes = {
        **base_attributes,
        **message_attributes,
        GenAIAttributes.GEN_AI_AGENT_ID: kwargs.get("agentId"),
        ExtendedGenAIAttributes.GEN_AI_BEDROCK_AGENT_ALIAS_ID: kwargs.get(
            "agentAliasId"
        ),
    }

    return attributes


def record_invoke_agent_result_attributes(
    result: AgentStreamResult,
    span: Span,
    start_time: float,
    instruments: Instruments,
    capture_content: bool,
):
    try:
        tool_calls = result.tool_calls_buffer if result.tool_calls_buffer else None
        current_choice = Choice(
            role="assistant",
            content=result.content,
            tool_calls=tool_calls,
        )

        if result.prompt_history is not None:
            all_prompts = result.prompt_history
        else:
            all_prompts = []

        if result.completion_history is not None:
            all_choices = result.completion_history + [current_choice]
        else:
            all_choices = [current_choice]

        attributes = {
            **generate_message_attributes(
                messages=all_prompts, capture_content=capture_content
            ),
            **generate_request_attributes(
                model=result.foundation_model,
                temperature=result.inference_config_temperature,
                top_p=result.inference_config_top_p,
                top_k=result.inference_config_top_k,
                max_tokens=result.inference_config_max_tokens,
            ),
            **generate_response_attributes(
                model=result.foundation_model,
                usage_input_tokens=result.usage_input_tokens,
                usage_output_tokens=result.usage_output_tokens,
            ),
            **generate_choice_attributes(
                choices=all_choices,
                capture_content=capture_content,
            ),
        }
        span.set_attributes(attributes)
    finally:
        duration = max((default_timer() - start_time), 0)
        span.end()
        record_metrics(
            instruments=instruments,
            duration=duration,
            usage_input_tokens=result.usage_input_tokens,
            usage_output_tokens=result.usage_output_tokens,
            response_model=result.foundation_model,
        )


class InvokeAgentStreamWrapper(ObjectProxy):
    """
    A wrapper for botocore.eventstream.EventStream that intercepts and processes
    events from the Bedrock `invoke_agent` API to gather telemetry data.
    It uses a single internal result object to manage state during streaming.
    """

    def __init__(
        self,
        stream: EventStream,
        stream_done_callback: Callable[[AgentStreamResult], None],
        stream_error_callback: Callable[[Exception], None],
    ):
        super().__init__(stream)
        self._stream_done_callback = stream_done_callback
        self._stream_error_callback = stream_error_callback
        self._result = AgentStreamResult()

    def __iter__(self):
        try:
            for event in self.__wrapped__:
                self._process_event(event)
                yield event

            self._stream_done_callback(self._result)
        except EventStreamError as exc:
            self._stream_error_callback(exc)
            raise

    def _process_usage_data(self, usage: Dict[str, int]):
        input_tokens = usage.get("inputTokens")
        if input_tokens is not None:
            if self._result.usage_input_tokens is None:
                self._result.usage_input_tokens = 0
            self._result.usage_input_tokens += input_tokens

        output_tokens = usage.get("outputTokens")
        if output_tokens is not None:
            if self._result.usage_output_tokens is None:
                self._result.usage_output_tokens = 0
            self._result.usage_output_tokens += output_tokens

    def _process_chat_history(self, raw_messages: List[Dict[str, Any]]):
        try:
            prompt_history: List[Message] = []
            completion_history: List[Choice] = []
            local_tool_calls_buffer: List[ToolCall] = []

            for msg in raw_messages:
                role = msg.get("role")
                raw_content = msg.get("content", "")

                if role is None or "type=tool_result" in raw_content:
                    continue

                tool_call = parsing_utils.parse_tool_use(raw_content)
                if tool_call is not None:
                    local_tool_calls_buffer.append(tool_call)
                    continue

                content = parsing_utils.parse_content(raw_content)
                if role == "user":
                    clean_content = parsing_utils.clean_user_content(content)
                    prompt_history.append(Message(role=role, content=clean_content))

                elif role == "assistant":
                    final_content = parsing_utils.extract_final_answer(content)
                    tool_calls_for_choice = local_tool_calls_buffer if local_tool_calls_buffer else None
                    completion_history.append(
                        Choice(
                            role=role,
                            content=final_content,
                            tool_calls=tool_calls_for_choice,
                        )
                    )
                    local_tool_calls_buffer = []

            self._result.tool_calls_buffer = local_tool_calls_buffer

            if not prompt_history and not completion_history:
                self._result.prompt_history = None
                self._result.completion_history = None
            else:
                self._result.prompt_history = prompt_history
                self._result.completion_history = completion_history
        except Exception:
            logger.exception(
                "Failed to process Bedrock agent chat history. Raw messages: %s",
                raw_messages,
            )
            self._result.prompt_history = None
            self._result.completion_history = None

    def _process_event(self, event):
        if "chunk" in event:
            if self._result.content is None:
                self._result.content = ""
            
            encoded_content = event["chunk"].get("bytes")
            if encoded_content is not None:
                self._result.content += encoded_content.decode()

        if "trace" in event and "trace" in event.get("trace", {}):
            self._process_trace_event(event["trace"]["trace"])

    def _process_trace_event(self, trace_data: Dict[str, Any]):
        for key in [
            "preProcessingTrace",
            "postProcessingTrace",
            "orchestrationTrace",
            "routingClassifierTrace",
        ]:
            if key not in trace_data:
                continue

            sub_trace = trace_data[key]
            model_invocation_input = sub_trace.get("modelInvocationInput", {})
            model_invocation_output = sub_trace.get("modelInvocationOutput", {})

            usage_data = model_invocation_output.get("metadata", {}).get("usage")
            if usage_data is not None:
                self._process_usage_data(usage_data)

            if self._result.foundation_model is None:
                self._result.foundation_model = model_invocation_input.get("foundationModel")

            inference_config = model_invocation_input.get("inferenceConfiguration", {})
            self._result.inference_config_max_tokens = inference_config.get("maximumLength")
            self._result.inference_config_temperature = inference_config.get("temperature")
            self._result.inference_config_top_k = inference_config.get("topK")
            self._result.inference_config_top_p = inference_config.get("topP")

            if "text" in model_invocation_input:
                try:
                    payload = json.loads(model_invocation_input["text"])
                    raw_messages = payload.get("messages", [])
                    if raw_messages:
                        self._process_chat_history(raw_messages)
                except (json.JSONDecodeError, TypeError):
                    logger.debug(
                        "Could not decode model invocation input text as JSON: %s",
                        model_invocation_input["text"],
                    )