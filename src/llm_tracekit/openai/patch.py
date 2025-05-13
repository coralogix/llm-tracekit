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

from timeit import default_timer
from typing import Any, Dict, Optional, Union

from openai import AsyncStream, Stream
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.semconv._incubating.attributes import (
    server_attributes as ServerAttributes,
)
from opentelemetry.trace import Span, SpanKind, Tracer

from llm_tracekit.instrumentation_utils import handle_span_exception
from llm_tracekit.instruments import Instruments
from llm_tracekit.openai.utils import (
    get_llm_request_attributes,
    get_llm_response_attributes,
    is_streaming,
)
from llm_tracekit.span_builder import (
    Choice,
    ToolCall,
    attribute_generator,
    generate_choice_attributes,
    generate_response_attributes,
)


def chat_completions_create(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    """Wrap the `create` method of the `ChatCompletion` class to trace it."""

    def traced_method(wrapped, instance, args, kwargs):
        span_attributes = {
            **get_llm_request_attributes(kwargs, instance, capture_content)
        }

        span_name = f"{span_attributes[GenAIAttributes.GEN_AI_OPERATION_NAME]} {span_attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL]}"
        with tracer.start_as_current_span(
            name=span_name,
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            start = default_timer()
            result = None
            error_type = None
            try:
                result = wrapped(*args, **kwargs)
                if is_streaming(kwargs):
                    return StreamWrapper(result, span, capture_content)

                if span.is_recording():
                    span.set_attributes(
                        get_llm_response_attributes(result, capture_content)
                    )

                span.end()
                return result

            except Exception as error:
                error_type = type(error).__qualname__
                handle_span_exception(span, error)
                raise
            finally:
                duration = max((default_timer() - start), 0)
                _record_metrics(
                    instruments,
                    duration,
                    result,
                    span_attributes,
                    error_type,
                )

    return traced_method


def async_chat_completions_create(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    """Wrap the `create` method of the `AsyncChatCompletion` class to trace it."""

    async def traced_method(wrapped, instance, args, kwargs):
        span_attributes = {**get_llm_request_attributes(kwargs, instance, capture_content)}

        span_name = f"{span_attributes[GenAIAttributes.GEN_AI_OPERATION_NAME]} {span_attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL]}"
        with tracer.start_as_current_span(
            name=span_name,
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            start = default_timer()
            result = None
            error_type = None
            try:
                result = await wrapped(*args, **kwargs)
                if is_streaming(kwargs):
                    return AsyncStreamWrapper(result, span, capture_content)

                if span.is_recording():
                    span.set_attributes(
                        get_llm_response_attributes(result, capture_content)
                    )

                span.end()
                return result

            except Exception as error:
                error_type = type(error).__qualname__
                handle_span_exception(span, error)
                raise
            finally:
                duration = max((default_timer() - start), 0)
                _record_metrics(
                    instruments,
                    duration,
                    result,
                    span_attributes,
                    error_type,
                )

    return traced_method


def _record_metrics(
    instruments: Instruments,
    duration: float,
    result,
    span_attributes: dict,
    error_type: Optional[str],
):
    common_attributes = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: GenAIAttributes.GenAiOperationNameValues.CHAT.value,
        GenAIAttributes.GEN_AI_SYSTEM: GenAIAttributes.GenAiSystemValues.OPENAI.value,
        GenAIAttributes.GEN_AI_REQUEST_MODEL: span_attributes[
            GenAIAttributes.GEN_AI_REQUEST_MODEL
        ],
    }

    if error_type:
        common_attributes["error.type"] = error_type

    if result and getattr(result, "model", None):
        common_attributes[GenAIAttributes.GEN_AI_RESPONSE_MODEL] = result.model

    if result and getattr(result, "service_tier", None):
        common_attributes[GenAIAttributes.GEN_AI_OPENAI_RESPONSE_SERVICE_TIER] = (
            result.service_tier
        )

    if result and getattr(result, "system_fingerprint", None):
        common_attributes[GenAIAttributes.GEN_AI_OPENAI_RESPONSE_SYSTEM_FINGERPRINT] = (
            result.system_fingerprint
        )

    if ServerAttributes.SERVER_ADDRESS in span_attributes:
        common_attributes[ServerAttributes.SERVER_ADDRESS] = span_attributes[
            ServerAttributes.SERVER_ADDRESS
        ]

    if ServerAttributes.SERVER_PORT in span_attributes:
        common_attributes[ServerAttributes.SERVER_PORT] = span_attributes[
            ServerAttributes.SERVER_PORT
        ]

    instruments.operation_duration_histogram.record(
        duration,
        attributes=common_attributes,
    )

    if result and getattr(result, "usage", None):
        input_attributes = {
            **common_attributes,
            GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.INPUT.value,
        }
        instruments.token_usage_histogram.record(
            result.usage.prompt_tokens,
            attributes=input_attributes,
        )

        completion_attributes = {
            **common_attributes,
            GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.COMPLETION.value,
        }
        instruments.token_usage_histogram.record(
            result.usage.completion_tokens,
            attributes=completion_attributes,
        )


class ToolCallBuffer:
    def __init__(self, index, tool_call_id, function_name):
        self.index = index
        self.function_name = function_name
        self.tool_call_id = tool_call_id
        self.arguments = []

    def append_arguments(self, arguments):
        self.arguments.append(arguments)


class ChoiceBuffer:
    def __init__(self, index):
        self.index = index
        self.finish_reason = None
        self.text_content = []
        self.tool_calls_buffers = []

    def append_text_content(self, content):
        self.text_content.append(content)

    def append_tool_call(self, tool_call):
        idx = tool_call.index
        # make sure we have enough tool call buffers
        for _ in range(len(self.tool_calls_buffers), idx + 1):
            self.tool_calls_buffers.append(None)

        if not self.tool_calls_buffers[idx]:
            self.tool_calls_buffers[idx] = ToolCallBuffer(
                idx, tool_call.id, tool_call.function.name
            )
        self.tool_calls_buffers[idx].append_arguments(tool_call.function.arguments)


class BaseStreamWrapper:
    span: Span
    response_id: Optional[str] = None
    response_model: Optional[str] = None
    service_tier: Optional[str] = None
    finish_reasons: list = []
    prompt_tokens: Optional[int] = 0
    completion_tokens: Optional[int] = 0

    def __init__(
        self,
        stream: Union[Stream, AsyncStream],
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
    def _generate_response_attributes(self) -> Dict[str, Any]:
        parsed_choices = []
        for choice in self.choice_buffers:
            content = None
            if choice.text_content:
                content = "".join(choice.text_content)

            tool_calls = None
            if choice.tool_calls_buffers:
                tool_calls = []
                for tool_call in choice.tool_calls_buffers:
                    tool_calls.append(
                        ToolCall(
                            id=tool_call.tool_call_id,
                            type="function",
                            function_name=tool_call.function_name,
                            function_arguments="".join(tool_call.arguments),
                        )
                    )

            parsed_choices.append(
                Choice(
                    finish_reason=choice.finish_reason or "error",
                    role="assistant",
                    content=content,
                    tool_calls=tool_calls,
                )
            )

        return {
            GenAIAttributes.GEN_AI_OPENAI_RESPONSE_SERVICE_TIER: self.service_tier,
            **generate_response_attributes(
                model=self.response_model,
                id=self.response_id,
                finish_reasons=self.finish_reasons,
                usage_input_tokens=self.prompt_tokens,
                usage_output_tokens=self.completion_tokens,
            ),
            **generate_choice_attributes(parsed_choices, self.capture_content),
        }

    def cleanup(self):
        if not self._span_started:
            return

        span_attributes = {}
        if self.span.is_recording():
            span_attributes = self._generate_response_attributes()

        self.span.set_attributes(span_attributes)
        self.span.end()
        self._span_started = False

    def set_response_model(self, chunk):
        if self.response_model:
            return

        if getattr(chunk, "model", None):
            self.response_model = chunk.model

    def set_response_id(self, chunk):
        if self.response_id:
            return

        if getattr(chunk, "id", None):
            self.response_id = chunk.id

    def set_response_service_tier(self, chunk):
        if self.service_tier:
            return

        if getattr(chunk, "service_tier", None):
            self.service_tier = chunk.service_tier

    def build_streaming_response(self, chunk):
        if getattr(chunk, "choices", None) is None:
            return

        choices = chunk.choices
        for choice in choices:
            if not choice.delta:
                continue

            # make sure we have enough choice buffers
            for idx in range(len(self.choice_buffers), choice.index + 1):
                self.choice_buffers.append(ChoiceBuffer(idx))

            if choice.finish_reason:
                self.choice_buffers[choice.index].finish_reason = choice.finish_reason

            if choice.delta.content is not None:
                self.choice_buffers[choice.index].append_text_content(
                    choice.delta.content
                )

            if choice.delta.tool_calls is not None:
                for tool_call in choice.delta.tool_calls:
                    self.choice_buffers[choice.index].append_tool_call(tool_call)

    def set_usage(self, chunk):
        if getattr(chunk, "usage", None):
            self.completion_tokens = chunk.usage.completion_tokens
            self.prompt_tokens = chunk.usage.prompt_tokens

    def process_chunk(self, chunk):
        self.set_response_id(chunk)
        self.set_response_model(chunk)
        self.set_response_service_tier(chunk)
        self.build_streaming_response(chunk)
        self.set_usage(chunk)


class StreamWrapper(BaseStreamWrapper):
    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                handle_span_exception(self.span, exc_val)
        finally:
            self.cleanup()
        return False  # Propagate the exception

    def close(self):
        """Close the underlying stream, handling both sync and async cases."""
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


class AsyncStreamWrapper(BaseStreamWrapper):
    async def __aenter__(self):
        self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                handle_span_exception(self.span, exc_val)
        finally:
            self.cleanup()
        return False  # Propagate the exception

    async def aclose(self):
        """Asynchronously close the underlying stream."""
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
