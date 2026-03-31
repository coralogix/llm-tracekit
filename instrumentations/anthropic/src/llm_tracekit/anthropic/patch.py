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

from __future__ import annotations

from timeit import default_timer
from typing import Any

from anthropic._streaming import AsyncStream, Stream
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.semconv._incubating.attributes import (
    server_attributes as ServerAttributes,
)
from opentelemetry.trace import Span, SpanKind, Tracer
from opentelemetry.util.types import AttributeValue

from types import SimpleNamespace

from llm_tracekit.core import (
    Choice,
    ToolCall,
    handle_span_exception,
    Instruments,
    generate_choice_attributes,
    generate_response_attributes,
)
from llm_tracekit.anthropic.utils import (
    get_message_response_attributes,
    get_messages_request_attributes,
    is_streaming,
    stop_reason_to_finish_reason,
)


def messages_create(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    """Wrap sync `Messages.create`."""

    def traced_method(wrapped, instance, args, kwargs):
        span_attributes = dict(
            get_messages_request_attributes(kwargs, instance, capture_content)
        )

        span_name = (
            f"{span_attributes[GenAIAttributes.GEN_AI_OPERATION_NAME]} "
            f"{span_attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL]}"
        )
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
                    return AnthropicStreamWrapper(
                        result,
                        span,
                        capture_content,
                        span_attributes,
                        instruments,
                        start,
                    )

                if span.is_recording():
                    span.set_attributes(
                        get_message_response_attributes(result, capture_content)
                    )

                span.end()
                return result

            except Exception as error:
                error_type = type(error).__qualname__
                handle_span_exception(span, error)
                raise
            finally:
                duration = max((default_timer() - start), 0)
                if not is_streaming(kwargs):
                    _record_metrics(
                        instruments,
                        duration,
                        result,
                        span_attributes,
                        error_type,
                    )

    return traced_method


def async_messages_create(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    """Wrap async `AsyncMessages.create`."""

    async def traced_method(wrapped, instance, args, kwargs):
        span_attributes = dict(
            get_messages_request_attributes(kwargs, instance, capture_content)
        )

        span_name = (
            f"{span_attributes[GenAIAttributes.GEN_AI_OPERATION_NAME]} "
            f"{span_attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL]}"
        )
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
                    return AnthropicAsyncStreamWrapper(
                        result,
                        span,
                        capture_content,
                        span_attributes,
                        instruments,
                        start,
                    )

                if span.is_recording():
                    span.set_attributes(
                        get_message_response_attributes(result, capture_content)
                    )

                span.end()
                return result

            except Exception as error:
                error_type = type(error).__qualname__
                handle_span_exception(span, error)
                raise
            finally:
                duration = max((default_timer() - start), 0)
                if not is_streaming(kwargs):
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
    result: Any,
    span_attributes: dict[str, Any],
    error_type: str | None,
) -> None:
    common_attributes: dict[str, AttributeValue] = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: GenAIAttributes.GenAiOperationNameValues.CHAT.value,
        GenAIAttributes.GEN_AI_SYSTEM: GenAIAttributes.GenAiSystemValues.ANTHROPIC.value,
        GenAIAttributes.GEN_AI_REQUEST_MODEL: span_attributes[
            GenAIAttributes.GEN_AI_REQUEST_MODEL
        ],
    }

    if error_type:
        common_attributes["error.type"] = error_type

    if result and getattr(result, "model", None):
        common_attributes[GenAIAttributes.GEN_AI_RESPONSE_MODEL] = str(result.model)

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

    usage = getattr(result, "usage", None) if result else None
    if usage:
        in_tok = getattr(usage, "input_tokens", None)
        out_tok = getattr(usage, "output_tokens", None)
        if in_tok is not None:
            input_attributes = {
                **common_attributes,
                GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.INPUT.value,
            }
            instruments.token_usage_histogram.record(
                in_tok,
                attributes=input_attributes,
            )
        if out_tok is not None:
            completion_attributes = {
                **common_attributes,
                GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.COMPLETION.value,
            }
            instruments.token_usage_histogram.record(
                out_tok,
                attributes=completion_attributes,
            )


