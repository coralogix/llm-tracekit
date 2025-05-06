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
    generate_base_attributes,
    generate_choice_attributes,
    generate_message_attributes,
    generate_request_attributes,
    generate_response_attributes,
    remove_attributes_with_null_values,
)


def _combine_tool_call_content_parts(
    content_parts: List[Dict[str, Any]],
) -> Optional[str]:
    text_parts = []
    for content_part in content_parts:
        if "text" in content_part:
            text_parts.append(content_part["text"])

        if "json" in content_part:
            return json.dumps(content_part["json"])

    if len(text_parts) > 0:
        return "".join(text_parts)

    return None


def _parse_converse_message(
    role: Optional[str], content_parts: Optional[List[Dict[str, Any]]]
) -> List[Message]:
    """Attempts to combine the content parts of a `converse` API message to a single message."""
    if content_parts is None:
        return [Message(role=role)]

    text_parts = []
    tool_calls = []
    tool_call_results = []

    # Get all the content parts we support
    for content_part in content_parts:
        if "text" in content_part:
            text_parts.append(content_part["text"])

        if "toolUse" in content_part:
            tool_calls.append(content_part["toolUse"])

        if "toolResult" in content_part:
            tool_call_results.append(content_part["toolResult"])

    # TODO: explain this mess
    if len(tool_calls) > 0:
        message_tool_calls = []
        for tool_call in tool_calls:
            arguments = None
            if "input" in tool_call:
                arguments = json.dumps(tool_call["input"])

            message_tool_calls.append(
                ToolCall(
                    id=tool_call.get("toolUseId"),
                    type="function",
                    function_name=tool_call.get("name"),
                    function_arguments=arguments,
                )
            )

        return [
            Message(
                role=role,
                tool_calls=message_tool_calls,
            )
        ]

    messages = []
    if len(tool_call_results) > 0:
        for tool_call_result in tool_call_results:
            content = None
            if "content" in tool_call_result:
                content = _combine_tool_call_content_parts(tool_call_result["content"])

            messages.append(
                Message(
                    role=role,
                    tool_call_id=tool_call_result.get("toolUseId"),
                    content=content,
                )
            )
    if len(text_parts) > 0:
        messages.append(Message(role=role, content="".join(text_parts)))

    if len(messages) > 0:
        return messages

    return [Message(role=role)]


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
                role=message.get("role"), content_parts=message.get("content")
            )
        )

    tool_attributes = {}
    tool_configs = kwargs.get("toolConfig", {}).get("tools", [])
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
        **remove_attributes_with_null_values(tool_attributes),
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
            content_parts=response_message.get("content"),
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
        model=model,
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
            if stop_reason := event["messageStop"].get("stopReason"):
                self._response["stopReason"] = stop_reason

            if self._record_message:
                self._response["output"] = {"message": self._message}
                self._record_message = False
                self._message = None

            return

        if "metadata" in event:
            # {'metadata': {'usage': {'inputTokens': 12, 'outputTokens': 15, 'totalTokens': 27}, 'metrics': {'latencyMs': 2980}}}
            if usage := event["metadata"].get("usage"):
                self._response["usage"] = {}
                if input_tokens := usage.get("inputTokens"):
                    self._response["usage"]["inputTokens"] = input_tokens

                if output_tokens := usage.get("outputTokens"):
                    self._response["usage"]["outputTokens"] = output_tokens

            self._stream_done_callback(self._response)

            return
