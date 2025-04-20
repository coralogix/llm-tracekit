# Copyright The OpenTelemetry Authors
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
from typing import Any, Callable, Dict, Union, Optional
from enum import Enum

from botocore.eventstream import EventStream, EventStreamError
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from llm_tracekit.span_builder import generate_base_attributes, generate_request_attributes, generate_message_attributes, generate_response_attributes, generate_choice_attributes, Message
from wrapt import ObjectProxy



class _ModelType(Enum):
    CLAUDE = "CLAUDE"
    LLAMA3 = "llama3"


def _get_model_type_from_model_id(model_id: Optional[str]) -> Optional[_ModelType]:
    if model_id is None:
        return None

    if "anthropic.claude" in model_id:
            return _ModelType.CLAUDE
    elif "meta.llama3" in model_id:
        return _ModelType.LLAMA3
    
    return None


def _generate_claude_request_and_message_attributes(
    model_id: Optional[str],
    parsed_body: Dict[str, Any],
    capture_content: bool
) -> Dict[str, Any]:
    # Handle the old text-completions API
    if "prompt" in parsed_body:
        messages = [Message(role="user", content=parsed_body["prompt"])]
        return {
            **generate_request_attributes(
                model=model_id,
                max_tokens=parsed_body.get("max_tokens_to_sample"),
                temperature=parsed_body.get("temperature"),
                top_p=parsed_body.get("top_p"),
            ),
            **generate_message_attributes(messages=messages, capture_content=capture_content),
        }

    # Handle the messages API
    request_attributes = generate_request_attributes(
        model=model_id,
        max_tokens=parsed_body.get("max_tokens"),
        temperature=parsed_body.get("temperature"),
        top_p=parsed_body.get("top_p"),
    )
    # TODO: record tools
    # TODO: extract messages & tools

    return {
        **request_attributes,
    }


def _generate_llama_request_and_message_attributes(
    model_id: Optional[str],
    parsed_body: Dict[str, Any],
    capture_content: bool
) -> Dict[str, Any]:
    attributes = generate_request_attributes(
        model=model_id,
        max_tokens=parsed_body.get("max_gen_len"),
        temperature=parsed_body.get("temperature"),
        top_p=parsed_body.get("top_p"),
    )
    if "prompt" in parsed_body:
        messages = [Message(role="user", content=parsed_body["prompt"])]
        attributes.update(generate_message_attributes(messages=messages, capture_content=capture_content))

    return attributes



def generate_attributes_from_invoke_input(
    kwargs: Dict[str, Any], capture_content: bool
) -> Dict[str, Any]:
    base_attributes = generate_base_attributes(
        system=GenAIAttributes.GenAiSystemValues.AWS_BEDROCK
    )
    model_id = kwargs.get("modelId")
    model_type = _get_model_type_from_model_id(model_id)
    partial_attributes = {
        **base_attributes,
        **generate_request_attributes(model=model_id),
    }

    if model_type is None:
        return partial_attributes
    
    body = kwargs.get("body")
    if body is None:
        return partial_attributes
    
    try:
        parsed_body = json.loads(body)
    except json.JSONDecodeError:
        return partial_attributes

    if model_type is _ModelType.CLAUDE:
        return {
            **base_attributes,
            **_generate_claude_request_and_message_attributes(
                model_id=model_id,
                parsed_body=parsed_body,
                capture_content=capture_content,
            ),
        }
    elif model_type is _ModelType.LLAMA3:
        return {
            **base_attributes,
            **_generate_llama_request_and_message_attributes(
                model_id=model_id,
                parsed_body=parsed_body,
                capture_content=capture_content,
            ),
        }

    return partial_attributes


def _decode_tool_use(tool_use):
    # input get sent encoded in json
    if "input" in tool_use:
        try:
            tool_use["input"] = json.loads(tool_use["input"])
        except json.JSONDecodeError:
            pass
    return tool_use


