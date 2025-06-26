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
import re
from dataclasses import dataclass, field
from timeit import default_timer
from typing import Any, Callable, Dict, List, Optional, Tuple

from botocore.eventstream import EventStream, EventStreamError
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.trace import Span
from wrapt import ObjectProxy

from llm_tracekit import extended_gen_ai_attributes as ExtendedGenAIAttributes
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
    generate_response_attributes,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentStreamResult:
    """
    A data transfer object to hold all the collected results from the agent stream.
    This avoids passing a long list of parameters between functions.
    """

    content: Optional[str]
    usage_input_tokens: Optional[int]
    usage_output_tokens: Optional[int]
    foundation_model: Optional[str]
    inference_config_max_tokens: Optional[int]
    inference_config_temperature: Optional[float]
    inference_config_top_k: Optional[int]
    inference_config_top_p: Optional[float]
    # Chat history is a tuple containing the list of prompts and the list of completions.
    chat_history: Optional[Tuple[List[Message], List[Choice]]]
    # A buffer for tool calls that have been observed but not yet assigned to an assistant's choice.
    tool_calls_buffer: List[ToolCall] = field(default_factory=list)


class BedrockMessageParser:
    """
    A dedicated parser for handling the specific string formats
    returned by the Bedrock InvokeAgent API.
    """

    # Pre-compile regex for efficiency.
    _CONTENT_PATTERN = re.compile(r"text=([^\]}]+)", re.DOTALL)
    _ANSWER_PATTERN = re.compile(r"<answer>(.*?)</answer>", re.DOTALL)
    _TOOL_USE_PATTERN = re.compile(
        r"\{\s*"
        r"input=(?P<function_arguments>\{.*\})\s*,\s*"
        r"name=(?P<function_name>[^,]+?)\s*,\s*"
        r"id=(?P<id>[^,]+?)\s*,\s*"
        r"type=(?P<type>tool_use)"
        r"\s*\}",
        re.DOTALL | re.IGNORECASE,
    )
    _TYPE_SUFFIX_PATTERN = re.compile(r",\s*type=\w+$")

    @classmethod
    def parse_content(cls, raw_content: str) -> str:
        """Extracts the primary text content from a raw content string."""
        match = cls._CONTENT_PATTERN.search(raw_content)
        return match.group(1).strip() if match else raw_content

    @classmethod
    def clean_user_content(cls, content: str) -> str:
        """Removes the trailing ', type=text' suffix from user content."""
        return cls._TYPE_SUFFIX_PATTERN.sub("", content)

    @classmethod
    def extract_final_answer(cls, content: str) -> str:
        """Extracts the content from within <answer> tags."""
        match = cls._ANSWER_PATTERN.search(content)
        return match.group(1).strip() if match else content

    @classmethod
    def parse_tool_use(cls, raw_content: str) -> Optional[ToolCall]:
        """Attempts to parse a tool call from the raw content string."""
        match = cls._TOOL_USE_PATTERN.search(raw_content)
        if not match:
            return None

        extracted_data = match.groupdict()
        try:
            extracted_data["function_arguments"] = json.loads(
                extracted_data["function_arguments"]
            )
        except (json.JSONDecodeError, TypeError):
            logger.debug(
                "Could not parse tool call arguments as JSON: %s",
                extracted_data["function_arguments"],
            )
        return ToolCall(**extracted_data)


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
        current_choice = Choice(
            role="assistant",
            content=result.content,
            tool_calls=result.tool_calls_buffer or None,
        )

        if result.chat_history:
            all_prompts = result.chat_history[0]
            all_choices = result.chat_history[1] + [current_choice]
        else:
            all_prompts = []
            all_choices = [current_choice]

        attributes = {
            **generate_message_attributes(
                messages=all_prompts, capture_content=capture_content
            ),
            **generate_response_attributes(
                model=result.foundation_model,
                usage_input_tokens=result.usage_input_tokens,
                usage_output_tokens=result.usage_output_tokens,
                foundation_model=result.foundation_model,
                inference_config_max_tokens=result.inference_config_max_tokens,
                inference_config_temperature=result.inference_config_temperature,
                inference_config_top_k=result.inference_config_top_k,
                inference_config_top_p=result.inference_config_top_p,
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
    It is designed to work robustly whether `enableTrace` is True or False.
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

        self._content: Optional[str] = None
        self._usage_input_tokens: Optional[int] = None
        self._usage_output_tokens: Optional[int] = None
        self._foundation_model: Optional[str] = None
        self._inference_config_max_tokens: Optional[int] = None
        self._inference_config_temperature: Optional[float] = None
        self._inference_config_top_k: Optional[int] = None
        self._inference_config_top_p: Optional[float] = None
        self._chat_history: Optional[Tuple[List[Message], List[Choice]]] = None
        self._tool_calls_buffer: List[ToolCall] = []

    def __iter__(self):
        try:
            for event in self.__wrapped__:
                self._process_event(event)
                yield event

            result = AgentStreamResult(
                content=self._content,
                usage_input_tokens=self._usage_input_tokens,
                usage_output_tokens=self._usage_output_tokens,
                foundation_model=self._foundation_model,
                inference_config_max_tokens=self._inference_config_max_tokens,
                inference_config_temperature=self._inference_config_temperature,
                inference_config_top_k=self._inference_config_top_k,
                inference_config_top_p=self._inference_config_top_p,
                chat_history=self._chat_history,
                tool_calls_buffer=self._tool_calls_buffer,
            )
            self._stream_done_callback(result)
        except EventStreamError as exc:
            self._stream_error_callback(exc)
            raise

    def _process_usage_data(self, usage: Dict[str, int]):
        if self._usage_input_tokens is None:
            self._usage_input_tokens = 0
        self._usage_input_tokens += usage.get("inputTokens", 0)

        if self._usage_output_tokens is None:
            self._usage_output_tokens = 0
        self._usage_output_tokens += usage.get("outputTokens", 0)

    def _process_chat_history(
        self, raw_messages: List[Dict[str, Any]]
    ) -> Optional[Tuple[List[Message], List[Choice]]]:
        try:
            prompt_history: List[Message] = []
            completion_history: List[Choice] = []
            local_tool_calls_buffer: List[ToolCall] = []

            for msg in raw_messages:
                role = msg.get("role")
                raw_content = msg.get("content", "")

                if not role or "type=tool_result" in raw_content:
                    continue

                tool_call = BedrockMessageParser.parse_tool_use(raw_content)
                if tool_call:
                    local_tool_calls_buffer.append(tool_call)
                    continue

                content = BedrockMessageParser.parse_content(raw_content)
                if role == "user":
                    clean_content = BedrockMessageParser.clean_user_content(content)
                    prompt_history.append(Message(role=role, content=clean_content))

                elif role == "assistant":
                    final_content = BedrockMessageParser.extract_final_answer(content)
                    completion_history.append(
                        Choice(
                            role=role,
                            content=final_content,
                            tool_calls=local_tool_calls_buffer or None,
                        )
                    )
                    local_tool_calls_buffer = []

            self._tool_calls_buffer = local_tool_calls_buffer
            if not prompt_history and not completion_history:
                return None
            return (prompt_history, completion_history)
        except Exception:
            logger.exception(
                "Failed to process Bedrock agent chat history. Raw messages: %s",
                raw_messages,
            )
            return None

    def _process_event(self, event):
        if "chunk" in event:
            if self._content is None:
                self._content = ""
            encoded_content = event["chunk"].get("bytes")
            if encoded_content:
                self._content += encoded_content.decode()

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
            if usage_data:
                self._process_usage_data(usage_data)

            if self._foundation_model is None:
                self._foundation_model = model_invocation_input.get("foundationModel")

            inference_config = model_invocation_input.get("inferenceConfiguration", {})
            if inference_config:
                self._inference_config_max_tokens = inference_config.get("maximumLength")
                self._inference_config_temperature = inference_config.get("temperature")
                self._inference_config_top_k = inference_config.get("topK")
                self._inference_config_top_p = inference_config.get("topP")

            if "text" in model_invocation_input:
                try:
                    payload = json.loads(model_invocation_input["text"])
                    raw_messages = payload.get("messages", [])
                    if raw_messages:
                        self._chat_history = self._process_chat_history(raw_messages)
                except (json.JSONDecodeError, TypeError):
                    logger.debug(
                        "Could not decode model invocation input text as JSON: %s",
                        model_invocation_input["text"],
                    )