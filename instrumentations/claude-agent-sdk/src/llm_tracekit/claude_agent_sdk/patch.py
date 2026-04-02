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

"""Patches for Claude Agent SDK query() and ClaudeSDKClient."""

from __future__ import annotations

from functools import wraps
from typing import Any

from opentelemetry.trace import SpanKind, Tracer

from llm_tracekit.claude_agent_sdk.span_attrs import (
    _extract_system_prompt,
    build_prompt_attributes_for_turn,
    build_request_attributes_from_options,
    build_tools_attributes_from_options,
)
from llm_tracekit.claude_agent_sdk.wrappers import (
    ClientReceiveResponseWrapper,
    QueryStreamWrapper,
)


def create_wrapped_query(
    original_query: Any,
    tracer: Tracer,
    capture_content: bool,
) -> Any:
    """Return a wrapped query() that starts a span and wraps the returned stream."""

    @wraps(original_query)
    def wrapped_query(
        *,
        prompt: str | Any = None,
        options: Any = None,
        transport: Any = None,
    ) -> Any:
        model = getattr(options, "model", None) if options else None
        span = tracer.start_span(
            f"chat {model or 'claude'}",
            kind=SpanKind.CLIENT,
        )
        if span.is_recording():
            req = build_request_attributes_from_options(options)
            span.set_attributes(req)
            tools = build_tools_attributes_from_options(options)
            span.set_attributes(tools)
            system_prompt = _extract_system_prompt(options)
            user_prompt = prompt if isinstance(prompt, str) else None
            prompt_attrs = build_prompt_attributes_for_turn(
                user_prompt, system_prompt, capture_content
            )
            span.set_attributes(prompt_attrs)
        stream = original_query(prompt=prompt, options=options, transport=transport)
        return QueryStreamWrapper(stream, span, capture_content=capture_content)

    return wrapped_query


def create_wrapped_client_query(original_query: Any) -> Any:
    """Wrap ClaudeSDKClient.query to store current turn prompt on instance."""

    @wraps(original_query)
    async def wrapped_query(
        self: Any,
        prompt: str | Any = None,
        session_id: str = "default",
    ) -> None:
        self._llm_tracekit_turn_prompt = prompt if isinstance(prompt, str) else None
        await original_query(self, prompt=prompt, session_id=session_id)

    return wrapped_query


def create_wrapped_receive_response(
    original_receive_response: Any,
    tracer: Tracer,
    capture_content: bool,
) -> Any:
    """Wrap ClaudeSDKClient.receive_response to run inside a span per turn."""

    @wraps(original_receive_response)
    def wrapped_receive_response(self: Any) -> Any:
        stream = original_receive_response(self)
        turn_prompt = getattr(self, "_llm_tracekit_turn_prompt", None)
        try:
            delattr(self, "_llm_tracekit_turn_prompt")
        except AttributeError:
            pass
        options = getattr(self, "options", None)
        system_prompt = _extract_system_prompt(options)
        model = getattr(options, "model", None)
        return ClientReceiveResponseWrapper(
            stream,
            tracer,
            turn_prompt=turn_prompt,
            system_prompt=system_prompt,
            model=model,
            options=options,
            capture_content=capture_content,
        )

    return wrapped_receive_response
