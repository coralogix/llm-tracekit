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

from dataclasses import dataclass
from time import perf_counter_ns
from typing import Any, AsyncIterator, Iterator, Optional

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.trace import SpanKind, Tracer

from llm_tracekit.gemini.state import GeminiOperationState, GeminiSpanContext
from llm_tracekit.gemini.utils import (
    build_request_details,
    build_response_details,
)
from llm_tracekit.instrumentation_utils import handle_span_exception
from llm_tracekit.instruments import Instruments


_GEMINI_SYSTEM_VALUE = getattr(
    GenAIAttributes.GenAiSystemValues,
    "GOOGLE_GENAI",
    "google_genai",
)


@dataclass
class _WrapperConfig:
    tracer: Tracer
    instruments: Instruments
    capture_content: bool


def generate_content_wrapper(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    config = _WrapperConfig(tracer=tracer, instruments=instruments, capture_content=capture_content)

    def traced_method(wrapped, instance, args, kwargs):
        model = _get_argument(args, kwargs, name="model", position=0)
        contents = _get_argument(args, kwargs, name="contents", position=1)
        system_instruction = _get_argument(args, kwargs, name="system_instruction")
        config_payload = _get_argument(args, kwargs, name="config", position=2)

        request_details = build_request_details(
            model=model,
            contents=contents,
            system_instruction=system_instruction,
            config=config_payload,
            capture_content=config.capture_content,
        )

        with config.tracer.start_as_current_span(
            name=request_details.span_name,
            kind=SpanKind.CLIENT,
            attributes=request_details.span_attributes,
            end_on_exit=False,
        ) as span:
            operation_state = _prepare_operation_state(span, request_details, config.capture_content)

            try:
                result = wrapped(*args, **kwargs)
                operation_state.response_details = build_response_details(
                    response=result,
                    capture_content=config.capture_content,
                )
                operation_state.finish_reasons = operation_state.response_details.finish_reasons

                if span.is_recording():
                    span.set_attributes(operation_state.response_details.span_attributes)

                span.end()
                operation_state.mark_span_finished()
                return result
            except Exception as error:
                _handle_exception(operation_state, error)
                raise
            finally:
                _record_metrics(operation_state, config.instruments)

    return traced_method


def generate_content_stream_wrapper(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    config = _WrapperConfig(tracer=tracer, instruments=instruments, capture_content=capture_content)

    def traced_method(wrapped, instance, args, kwargs):
        model = _get_argument(args, kwargs, name="model", position=0)
        contents = _get_argument(args, kwargs, name="contents", position=1)
        system_instruction = _get_argument(args, kwargs, name="system_instruction")
        config_payload = _get_argument(args, kwargs, name="config", position=2)

        request_details = build_request_details(
            model=model,
            contents=contents,
            system_instruction=system_instruction,
            config=config_payload,
            capture_content=config.capture_content,
        )

        span = config.tracer.start_span(
            name=request_details.span_name,
            kind=SpanKind.CLIENT,
            attributes=request_details.span_attributes,
        )
        operation_state = _prepare_operation_state(span, request_details, config.capture_content)

        try:
            stream = wrapped(*args, **kwargs)
        except Exception as error:
            _handle_exception(operation_state, error)
            raise

        return GeminiStreamWrapper(
            stream=stream,
            operation_state=operation_state,
            instruments=config.instruments,
        )

    return traced_method


def async_generate_content_wrapper(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    config = _WrapperConfig(tracer=tracer, instruments=instruments, capture_content=capture_content)

    async def traced_method(wrapped, instance, args, kwargs):
        model = _get_argument(args, kwargs, name="model", position=0)
        contents = _get_argument(args, kwargs, name="contents", position=1)
        system_instruction = _get_argument(args, kwargs, name="system_instruction")
        config_payload = _get_argument(args, kwargs, name="config", position=2)

        request_details = build_request_details(
            model=model,
            contents=contents,
            system_instruction=system_instruction,
            config=config_payload,
            capture_content=config.capture_content,
        )

        span = config.tracer.start_span(
            name=request_details.span_name,
            kind=SpanKind.CLIENT,
            attributes=request_details.span_attributes,
        )
        operation_state = _prepare_operation_state(span, request_details, config.capture_content)

        try:
            result = await wrapped(*args, **kwargs)
            operation_state.response_details = build_response_details(
                response=result,
                capture_content=config.capture_content,
            )
            operation_state.finish_reasons = operation_state.response_details.finish_reasons

            if span.is_recording():
                span.set_attributes(operation_state.response_details.span_attributes)

            span.end()
            operation_state.mark_span_finished()
            return result
        except Exception as error:
            _handle_exception(operation_state, error)
            raise
        finally:
            _record_metrics(operation_state, config.instruments)

    return traced_method


def async_generate_content_stream_wrapper(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    config = _WrapperConfig(tracer=tracer, instruments=instruments, capture_content=capture_content)

    async def traced_method(wrapped, instance, args, kwargs):
        model = _get_argument(args, kwargs, name="model", position=0)
        contents = _get_argument(args, kwargs, name="contents", position=1)
        system_instruction = _get_argument(args, kwargs, name="system_instruction")
        config_payload = _get_argument(args, kwargs, name="config", position=2)

        request_details = build_request_details(
            model=model,
            contents=contents,
            system_instruction=system_instruction,
            config=config_payload,
            capture_content=config.capture_content,
        )

        span = config.tracer.start_span(
            name=request_details.span_name,
            kind=SpanKind.CLIENT,
            attributes=request_details.span_attributes,
        )
        operation_state = _prepare_operation_state(span, request_details, config.capture_content)

        try:
            stream = await wrapped(*args, **kwargs)
        except Exception as error:
            _handle_exception(operation_state, error)
            raise

        return GeminiAsyncStreamWrapper(
            stream=stream,
            operation_state=operation_state,
            instruments=config.instruments,
        )

    return traced_method


class GeminiStreamWrapper(Iterator[Any]):
    def __init__(
        self,
        stream: Iterator[Any],
        operation_state: GeminiOperationState,
        instruments: Instruments,
    ) -> None:
        self._stream = stream
        self._state = operation_state
        self._instruments = instruments
        self._finalized = False

    def __iter__(self) -> "GeminiStreamWrapper":
        return self

    def __next__(self):
        try:
            chunk = next(self._stream)
        except StopIteration:
            self._finalize()
            raise
        except Exception as error:
            self._handle_stream_exception(error)
            raise

        self._state.ensure_stream_state().ingest_chunk(chunk)
        return chunk

    def close(self) -> None:
        if hasattr(self._stream, "close"):
            self._stream.close()
        self._finalize()

    def __enter__(self) -> "GeminiStreamWrapper":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None and exc_val is not None:
                self._handle_stream_exception(exc_val)
        finally:
            self._finalize()
        return False

    def _handle_stream_exception(self, error: Exception) -> None:
        self._state.error_type = type(error).__qualname__
        handle_span_exception(self._state.span_context.span, error)
        self._state.mark_span_finished()
        self._finalized = True
        _record_metrics(self._state, self._instruments)

    def _finalize(self) -> None:
        if self._finalized:
            return

        self._finalized = True
        stream_state = self._state.stream_state
        if stream_state is not None and self._state.response_details is None:
            self._state.response_details = stream_state.finalize()
            self._state.finish_reasons = self._state.response_details.finish_reasons

        span = self._state.span_context.span
        if not self._state.span_finished:
            if span.is_recording() and self._state.response_details is not None:
                span.set_attributes(self._state.response_details.span_attributes)
            span.end()
            self._state.mark_span_finished()

        _record_metrics(self._state, self._instruments)

    def __del__(self) -> None:
        self._finalize()


class GeminiAsyncStreamWrapper(AsyncIterator[Any]):
    def __init__(
        self,
        stream: AsyncIterator[Any],
        operation_state: GeminiOperationState,
        instruments: Instruments,
    ) -> None:
        self._stream = stream
        self._state = operation_state
        self._instruments = instruments
        self._finalized = False

    def __aiter__(self) -> "GeminiAsyncStreamWrapper":
        return self

    async def __anext__(self):
        try:
            chunk = await self._stream.__anext__()
        except StopAsyncIteration:
            await self._finalize()
            raise
        except Exception as error:
            self._handle_stream_exception(error)
            raise

        self._state.ensure_stream_state().ingest_chunk(chunk)
        return chunk

    async def aclose(self) -> None:
        close_method = getattr(self._stream, "aclose", None)
        if callable(close_method):
            await close_method()
        await self._finalize()

    async def __aenter__(self) -> "GeminiAsyncStreamWrapper":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None and exc_val is not None:
                self._handle_stream_exception(exc_val)
        finally:
            await self._finalize()
        return False

    def _handle_stream_exception(self, error: Exception) -> None:
        self._state.error_type = type(error).__qualname__
        handle_span_exception(self._state.span_context.span, error)
        self._state.mark_span_finished()
        self._finalized = True
        _record_metrics(self._state, self._instruments)

    async def _finalize(self) -> None:
        if self._finalized:
            return

        self._finalized = True
        stream_state = self._state.stream_state
        if stream_state is not None and self._state.response_details is None:
            self._state.response_details = stream_state.finalize()
            self._state.finish_reasons = self._state.response_details.finish_reasons

        span = self._state.span_context.span
        if not self._state.span_finished:
            if span.is_recording() and self._state.response_details is not None:
                span.set_attributes(self._state.response_details.span_attributes)
            span.end()
            self._state.mark_span_finished()

        _record_metrics(self._state, self._instruments)

    def __del__(self) -> None:
        _record_metrics(self._state, self._instruments)


def _prepare_operation_state(
    span,
    request_details,
    capture_content: bool,
) -> GeminiOperationState:
    span_context = GeminiSpanContext(
        span=span,
        capture_content=capture_content,
        start_time_ns=perf_counter_ns(),
        request_attributes=request_details.span_attributes,
    )
    state = GeminiOperationState(span_context=span_context)
    state.finish_reasons = []
    return state


def _handle_exception(operation_state: GeminiOperationState, error: Exception) -> None:
    operation_state.error_type = type(error).__qualname__
    handle_span_exception(operation_state.span_context.span, error)
    operation_state.mark_span_finished()


def _record_metrics(operation_state: GeminiOperationState, instruments: Instruments) -> None:
    if operation_state.metrics_recorded:
        return

    if instruments is None:
        return

    duration_ns = perf_counter_ns() - operation_state.span_context.start_time_ns
    duration_s = max(duration_ns / 1_000_000_000, 0.0)

    request_attributes = operation_state.span_context.request_attributes
    common_attributes = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: GenAIAttributes.GenAiOperationNameValues.CHAT.value,
        GenAIAttributes.GEN_AI_SYSTEM: _GEMINI_SYSTEM_VALUE,
    }

    request_model = request_attributes.get(GenAIAttributes.GEN_AI_REQUEST_MODEL)
    if request_model is not None:
        common_attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL] = request_model

    response_details = operation_state.response_details
    if response_details is not None and response_details.model is not None:
        common_attributes[GenAIAttributes.GEN_AI_RESPONSE_MODEL] = response_details.model

    if operation_state.error_type is not None:
        common_attributes["error.type"] = operation_state.error_type

    instruments.operation_duration_histogram.record(
        duration_s,
        attributes=common_attributes,
    )

    if response_details is not None:
        usage = response_details.usage
        if usage.prompt_tokens is not None:
            input_attributes = dict(common_attributes)
            input_attributes[
                GenAIAttributes.GEN_AI_TOKEN_TYPE
            ] = GenAIAttributes.GenAiTokenTypeValues.INPUT.value
            instruments.token_usage_histogram.record(
                usage.prompt_tokens,
                attributes=input_attributes,
            )

        if usage.candidates_tokens is not None:
            completion_attributes = dict(common_attributes)
            completion_attributes[
                GenAIAttributes.GEN_AI_TOKEN_TYPE
            ] = GenAIAttributes.GenAiTokenTypeValues.COMPLETION.value
            instruments.token_usage_histogram.record(
                usage.candidates_tokens,
                attributes=completion_attributes,
            )

    operation_state.mark_metrics_recorded()


def _get_argument(args, kwargs, name: str, position: Optional[int] = None):
    if name in kwargs:
        return kwargs[name]
    if position is not None and len(args) > position:
        return args[position]
    return None


__all__ = [
    "generate_content_wrapper",
    "generate_content_stream_wrapper",
    "async_generate_content_wrapper",
    "async_generate_content_stream_wrapper",
]
