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
from contextlib import suppress
from copy import deepcopy
from timeit import default_timer
from typing import Any, Callable, Dict, List, Optional, Union

from botocore.eventstream import EventStream, EventStreamError
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.trace import Span
from wrapt import ObjectProxy

from llm_tracekit import extended_gen_ai_attributes as ExtendedGenAIAttributes
from llm_tracekit.bedrock.utils import decode_tool_use_in_stream, record_metrics
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


def _combine_tool_call_content_blocks(
    content_blocks: List[Dict[str, Any]],
) -> Optional[str]:
    text_blocks = []
    for content_block in content_blocks:
        if "text" in content_block:
            text_blocks.append(content_block["text"])

        if "json" in content_block:
            return json.dumps(content_block["json"])

    if len(text_blocks) > 0:
        return "".join(text_blocks)

    return None


def _parse_converse_message(
    role: Optional[str], content_blocks: Optional[List[Dict[str, Any]]]
) -> List[Message]:
    """Attempts to combine the content blocks of a `converse` API message to a single message."""
    if content_blocks is None:
        return [Message(role=role)]

    text_blocks = []
    tool_call_blocks = []
    tool_call_result_blocks = []

    # Get all the content blocks we support
    for content_block in content_blocks:
        if "text" in content_block:
            text_blocks.append(content_block["text"])

        if "toolUse" in content_block:
            tool_call_blocks.append(content_block["toolUse"])

        if "toolResult" in content_block:
            tool_call_result_blocks.append(content_block["toolResult"])

    # We follow the same logic the OTEL implementation uses:
    #  * For assistant messages (text/tool calls) - return a single message
    #  * for user messages (text / tool call results) - return a message for each tool 
    #    call result, and another message for text
    messages = []
    if role == "assistant":
        tool_calls = None
        content = None
        if len(text_blocks) > 0:
            content="".join(text_blocks)
        if len(tool_call_blocks) > 0:
            tool_calls = []
            for tool_call in tool_call_blocks:
                arguments = None
                if "input" in tool_call:
                    arguments = json.dumps(tool_call["input"])

                tool_calls.append(
                    ToolCall(
                        id=tool_call.get("toolUseId"),
                        type="function",
                        function_name=tool_call.get("name"),
                        function_arguments=arguments,
                    )
                )

        messages.append(
            Message(
                role=role,
                tool_calls=tool_calls,
                content=content
            )
        )
    elif role == "user":
        if len(tool_call_result_blocks) > 0:
            for tool_call_result in tool_call_result_blocks:
                content = None
                if "content" in tool_call_result:
                    content = _combine_tool_call_content_blocks(tool_call_result["content"])

                messages.append(
                    Message(
                        role="tool",
                        tool_call_id=tool_call_result.get("toolUseId"),
                        content=content,
                    )
                )

        if len(text_blocks) > 0:
            messages.append(Message(role=role, content="".join(text_blocks)))

    if len(messages) > 0:
        return messages

    return [Message(role=role)]


@attribute_generator
def generate_attributes_from_converse_input(
    kwargs: Dict[str, Any], capture_content: bool
) -> Dict[str, Any]:
    inference_config = kwargs.get("inferenceConfig", {})
    messages = []
    for system_message in kwargs.get("system", []):
        messages.append(Message(role="system", content=system_message.get("text")))

    for message in kwargs.get("messages", []):
        messages.extend(
            _parse_converse_message(
                role=message.get("role"), content_blocks=message.get("content")
            )
        )

    tool_attributes = {}
    tool_configs = kwargs.get("toolConfig", {}).get("tools", [])
    # tool configs can contain either "toolSpec" (which is the actual tool definition) or
    # "cachePoint" (to use prompt caching) - we can only gather information from "toolSpec",
    # so we filter out the rest
    tool_specs = [tool["toolSpec"] for tool in tool_configs if "toolSpec" in tool]
    for index, tool_spec in enumerate(tool_specs):
        tool_params = None
        if "inputSchema" in tool_spec and "json" in tool_spec["inputSchema"]:
            with suppress(TypeError):
                tool_params = json.dumps(tool_spec["inputSchema"]["json"])

        tool_attributes.update(
            {
                ExtendedGenAIAttributes.GEN_AI_BEDROCK_REQUEST_TOOLS_FUNCTION_NAME.format(
                    tool_index=index
                ): tool_spec.get("name"),
                ExtendedGenAIAttributes.GEN_AI_BEDROCK_REQUEST_TOOLS_FUNCTION_DESCRIPTION.format(
                    tool_index=index
                ): tool_spec.get("description"),
                ExtendedGenAIAttributes.GEN_AI_BEDROCK_REQUEST_TOOLS_FUNCTION_PARAMETERS.format(
                    tool_index=index
                ): tool_params,
            }
        )

    return {
        **generate_base_attributes(
            system=GenAIAttributes.GenAiSystemValues.AWS_BEDROCK
        ),
        **generate_request_attributes(
            model=kwargs.get("modelId"),
            temperature=inference_config.get("temperature"),
            top_p=inference_config.get("topP"),
            max_tokens=inference_config.get("maxTokens"),
        ),
        **generate_message_attributes(
            messages=messages, capture_content=capture_content
        ),
        **tool_attributes,
    }


