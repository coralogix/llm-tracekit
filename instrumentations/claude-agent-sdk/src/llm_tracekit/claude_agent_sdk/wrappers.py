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

from collections.abc import AsyncIterator
from typing import Any

from opentelemetry.trace import Span, SpanKind, Tracer

from llm_tracekit.core import handle_span_exception
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
        capture_content: bool,
    ) -> None:
        self._stream = stream
        self._span = span
        self._capture_content = capture_content
        self._assistant_messages: list[Any] = []
        self._result_message: Any = None
        self._finalized = False

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
        finally:
            self._span.end()

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
        turn_prompt: str | None,
        system_prompt: str | None,
        model: str | None,
        options: Any = None,
        capture_content: bool = True,
    ) -> None:
        self._stream = stream
        self._tracer = tracer
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

    def __aiter__(self) -> ClientReceiveResponseWrapper:
        return self

    async def __anext__(self) -> Any:
        if not self._started:
            self._started = True
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
        finally:
            self._span.end()

    def _finalize_on_error(self, error: Exception) -> None:
        if self._finalized or self._span is None:
            return
        self._finalized = True
        handle_span_exception(self._span, error)  # sets status and ends span