class _AnthropicStreamAccumState:
    def __init__(self) -> None:
        self.message_id: str | None = None
        self.response_model: str | None = None
        self.text_parts: list[str] = []
        self.stop_reason: Any = None
        self.input_tokens: int | None = None
        self.output_tokens: int | None = None
        self._tool_meta: dict[int, tuple[str, str]] = {}
        self._tool_json_parts: dict[int, list[str]] = {}

    def process_event(self, event: Any) -> None:
        et = getattr(event, "type", None)
        if et == "message_start":
            msg = getattr(event, "message", None)
            if msg:
                self.message_id = getattr(msg, "id", None)
                mdl = getattr(msg, "model", None)
                if mdl is not None:
                    self.response_model = str(mdl)
        elif et == "content_block_start":
            idx = getattr(event, "index", 0)
            block = getattr(event, "content_block", None)
            if block is None:
                return
            bt = getattr(block, "type", None)
            if bt == "tool_use":
                tid = getattr(block, "id", "") or ""
                name = getattr(block, "name", "") or ""
                self._tool_meta[idx] = (tid, name)
                self._tool_json_parts.setdefault(idx, [])
        elif et == "content_block_delta":
            idx = getattr(event, "index", 0)
            delta = getattr(event, "delta", None)
            if delta is None:
                return
            dt = getattr(delta, "type", None)
            if dt == "text_delta":
                self.text_parts.append(str(getattr(delta, "text", "") or ""))
            elif dt == "input_json_delta":
                self._tool_json_parts.setdefault(idx, []).append(
                    str(getattr(delta, "partial_json", "") or "")
                )
        elif et == "message_delta":
            d = getattr(event, "delta", None)
            if d is not None:
                sr = getattr(d, "stop_reason", None)
                if sr is not None:
                    self.stop_reason = sr
            usage = getattr(event, "usage", None)
            if usage is not None:
                it = getattr(usage, "input_tokens", None)
                ot = getattr(usage, "output_tokens", None)
                if it is not None:
                    self.input_tokens = it
                if ot is not None:
                    self.output_tokens = ot

    def build_response_attributes(self, capture_content: bool) -> dict[str, Any]:
        tool_calls: list[ToolCall] = []
        for idx in sorted(self._tool_meta.keys()):
            tid, name = self._tool_meta[idx]
            parts = self._tool_json_parts.get(idx, [])
            arg_str = "".join(parts) if parts else None
            tool_calls.append(
                ToolCall(
                    id=tid,
                    type="function",
                    function_name=name,
                    function_arguments=arg_str,
                )
            )
        content = "".join(self.text_parts) if self.text_parts else None
        choice = Choice(
            finish_reason=stop_reason_to_finish_reason(self.stop_reason),
            role="assistant",
            content=content,
            tool_calls=tool_calls or None,
        )
        return {
            **generate_response_attributes(
                model=self.response_model,
                finish_reasons=[choice.finish_reason] if choice.finish_reason else None,
                id=self.message_id,
                usage_input_tokens=self.input_tokens,
                usage_output_tokens=self.output_tokens,
            ),
            **generate_choice_attributes([choice], capture_content),
        }


class AnthropicStreamWrapper:
    def __init__(
        self,
        stream: Stream[Any],
        span: Span,
        capture_content: bool,
        span_attributes: dict[str, Any],
        instruments: Instruments,
        start_time: float,
    ) -> None:
        self.stream = stream
        self.span = span
        self.capture_content = capture_content
        self._span_attributes = span_attributes
        self._instruments = instruments
        self._start_time = start_time
        self._state = _AnthropicStreamAccumState()
        self._finished = False

    def _finalize(self, error_type: str | None = None) -> None:
        if self._finished:
            return
        self._finished = True
        if self.span.is_recording():
            self.span.set_attributes(
                self._state.build_response_attributes(self.capture_content)
            )
        self.span.end()
        duration = max((default_timer() - self._start_time), 0)
        result = None
        if (
            self._state.input_tokens is not None
            or self._state.output_tokens is not None
        ):
            result = SimpleNamespace(
                model=self._state.response_model,
                usage=SimpleNamespace(
                    input_tokens=self._state.input_tokens,
                    output_tokens=self._state.output_tokens,
                ),
            )
        _record_metrics(
            self._instruments,
            duration,
            result,
            self._span_attributes,
            error_type,
        )

    def __enter__(self) -> AnthropicStreamWrapper:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            if exc_type is not None and exc_val is not None:
                handle_span_exception(self.span, exc_val)
        finally:
            et = type(exc_val).__qualname__ if exc_val is not None else None
            self._finalize(et)

    def close(self) -> None:
        self.stream.close()
        self._finalize()

    def __iter__(self) -> AnthropicStreamWrapper:
        return self

    def __next__(self) -> Any:
        try:
            event = next(self.stream)
            self._state.process_event(event)
            return event
        except StopIteration:
            self._finalize()
            raise
        except Exception as error:
            handle_span_exception(self.span, error)
            self._finalize(type(error).__qualname__)
            raise


class AnthropicAsyncStreamWrapper:
    def __init__(
        self,
        stream: AsyncStream[Any],
        span: Span,
        capture_content: bool,
        span_attributes: dict[str, Any],
        instruments: Instruments,
        start_time: float,
    ) -> None:
        self.stream = stream
        self.span = span
        self.capture_content = capture_content
        self._span_attributes = span_attributes
        self._instruments = instruments
        self._start_time = start_time
        self._state = _AnthropicStreamAccumState()
        self._finished = False

    def _finalize(self, error_type: str | None = None) -> None:
        if self._finished:
            return
        self._finished = True
        if self.span.is_recording():
            self.span.set_attributes(
                self._state.build_response_attributes(self.capture_content)
            )
        self.span.end()
        duration = max((default_timer() - self._start_time), 0)
        result = None
        if (
            self._state.input_tokens is not None
            or self._state.output_tokens is not None
        ):
            result = SimpleNamespace(
                model=self._state.response_model,
                usage=SimpleNamespace(
                    input_tokens=self._state.input_tokens,
                    output_tokens=self._state.output_tokens,
                ),
            )
        _record_metrics(
            self._instruments,
            duration,
            result,
            self._span_attributes,
            error_type,
        )

    async def __aenter__(self) -> AnthropicAsyncStreamWrapper:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            if exc_type is not None and exc_val is not None:
                handle_span_exception(self.span, exc_val)
        finally:
            et = type(exc_val).__qualname__ if exc_val is not None else None
            self._finalize(et)

    async def close(self) -> None:
        await self.stream.close()
        self._finalize()

    async def aclose(self) -> None:
        await self.close()

    def __aiter__(self) -> AnthropicAsyncStreamWrapper:
        return self

    async def __anext__(self) -> Any:
        try:
            event = await self.stream.__anext__()
            self._state.process_event(event)
            return event
        except StopAsyncIteration:
            self._finalize()
            raise
        except Exception as error:
            handle_span_exception(self.span, error)
            self._finalize(type(error).__qualname__)
            raise
