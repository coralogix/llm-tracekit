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

from typing import Any, Literal

from openai import AsyncStream, Stream
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.trace import Span

from llm_tracekit.core import (
    ToolCall,
    Choice,
    attribute_generator,
    generate_choice_attributes,
    generate_response_attributes,
    handle_span_exception,
)
from llm_tracekit.microsoft_foundry.utils import (
    get_responses_response_attributes,
)


class ToolCallBuffer:
    def __init__(self, index, tool_call_id, function_name):
        self.index = index
        self.function_name = function_name
        self.tool_call_id = tool_call_id
        self.arguments: list[str] = []

    def append_arguments(self, arguments):
        if arguments:
            self.arguments.append(arguments)


class ChoiceBuffer:
    def __init__(self, index):
        self.index = index
        self.finish_reason = None
        self.text_content: list[str] = []
        self.tool_calls_buffers: list[ToolCallBuffer | None] = []

    def append_text_content(self, content):
        if content:
            self.text_content.append(content)

    def append_tool_call(self, tool_call):
        idx = tool_call.index
        for _ in range(len(self.tool_calls_buffers), idx + 1):
            self.tool_calls_buffers.append(None)

        if not self.tool_calls_buffers[idx]:
            func = getattr(tool_call, "function", None)
            func_name = getattr(func, "name", None) if func else None
            self.tool_calls_buffers[idx] = ToolCallBuffer(idx, tool_call.id, func_name)

        func = getattr(tool_call, "function", None)
        if func:
            args = getattr(func, "arguments", None)
            if args and self.tool_calls_buffers[idx]:
                self.tool_calls_buffers[idx].append_arguments(args)


class BaseChatStreamWrapper:
    span: Span
    response_id: str | None = None
    response_model: str | None = None
    service_tier: str | None = None
    finish_reasons: list = []
    prompt_tokens: int | None = 0
    completion_tokens: int | None = 0

    def __init__(
        self,
        stream: Stream | AsyncStream,
        span: Span,
        capture_content: bool,
    ):
        self.stream = stream
        self.span = span
        self.choice_buffers: list[ChoiceBuffer] = []
        self._span_started = False
        self.capture_content = capture_content
        self.setup()

    def setup(self):
        if not self._span_started:
            self._span_started = True

    @attribute_generator
    def _generate_response_attributes(self) -> dict[str, Any]:
        parsed_choices = []
        finish_reasons = []
        for choice in self.choice_buffers:
            content = None
            if choice.text_content:
                content = "".join(choice.text_content)

            tool_calls = None
            if choice.tool_calls_buffers:
                tool_calls = []
                for tool_call in choice.tool_calls_buffers:
                    if tool_call:
                        tool_calls.append(
                            ToolCall(
                                id=tool_call.tool_call_id,
                                type="function",
                                function_name=tool_call.function_name,
                                function_arguments="".join(tool_call.arguments),
                            )
                        )

            finish_reason = choice.finish_reason or "error"
            finish_reasons.append(finish_reason)
            parsed_choices.append(
                Choice(
                    finish_reason=finish_reason,
                    role="assistant",
                    content=content,
                    tool_calls=tool_calls if tool_calls else None,
                )
            )

        attributes: dict[str, Any] = {
            **generate_response_attributes(
                model=self.response_model,
                id=self.response_id,
                finish_reasons=finish_reasons if finish_reasons else None,
                usage_input_tokens=self.prompt_tokens,
                usage_output_tokens=self.completion_tokens,
            ),
            **generate_choice_attributes(parsed_choices, self.capture_content),
        }

        if self.service_tier:
            attributes[GenAIAttributes.GEN_AI_OPENAI_RESPONSE_SERVICE_TIER] = (
                self.service_tier
            )

        return attributes

    def cleanup(self):
        if not self._span_started:
            return

        if self.span.is_recording():
            span_attributes = self._generate_response_attributes()
            self.span.set_attributes(span_attributes)

        self.span.end()
        self._span_started = False

    def set_response_model(self, chunk):
        if self.response_model:
            return
        model = getattr(chunk, "model", None)
        if model:
            self.response_model = model

    def set_response_id(self, chunk):
        if self.response_id:
            return
        chunk_id = getattr(chunk, "id", None)
        if chunk_id:
            self.response_id = chunk_id

    def set_response_service_tier(self, chunk):
        if self.service_tier:
            return
        tier = getattr(chunk, "service_tier", None)
        if tier:
            self.service_tier = tier

    def build_streaming_response(self, chunk):
        choices = getattr(chunk, "choices", None)
        if choices is None:
            return

        for choice in choices:
            delta = getattr(choice, "delta", None)
            if not delta:
                continue

            choice_index = getattr(choice, "index", 0)
            for idx in range(len(self.choice_buffers), choice_index + 1):
                self.choice_buffers.append(ChoiceBuffer(idx))

            finish_reason = getattr(choice, "finish_reason", None)
            if finish_reason:
                self.choice_buffers[choice_index].finish_reason = finish_reason

            content = getattr(delta, "content", None)
            if content is not None:
                self.choice_buffers[choice_index].append_text_content(content)

            tool_calls = getattr(delta, "tool_calls", None)
            if tool_calls is not None:
                for tool_call in tool_calls:
                    self.choice_buffers[choice_index].append_tool_call(tool_call)

    def set_usage(self, chunk):
        usage = getattr(chunk, "usage", None)
        if usage:
            self.completion_tokens = getattr(usage, "completion_tokens", None)
            self.prompt_tokens = getattr(usage, "prompt_tokens", None)

    def process_chunk(self, chunk):
        self.set_response_id(chunk)
        self.set_response_model(chunk)
        self.set_response_service_tier(chunk)
        self.build_streaming_response(chunk)
        self.set_usage(chunk)