class InvokeModelWithResponseStreamWrapper(ObjectProxy):
    """Wrapper for botocore.eventstream.EventStream"""

    def __init__(
        self,
        stream: EventStream,
        stream_done_callback: Callable[[Dict[str, Union[int, str]]], None],
        stream_error_callback: Callable[[Exception], None],
        model_id: str,
    ):
        super().__init__(stream)

        self._stream_done_callback = stream_done_callback
        self._stream_error_callback = stream_error_callback
        self._model_id = model_id

        # accumulating things in the same shape of the Converse API
        # {"usage": {"inputTokens": 0, "outputTokens": 0}, "stopReason": "finish", "output": {"message": {"role": "", "content": [{"text": ""}]}
        self._response = {}
        self._message = None
        self._content_block = {}
        self._tool_json_input_buf = ""
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
        if "chunk" not in event:
            return

        json_bytes = event["chunk"].get("bytes", b"")
        decoded = json_bytes.decode("utf-8")
        try:
            chunk = json.loads(decoded)
        except json.JSONDecodeError:
            return

        if "amazon.titan" in self._model_id:
            self._process_amazon_titan_chunk(chunk)
        elif "amazon.nova" in self._model_id:
            self._process_amazon_nova_chunk(chunk)
        elif "anthropic.claude" in self._model_id:
            self._process_anthropic_claude_chunk(chunk)

    def _process_invocation_metrics(self, invocation_metrics):
        self._response["usage"] = {}
        if input_tokens := invocation_metrics.get("inputTokenCount"):
            self._response["usage"]["inputTokens"] = input_tokens

        if output_tokens := invocation_metrics.get("outputTokenCount"):
            self._response["usage"]["outputTokens"] = output_tokens

    def _process_amazon_titan_chunk(self, chunk):
        if (stop_reason := chunk.get("completionReason")) is not None:
            self._response["stopReason"] = stop_reason

        if invocation_metrics := chunk.get("amazon-bedrock-invocationMetrics"):
            # "amazon-bedrock-invocationMetrics":{
            #     "inputTokenCount":9,"outputTokenCount":128,"invocationLatency":3569,"firstByteLatency":2180
            # }
            self._process_invocation_metrics(invocation_metrics)

            # transform the shape of the message to match other models
            self._response["output"] = {
                "message": {"content": [{"text": chunk["outputText"]}]}
            }
            self._stream_done_callback(self._response)

    def _process_amazon_nova_chunk(self, chunk):
        # pylint: disable=too-many-branches
        if "messageStart" in chunk:
            # {'messageStart': {'role': 'assistant'}}
            if chunk["messageStart"].get("role") == "assistant":
                self._record_message = True
                self._message = {"role": "assistant", "content": []}
            return

        if "contentBlockStart" in chunk:
            # {'contentBlockStart': {'start': {'toolUse': {'toolUseId': 'id', 'name': 'name'}}, 'contentBlockIndex': 31}}
            if self._record_message:
                self._message["content"].append(self._content_block)

                start = chunk["contentBlockStart"].get("start", {})
                if "toolUse" in start:
                    self._content_block = start
                else:
                    self._content_block = {}
            return

        if "contentBlockDelta" in chunk:
            # {'contentBlockDelta': {'delta': {'text': "Hello"}, 'contentBlockIndex': 0}}
            # {'contentBlockDelta': {'delta': {'toolUse': {'input': '{"location":"San Francisco"}'}}, 'contentBlockIndex': 31}}
            if self._record_message:
                delta = chunk["contentBlockDelta"].get("delta", {})
                if "text" in delta:
                    self._content_block.setdefault("text", "")
                    self._content_block["text"] += delta["text"]
                elif "toolUse" in delta:
                    self._content_block.setdefault("toolUse", {})
                    self._content_block["toolUse"]["input"] = json.loads(
                        delta["toolUse"]["input"]
                    )
            return

        if "contentBlockStop" in chunk:
            # {'contentBlockStop': {'contentBlockIndex': 0}}
            if self._record_message:
                # create a new content block only for tools
                if "toolUse" in self._content_block:
                    self._message["content"].append(self._content_block)
                    self._content_block = {}
            return

        if "messageStop" in chunk:
            # {'messageStop': {'stopReason': 'end_turn'}}
            if stop_reason := chunk["messageStop"].get("stopReason"):
                self._response["stopReason"] = stop_reason

            if self._record_message:
                self._message["content"].append(self._content_block)
                self._content_block = {}
                self._response["output"] = {"message": self._message}
                self._record_message = False
                self._message = None
            return

        if "metadata" in chunk:
            # {'metadata': {'usage': {'inputTokens': 8, 'outputTokens': 117}, 'metrics': {}, 'trace': {}}}
            if usage := chunk["metadata"].get("usage"):
                self._response["usage"] = {}
                if input_tokens := usage.get("inputTokens"):
                    self._response["usage"]["inputTokens"] = input_tokens

                if output_tokens := usage.get("outputTokens"):
                    self._response["usage"]["outputTokens"] = output_tokens

            self._stream_done_callback(self._response)
            return

    def _process_anthropic_claude_chunk(self, chunk):
        # pylint: disable=too-many-return-statements,too-many-branches
        if not (message_type := chunk.get("type")):
            return

        if message_type == "message_start":
            # {'type': 'message_start', 'message': {'id': 'id', 'type': 'message', 'role': 'assistant', 'model': 'claude-2.0', 'content': [], 'stop_reason': None, 'stop_sequence': None, 'usage': {'input_tokens': 18, 'output_tokens': 1}}}
            if chunk.get("message", {}).get("role") == "assistant":
                self._record_message = True
                message = chunk["message"]
                self._message = {
                    "role": message["role"],
                    "content": message.get("content", []),
                }
            return

        if message_type == "content_block_start":
            # {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}}
            # {'type': 'content_block_start', 'index': 1, 'content_block': {'type': 'tool_use', 'id': 'id', 'name': 'func_name', 'input': {}}}
            if self._record_message:
                block = chunk.get("content_block", {})
                if block.get("type") == "text":
                    self._content_block = block
                elif block.get("type") == "tool_use":
                    self._content_block = block
            return

        if message_type == "content_block_delta":
            # {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': 'Here'}}
            # {'type': 'content_block_delta', 'index': 1, 'delta': {'type': 'input_json_delta', 'partial_json': ''}}
            if self._record_message:
                delta = chunk.get("delta", {})
                if delta.get("type") == "text_delta":
                    self._content_block["text"] += delta.get("text", "")
                elif delta.get("type") == "input_json_delta":
                    self._tool_json_input_buf += delta.get("partial_json", "")
            return

        if message_type == "content_block_stop":
            # {'type': 'content_block_stop', 'index': 0}
            if self._tool_json_input_buf:
                self._content_block["input"] = self._tool_json_input_buf
            self._message["content"].append(_decode_tool_use(self._content_block))
            self._content_block = {}
            self._tool_json_input_buf = ""
            return

        if message_type == "message_delta":
            # {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': 123}}
            if (stop_reason := chunk.get("delta", {}).get("stop_reason")) is not None:
                self._response["stopReason"] = stop_reason
            return

        if message_type == "message_stop":
            # {'type': 'message_stop', 'amazon-bedrock-invocationMetrics': {'inputTokenCount': 18, 'outputTokenCount': 123, 'invocationLatency': 5250, 'firstByteLatency': 290}}
            if invocation_metrics := chunk.get("amazon-bedrock-invocationMetrics"):
                self._process_invocation_metrics(invocation_metrics)

            if self._record_message:
                self._response["output"] = {"message": self._message}
                self._record_message = False
                self._message = None

            self._stream_done_callback(self._response)
            return