def record_converse_result_attributes(
    result: Dict[str, Any],
    span: Span,
    start_time: float,
    instruments: Instruments,
    capture_content: bool,
    model: Optional[str],
):
    finish_reason = result.get("stopReason")
    usage_data = result.get("usage", {})
    usage_input_tokens = usage_data.get("inputTokens")
    usage_output_tokens = usage_data.get("outputTokens")

    response_attributes = generate_response_attributes(
        model=model,
        finish_reasons=None if finish_reason is None else [finish_reason],
        usage_input_tokens=usage_input_tokens,
        usage_output_tokens=usage_output_tokens,
    )
    span.set_attributes(response_attributes)

    response_message = result.get("output", {}).get("message")
    if response_message is not None:
        parsed_response_message = _parse_converse_message(
            role=response_message.get("role"),
            content_blocks=response_message.get("content"),
        )[0]
        choice = Choice(
            finish_reason=finish_reason,
            role=parsed_response_message.role,
            content=parsed_response_message.content,
            tool_calls=parsed_response_message.tool_calls,
        )
        span.set_attributes(
            generate_choice_attributes(
                choices=[choice], capture_content=capture_content
            )
        )

    span.end()

    duration = max((default_timer() - start_time), 0)
    record_metrics(
        instruments=instruments,
        duration=duration,
        request_model=model,
        response_model=model,
        usage_input_tokens=usage_input_tokens,
        usage_output_tokens=usage_output_tokens,
    )


class ConverseStreamWrapper(ObjectProxy):
    """Wrapper for botocore.eventstream.EventStream"""

    def __init__(
        self,
        stream: EventStream,
        stream_done_callback: Callable[[Dict[str, Union[int, str]]], None],
        stream_error_callback: Callable[[Exception], None],
    ):
        super().__init__(stream)

        self._stream_done_callback = stream_done_callback
        self._stream_error_callback = stream_error_callback
        # accumulating things in the same shape of non-streaming version
        # {"usage": {"inputTokens": 0, "outputTokens": 0}, "stopReason": "finish", "output": {"message": {"role": "", "content": [{"text": ""}]}
        self._response: Dict[str, Any] = {}
        self._message = None
        self._content_block: Dict[str, Any] = {}
        self._record_message = False

    def __iter__(self):
        try:
            for event in self.__wrapped__:
                self._process_event(event)
                yield event
        except EventStreamError as exc:
            self._stream_error_callback(exc)
            raise

    def _process_event(self, event):
        # pylint: disable=too-many-branches
        if "messageStart" in event:
            # {'messageStart': {'role': 'assistant'}}
            if event["messageStart"].get("role") == "assistant":
                self._record_message = True
                self._message = {"role": "assistant", "content": []}
            return

        if "contentBlockStart" in event:
            # {'contentBlockStart': {'start': {'toolUse': {'toolUseId': 'id', 'name': 'func_name'}}, 'contentBlockIndex': 1}}
            start = event["contentBlockStart"].get("start", {})
            if "toolUse" in start:
                self._content_block = {"toolUse": deepcopy(start["toolUse"])}
            return

        if "contentBlockDelta" in event:
            # {'contentBlockDelta': {'delta': {'text': "Hello"}, 'contentBlockIndex': 0}}
            # {'contentBlockDelta': {'delta': {'toolUse': {'input': '{"location":"Seattle"}'}}, 'contentBlockIndex': 1}}
            if self._record_message:
                delta = event["contentBlockDelta"].get("delta", {})
                if "text" in delta:
                    self._content_block.setdefault("text", "")
                    self._content_block["text"] += delta["text"]
                elif "toolUse" in delta:
                    self._content_block["toolUse"].setdefault("input", "")
                    self._content_block["toolUse"]["input"] += delta["toolUse"].get(
                        "input", ""
                    )
            return

        if "contentBlockStop" in event:
            # {'contentBlockStop': {'contentBlockIndex': 0}}
            if self._record_message and self._message is not None:
                if "toolUse" in self._content_block:
                    self._content_block["toolUse"] = decode_tool_use_in_stream(
                        self._content_block["toolUse"]
                    )

                self._message["content"].append(self._content_block)
                self._content_block = {}
            return

        if "messageStop" in event:
            # {'messageStop': {'stopReason': 'end_turn'}}
            stop_reason = event["messageStop"].get("stopReason")
            if stop_reason is not None:
                self._response["stopReason"] = stop_reason

            if self._record_message:
                self._response["output"] = {"message": self._message}
                self._record_message = False
                self._message = None

            return

        if "metadata" in event:
            # {'metadata': {'usage': {'inputTokens': 12, 'outputTokens': 15, 'totalTokens': 27}, 'metrics': {'latencyMs': 2980}}}
            usage = event["metadata"].get("usage")
            if usage is not None:
                self._response["usage"] = {}
                input_tokens = usage.get("inputTokens")
                if input_tokens is not None:
                    self._response["usage"]["inputTokens"] = input_tokens

                output_tokens = usage.get("outputTokens")
                if output_tokens is not None:
                    self._response["usage"]["outputTokens"] = output_tokens

            self._stream_done_callback(self._response)

            return