class ChatStreamWrapper(BaseChatStreamWrapper):
    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                handle_span_exception(self.span, exc_val)
        finally:
            self.cleanup()
        return False

    def close(self):
        self.stream.close()
        self.cleanup()

    def __iter__(self):
        return self

    def __next__(self):
        try:
            chunk = next(self.stream)
            self.process_chunk(chunk)
            return chunk
        except StopIteration:
            self.cleanup()
            raise
        except Exception as error:
            handle_span_exception(self.span, error)
            self.cleanup()
            raise


class AsyncChatStreamWrapper(BaseChatStreamWrapper):
    async def __aenter__(self):
        self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                handle_span_exception(self.span, exc_val)
        finally:
            self.cleanup()
        return False

    async def aclose(self):
        await self.stream.close()
        self.cleanup()

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            chunk = await self.stream.__anext__()
            self.process_chunk(chunk)
            return chunk
        except StopAsyncIteration:
            self.cleanup()
            raise
        except Exception as error:
            handle_span_exception(self.span, error)
            self.cleanup()
            raise

    def parse(self):
        return self.stream.parse()


class ResponsesStreamWrapper:
    """Wrap Responses API SSE streams; finalize span on response.completed."""

    def __init__(self, stream: Stream, span: Span, capture_content: bool) -> None:
        self.stream = stream
        self.span = span
        self.capture_content = capture_content
        self._final_response: Any = None
        self._stream_error: Any = None
        self._span_finalized = False

    def process_event(self, event: Any) -> None:
        etype = getattr(event, "type", None)
        if etype == "response.completed":
            self._final_response = getattr(event, "response", None)
        elif etype == "response.failed":
            self._final_response = getattr(event, "response", None)
        elif etype == "response.done":
            resp = getattr(event, "response", None)
            if resp is not None:
                self._final_response = resp
        elif etype == "error":
            self._stream_error = event

    def cleanup(self) -> None:
        if self._span_finalized:
            return
        self._span_finalized = True
        if self._stream_error is not None:
            msg = getattr(self._stream_error, "message", str(self._stream_error))
            handle_span_exception(self.span, RuntimeError(msg))
        elif self._final_response is not None and self.span.is_recording():
            self.span.set_attributes(
                get_responses_response_attributes(
                    self._final_response, self.capture_content
                )
            )
        else:
            response = getattr(self.stream, "response", None)
            if response is not None and self.span.is_recording():
                self.span.set_attributes(
                    get_responses_response_attributes(response, self.capture_content)
                )
        self.span.end()

    def __enter__(self) -> "ResponsesStreamWrapper":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> Literal[False]:
        try:
            if exc_type is not None:
                handle_span_exception(self.span, exc_val)
        finally:
            self.cleanup()
        return False

    def close(self) -> None:
        self.stream.close()
        self.cleanup()

    def __iter__(self) -> "ResponsesStreamWrapper":
        return self

    def __next__(self) -> Any:
        try:
            event = next(self.stream)
            self.process_event(event)
            return event
        except StopIteration:
            self.cleanup()
            raise
        except Exception as error:
            handle_span_exception(self.span, error)
            self.cleanup()
            raise


class AsyncResponsesStreamWrapper:
    """Async variant of ResponsesStreamWrapper."""

    def __init__(self, stream: AsyncStream, span: Span, capture_content: bool) -> None:
        self.stream = stream
        self.span = span
        self.capture_content = capture_content
        self._final_response: Any = None
        self._stream_error: Any = None
        self._span_finalized = False

    def process_event(self, event: Any) -> None:
        etype = getattr(event, "type", None)
        if etype == "response.completed":
            self._final_response = getattr(event, "response", None)
        elif etype == "response.failed":
            self._final_response = getattr(event, "response", None)
        elif etype == "response.done":
            resp = getattr(event, "response", None)
            if resp is not None:
                self._final_response = resp
        elif etype == "error":
            self._stream_error = event

    def cleanup(self) -> None:
        if self._span_finalized:
            return
        self._span_finalized = True
        if self._stream_error is not None:
            msg = getattr(self._stream_error, "message", str(self._stream_error))
            handle_span_exception(self.span, RuntimeError(msg))
        elif self._final_response is not None and self.span.is_recording():
            self.span.set_attributes(
                get_responses_response_attributes(
                    self._final_response, self.capture_content
                )
            )
        else:
            response = getattr(self.stream, "response", None)
            if response is not None and self.span.is_recording():
                self.span.set_attributes(
                    get_responses_response_attributes(response, self.capture_content)
                )
        self.span.end()

    async def __aenter__(self) -> "AsyncResponsesStreamWrapper":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        try:
            if exc_type is not None:
                handle_span_exception(self.span, exc_val)
        finally:
            self.cleanup()
        return False

    async def aclose(self) -> None:
        await self.stream.close()
        self.cleanup()

    def __aiter__(self) -> "AsyncResponsesStreamWrapper":
        return self

    async def __anext__(self) -> Any:
        try:
            event = await self.stream.__anext__()
            self.process_event(event)
            return event
        except StopAsyncIteration:
            self.cleanup()
            raise
        except Exception as error:
            handle_span_exception(self.span, error)
            self.cleanup()
            raise
