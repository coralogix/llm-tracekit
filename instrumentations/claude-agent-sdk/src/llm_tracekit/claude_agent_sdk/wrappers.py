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

"""Async iterator wrappers for Claude Agent SDK streams."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.trace import Span, SpanKind, Tracer

from llm_tracekit.core import handle_span_exception
from llm_tracekit.core._metrics import Instruments
from llm_tracekit.claude_agent_sdk.span_attrs import (
    build_completion_attributes,
    build_library_specific_attributes,
    build_prompt_attributes_for_turn,
    build_request_attributes_from_options,
    build_response_attributes,
    build_tools_attributes_from_options,
)


def _is_assistant_message(msg: Any) -> bool:
    return type(msg).__name__ == "AssistantMessage"


def _is_result_message(msg: Any) -> bool:
    return type(msg).__name__ == "ResultMessage"


class QueryStreamWrapper(AsyncIterator[Any]):
    """Wraps the async iterator from query() to record one span per call."""

    def __init__(
        self,
        stream: AsyncIterator[Any],
        span: Span,
        *,
        instruments: Instruments,
        capture_content: bool,
    ) -> None:
        self._stream = stream
        self._span = span
        self._instruments = instruments
        self._capture_content = capture_content
        self._assistant_messages: list[Any] = []
        self._result_message: Any = None
        self._finalized = False
        self._start_time = time.perf_counter()

    def __aiter__(self) -> QueryStreamWrapper:
        return self

    async def __anext__(self) -> Any:
        try:
            msg = await self._stream.__anext__()
        except StopAsyncIteration:
            self._finalize()
            raise
        except Exception as e:
            self._finalize_on_error(e)
            raise

        if _is_assistant_message(msg):
            self._assistant_messages.append(msg)
        elif _is_result_message(msg):
            self._result_message = msg

        return msg

    def _finalize(self) -> None:
        if self._finalized:
            return
        self._finalized = True
        duration = time.perf_counter() - self._start_time
        try:
            if self._span.is_recording():
                comp = build_completion_attributes(
                    self._assistant_messages,
                    self._result_message,
                    self._capture_content,
                )
                self._span.set_attributes(comp)
                resp = build_response_attributes(self._result_message)
                self._span.set_attributes(resp)
                lib_attrs = build_library_specific_attributes(self._result_message)
                self._span.set_attributes(lib_attrs)
            self._record_metrics(duration)
        finally:
            self._span.end()

    def _record_metrics(self, duration: float) -> None:
        common_attrs = {
            GenAIAttributes.GEN_AI_OPERATION_NAME: GenAIAttributes.GenAiOperationNameValues.CHAT.value,
            GenAIAttributes.GEN_AI_SYSTEM: "claude.agent_sdk",
        }
        self._instruments.operation_duration_histogram.record(duration, attributes=common_attrs)

        if self._result_message is not None:
            usage = getattr(self._result_message, "usage", None) or {}
            if isinstance(usage, dict):
                input_tokens = usage.get("input_tokens")
                output_tokens = usage.get("output_tokens")
            else:
                input_tokens = getattr(usage, "input_tokens", None)
                output_tokens = getattr(usage, "output_tokens", None)

            if input_tokens is not None:
                self._instruments.token_usage_histogram.record(
                    input_tokens,
                    attributes={
                        **common_attrs,
                        GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.INPUT.value,
                    },
                )
            if output_tokens is not None:
                self._instruments.token_usage_histogram.record(
                    output_tokens,
                    attributes={
                        **common_attrs,
                        GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.COMPLETION.value,
                    },
                )

    def _finalize_on_error(self, error: Exception) -> None:
        if self._finalized:
            return
        self._finalized = True
        handle_span_exception(self._span, error)  # sets status and ends span

    async def aclose(self) -> None:
        aclose = getattr(self._stream, "aclose", None)
        if callable(aclose):
            await aclose()
        self._finalize()


class ClientReceiveResponseWrapper(AsyncIterator[Any]):
    """Wraps receive_response() so one span is created per turn. Stateless: prompt from current request only."""

    def __init__(
        self,
        stream: AsyncIterator[Any],
        tracer: Tracer,
        *,
        instruments: Instruments,
        turn_prompt: str | None,
        system_prompt: str | None,
        model: str | None,
        options: Any = None,
        capture_content: bool = True,
    ) -> None:
        self._stream = stream
        self._tracer = tracer
        self._instruments = instruments
        self._turn_prompt = turn_prompt
        self._system_prompt = system_prompt
        self._model = model
        self._options = options
        self._capture_content = capture_content
        self._span: Span | None = None
        self._assistant_messages: list[Any] = []
        self._result_message: Any = None
        self._finalized = False
        self._started = False
        self._start_time: float | None = None

    def __aiter__(self) -> ClientReceiveResponseWrapper:
        return self

    async def __anext__(self) -> Any:
        if not self._started:
            self._started = True
            self._start_time = time.perf_counter()
            self._span = self._tracer.start_span(
                f"chat {self._model or 'claude'}",
                kind=SpanKind.CLIENT,
            )
            if self._span.is_recording():
                base = build_request_attributes_from_options(self._options)
                self._span.set_attributes(base)
                tools_attrs = build_tools_attributes_from_options(self._options)
                self._span.set_attributes(tools_attrs)
                prompt_attrs = build_prompt_attributes_for_turn(
                    self._turn_prompt,
                    self._system_prompt,
                    self._capture_content,
                )
                self._span.set_attributes(prompt_attrs)

        try:
            msg = await self._stream.__anext__()
        except StopAsyncIteration:
            self._finalize()
            raise
        except Exception as e:
            self._finalize_on_error(e)
            raise

        if _is_assistant_message(msg):
            self._assistant_messages.append(msg)
        elif _is_result_message(msg):
            self._result_message = msg

        return msg

    def _finalize(self) -> None:
        if self._finalized or self._span is None:
            return
        self._finalized = True
        duration = time.perf_counter() - self._start_time if self._start_time else 0.0
        try:
            if self._span.is_recording():
                comp = build_completion_attributes(
                    self._assistant_messages,
                    self._result_message,
                    self._capture_content,
                )
                self._span.set_attributes(comp)
                resp = build_response_attributes(self._result_message)
                self._span.set_attributes(resp)
                lib_attrs = build_library_specific_attributes(self._result_message)
                self._span.set_attributes(lib_attrs)
            self._record_metrics(duration)
        finally:
            self._span.end()

    def _record_metrics(self, duration: float) -> None:
        common_attrs = {
            GenAIAttributes.GEN_AI_OPERATION_NAME: GenAIAttributes.GenAiOperationNameValues.CHAT.value,
            GenAIAttributes.GEN_AI_SYSTEM: "claude.agent_sdk",
        }
        if self._model:
            common_attrs[GenAIAttributes.GEN_AI_REQUEST_MODEL] = self._model

        self._instruments.operation_duration_histogram.record(duration, attributes=common_attrs)

        if self._result_message is not None:
            usage = getattr(self._result_message, "usage", None) or {}
            if isinstance(usage, dict):
                input_tokens = usage.get("input_tokens")
                output_tokens = usage.get("output_tokens")
            else:
                input_tokens = getattr(usage, "input_tokens", None)
                output_tokens = getattr(usage, "output_tokens", None)

            if input_tokens is not None:
                self._instruments.token_usage_histogram.record(
                    input_tokens,
                    attributes={
                        **common_attrs,
                        GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.INPUT.value,
                    },
                )
            if output_tokens is not None:
                self._instruments.token_usage_histogram.record(
                    output_tokens,
                    attributes={
                        **common_attrs,
                        GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.COMPLETION.value,
                    },
                )

    def _finalize_on_error(self, error: Exception) -> None:
        if self._finalized or self._span is None:
            return
        self._finalized = True
        handle_span_exception(self._span, error)  # sets status and ends span
