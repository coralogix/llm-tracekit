import json
from collections import defaultdict
from contextlib import suppress
from enum import Enum
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
    generate_base_attributes,
    generate_choice_attributes,
    generate_message_attributes,
    generate_request_attributes,
    generate_response_attributes,
    remove_attributes_with_null_values,
)


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


def _parse_claude_message(
    role: Optional[str], content: Optional[Union[str, list]]
) -> List[Message]:
    """Attempts to combine the content parts of a `converse` API message to a single message."""
    if isinstance(content, str):
        return [Message(role=role, content=content)]

    if isinstance(content, list):
        # TODO: explain this mess
        content_blocks_by_type = defaultdict(list)
        for block in content:
            content_blocks_by_type[block.get("type")].append(block)

        if "tool_use" in content_blocks_by_type:
            tool_calls = []
            for block in content_blocks_by_type["tool_use"]:
                arguments = None
                if "input" in block:
                    arguments = json.dumps(block["input"])

                tool_calls.append(
                    ToolCall(
                        id=block.get("id"),
                        type="function",
                        function_name=block.get("name"),
                        function_arguments=arguments,
                    )
                )

            return [Message(role=role, tool_calls=tool_calls)]

        messages = []
        if "tool_result" in content_blocks_by_type:
            for tool_result in content_blocks_by_type["tool_result"]:
                tool_result_content = tool_result.get("content")
                if not isinstance(tool_result_content, str):
                    tool_result_content = None

                messages.append(
                    Message(
                        role=role,
                        tool_call_id=tool_result.get("tool_use_id"),
                        content=tool_result_content,
                    )
                )
        if "text" in content_blocks_by_type:
            text_parts = [
                block["text"]
                for block in content_blocks_by_type["text"]
                if block.get("text") is not None
            ]
            messages.append(Message(role=role, content="".join(text_parts)))

        if len(messages) > 0:
            return messages

    return [Message(role=role)]


def _generate_claude_request_and_message_attributes(
    model_id: Optional[str], parsed_body: Dict[str, Any], capture_content: bool
) -> Dict[str, Any]:
    messages = []
    if "system" in parsed_body and isinstance(parsed_body["system"], str):
        messages.append(Message(role="system", content=parsed_body["system"]))

    for message in parsed_body.get("messages", []):
        messages.extend(
            _parse_claude_message(
                role=message.get("role"), content=message.get("content")
            )
        )

    tool_attributes = {}
    tools = parsed_body.get("tools", [])
    for index, tool_definition in enumerate(tools):
        tool_params = None
        if (
            "input_schema" in tool_definition
            and "properties" in tool_definition["input_schema"]
        ):
            with suppress(TypeError):
                tool_params = json.dumps(tool_definition["input_schema"])

        tool_attributes.update(
            {
                ExtendedGenAIAttributes.GEN_AI_BEDROCK_REQUEST_TOOLS_FUNCTION_NAME.format(
                    tool_index=index
                ): tool_definition.get("name"),
                ExtendedGenAIAttributes.GEN_AI_BEDROCK_REQUEST_TOOLS_FUNCTION_DESCRIPTION.format(
                    tool_index=index
                ): tool_definition.get("description"),
                ExtendedGenAIAttributes.GEN_AI_BEDROCK_REQUEST_TOOLS_FUNCTION_PARAMETERS.format(
                    tool_index=index
                ): tool_params,
            }
        )

    return {
        **generate_request_attributes(
            model=model_id,
            max_tokens=parsed_body.get("max_tokens"),
            temperature=parsed_body.get("temperature"),
            top_p=parsed_body.get("top_p"),
        ),
        **generate_message_attributes(
            messages=messages, capture_content=capture_content
        ),
        **remove_attributes_with_null_values(tool_attributes),
    }


def _generate_claude_response_and_choice_attributes(
    parsed_body: Dict[str, Any], capture_content: bool
) -> Dict[str, Any]:
    finish_reason = parsed_body.get("stop_reason")
    usage_data = parsed_body.get("usage", {})
    parsed_response_message = _parse_claude_message(
        role=parsed_body.get("role"), content=parsed_body.get("content")
    )[0]
    choice = Choice(
        finish_reason=finish_reason,
        role=parsed_response_message.role,
        content=parsed_response_message.content,
        tool_calls=parsed_response_message.tool_calls,
    )

    return {
        **generate_response_attributes(
            model=parsed_body.get("model"),
            finish_reasons=[] if finish_reason is None else [finish_reason],
            id=parsed_body.get("id"),
            usage_input_tokens=usage_data.get("input_tokens"),
            usage_output_tokens=usage_data.get("output_tokens"),
        ),
        **generate_choice_attributes(choices=[choice], capture_content=capture_content),
    }


def _generate_llama_request_and_message_attributes(
    model_id: Optional[str], parsed_body: Dict[str, Any], capture_content: bool
) -> Dict[str, Any]:
    attributes = generate_request_attributes(
        model=model_id,
        max_tokens=parsed_body.get("max_gen_len"),
        temperature=parsed_body.get("temperature"),
        top_p=parsed_body.get("top_p"),
    )
    if "prompt" in parsed_body:
        messages = [Message(role="user", content=parsed_body["prompt"])]
        attributes.update(
            generate_message_attributes(
                messages=messages, capture_content=capture_content
            )
        )

    return attributes


def _generate_llama_response_and_choice_attributes(
    model_id: Optional[str], parsed_body: Dict[str, Any], capture_content: bool
) -> Dict[str, Any]:
    finish_reason = parsed_body.get("stop_reason")
    usage_input_tokens = parsed_body.get("prompt_token_count")
    usage_output_tokens = parsed_body.get("generation_token_count")
    return {
        **generate_response_attributes(
            model=model_id,
            finish_reasons=None if finish_reason is None else [finish_reason],
            usage_input_tokens=usage_input_tokens,
            usage_output_tokens=usage_output_tokens,
        ),
        **generate_choice_attributes(
            choices=[
                Choice(
                    finish_reason=finish_reason,
                    role="assistant",
                    content=parsed_body.get("generation"),
                )
            ],
            capture_content=capture_content,
        ),
    }


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


def record_invoke_model_result_attributes(
    result_body: Union[str, Dict[str, Any]],
    span: Span,
    start_time: float,
    instruments: Instruments,
    capture_content: bool,
    model_id: Optional[str],
):
    usage_input_tokens = None
    usage_output_tokens = None
    try:
        model_type = _get_model_type_from_model_id(model_id)
        if model_type is None:
            return

        parsed_body = {}
        if isinstance(result_body, dict):
            parsed_body = result_body
        elif isinstance(result_body, (str, bytes)):
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
            usage_input_tokens = parsed_body.get("prompt_token_count")
            usage_output_tokens = parsed_body.get("generation_token_count")
        elif model_type is _ModelType.CLAUDE:
            span.set_attributes(
                _generate_claude_response_and_choice_attributes(
                    parsed_body=parsed_body, capture_content=capture_content
                )
            )
            usage_input_tokens = parsed_body.get("usage", {}).get("input_tokens")
            usage_output_tokens = parsed_body.get("usage", {}).get("output_tokens")

    finally:
        duration = max((default_timer() - start_time), 0)
        span.end()
        record_metrics(
            instruments=instruments,
            duration=duration,
            model=model_id,
            usage_input_tokens=usage_input_tokens,
            usage_output_tokens=usage_output_tokens,
        )


class InvokeModelWithResponseStreamWrapper(ObjectProxy):
    """Wrapper for botocore.eventstream.EventStream"""

    def __init__(
        self,
        stream: EventStream,
        stream_done_callback: Callable[[Dict[str, Union[int, str]]], None],
        stream_error_callback: Callable[[Exception], None],
        model_id: Optional[str],
    ):
        super().__init__(stream)

        self._stream_done_callback = stream_done_callback
        self._stream_error_callback = stream_error_callback
        self._model_id = model_id

        # accumulating things in the same shape of the Converse API
        # {"usage": {"inputTokens": 0, "outputTokens": 0}, "stopReason": "finish", "output": {"message": {"role": "", "content": [{"text": ""}]}
        self._response: Dict[str, Any] = {}
        self._message = None
        self._content_block: Dict[str, Any] = {}
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

        model_type = _get_model_type_from_model_id(self._model_id)

        if model_type is _ModelType.LLAMA3:
            self._process_meta_llama_chunk(chunk)
        elif model_type is _ModelType.CLAUDE:
            self._process_anthropic_claude_chunk(chunk)

    def _process_meta_llama_invocation_metrics(self, invocation_metrics):
        if input_tokens := invocation_metrics.get("inputTokenCount"):
            self._response["prompt_token_count"] = input_tokens
        if output_tokens := invocation_metrics.get("outputTokenCount"):
            self._response["generation_token_count"] = output_tokens

    def _process_anthropic_claude_invocation_metrics(self, invocation_metrics):
        self._response["usage"] = {}
        if input_tokens := invocation_metrics.get("inputTokenCount"):
            self._response["usage"]["input_tokens"] = input_tokens

        if output_tokens := invocation_metrics.get("outputTokenCount"):
            self._response["usage"]["output_tokens"] = output_tokens

    def _process_meta_llama_chunk(self, chunk):
        if self._message is None:
            self._message = {"generation": ""}

        self._message["generation"] += chunk.get("generation", "")

        if chunk.get("stop_reason") is not None and self._message is not None:
            if invocation_metrics := chunk.get("amazon-bedrock-invocationMetrics"):
                self._process_meta_llama_invocation_metrics(invocation_metrics)

            self._response["stop_reason"] = chunk["stop_reason"]
            self._response["generation"] = self._message["generation"]
            self._message = None

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
                    "model": message["model"],
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

            if self._message is not None:
                self._message["content"].append(
                    decode_tool_use_in_stream(self._content_block)
                )
            self._content_block = {}
            self._tool_json_input_buf = ""
            return

        if message_type == "message_delta":
            # {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': 123}}
            if (stop_reason := chunk.get("delta", {}).get("stop_reason")) is not None:
                self._response["stop_reason"] = stop_reason
            return

        if message_type == "message_stop":
            # {'type': 'message_stop', 'amazon-bedrock-invocationMetrics': {'inputTokenCount': 18, 'outputTokenCount': 123, 'invocationLatency': 5250, 'firstByteLatency': 290}}
            if invocation_metrics := chunk.get("amazon-bedrock-invocationMetrics"):
                self._process_anthropic_claude_invocation_metrics(invocation_metrics)

            if self._record_message and self._message is not None:
                self._response["model"] = self._message["model"]
                self._response["role"] = self._message["role"]
                self._response["content"] = self._message["content"]
                self._record_message = False
                self._message = None

            self._stream_done_callback(self._response)
            return
