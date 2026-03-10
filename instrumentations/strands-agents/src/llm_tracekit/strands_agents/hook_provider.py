# Copyright Coralogix Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this package except in compliance with the License.
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

import json
import time
import threading
from typing import Any

from opentelemetry import context as otel_context
from opentelemetry import trace as trace_api
from opentelemetry.trace import Tracer, Span, SpanKind, StatusCode
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import (
    BeforeInvocationEvent,
    AfterInvocationEvent,
    BeforeModelCallEvent,
    AfterModelCallEvent,
    BeforeToolCallEvent,
    AfterToolCallEvent,
)

from llm_tracekit.core import is_content_enabled
from llm_tracekit.core._config import handle_span_exception
from llm_tracekit.core._metrics import Instruments
from llm_tracekit.core._span_builder import (
    Message,
    Choice,
    ToolCall,
    generate_base_attributes,
    generate_request_attributes,
    generate_response_attributes,
    generate_message_attributes,
    generate_choice_attributes,
)

_SYSTEM = "strands"


class _AgentTraceState:
    """Per-invocation trace state, keyed by thread."""

    def __init__(self):
        self.agent_span: Span | None = None
        self.agent_token: object | None = None
        self.cycle_span: Span | None = None
        self.cycle_token: object | None = None
        self.current_cycle_id: str | None = None
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0


class StrandsHookProvider(HookProvider):
    def __init__(
        self,
        tracer: Tracer,
        instruments: Instruments,
        capture_content: bool = False,
    ):
        self._tracer = tracer
        self._instruments = instruments
        self._capture_content = capture_content
        self.disabled = False
        self._states: dict[int, _AgentTraceState] = {}
        self._lock = threading.Lock()

    def _get_state(self) -> _AgentTraceState:
        tid = threading.get_ident()
        with self._lock:
            if tid not in self._states:
                self._states[tid] = _AgentTraceState()
            return self._states[tid]

    def _clear_state(self):
        tid = threading.get_ident()
        with self._lock:
            self._states.pop(tid, None)

    def register_hooks(self, registry: HookRegistry):
        registry.add_callback("before_invocation", self._before_invocation)
        registry.add_callback("after_invocation", self._after_invocation)
        registry.add_callback("before_model_call", self._before_model_call)
        registry.add_callback("after_model_call", self._after_model_call)
        registry.add_callback("before_tool_call", self._before_tool_call)
        registry.add_callback("after_tool_call", self._after_tool_call)

    # ── Agent span ──────────────────────────────────────────────────────

    def _before_invocation(self, event: BeforeInvocationEvent, **kwargs: Any):
        if self.disabled:
            return

        state = self._get_state()
        agent = kwargs.get("agent") or getattr(event, "agent", None)
        agent_name = getattr(agent, "name", None) or "unknown"
        model_id = None
        tools_list: list[str] = []

        if agent is not None:
            model = getattr(agent, "model", None)
            if model is not None:
                model_id = getattr(model, "model_id", None) or getattr(
                    model, "config", {}
                ).get("model_id")
            agent_tools = getattr(agent, "tool_registry", None)
            if agent_tools is not None:
                tool_names = getattr(agent_tools, "get_all_tools_config", None)
                if callable(tool_names):
                    try:
                        tools_list = [
                            t.get("name", "") for t in tool_names() if isinstance(t, dict)
                        ]
                    except Exception:
                        pass
                if not tools_list:
                    registry_dict = getattr(agent_tools, "registry", {})
                    if isinstance(registry_dict, dict):
                        tools_list = list(registry_dict.keys())

        span_name = f"invoke_agent {agent_name}"
        attributes: dict[str, Any] = {
            GenAIAttributes.GEN_AI_SYSTEM: _SYSTEM,
            GenAIAttributes.GEN_AI_OPERATION_NAME: "invoke_agent",
            GenAIAttributes.GEN_AI_AGENT_NAME: agent_name,
        }
        if model_id:
            attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL] = model_id
        if tools_list:
            attributes["gen_ai.agent.tools"] = json.dumps(tools_list)

        state.agent_span = self._tracer.start_span(
            name=span_name,
            kind=SpanKind.INTERNAL,
            attributes=attributes,
        )
        state.agent_token = otel_context.attach(
            trace_api.set_span_in_context(state.agent_span)
        )

    def _after_invocation(self, event: AfterInvocationEvent, **kwargs: Any):
        if self.disabled:
            return

        state = self._get_state()

        self._end_cycle_span(state)

        if state.agent_span is not None:
            if state.total_input_tokens > 0:
                state.agent_span.set_attribute(
                    GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS,
                    state.total_input_tokens,
                )
            if state.total_output_tokens > 0:
                state.agent_span.set_attribute(
                    GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS,
                    state.total_output_tokens,
                )

            result = getattr(event, "result", None)
            if result is None:
                exception = getattr(event, "exception", None)
                if exception is not None:
                    handle_span_exception(state.agent_span, exception)
                else:
                    state.agent_span.set_status(StatusCode.OK)
                    state.agent_span.end()
            else:
                state.agent_span.set_status(StatusCode.OK)
                state.agent_span.end()

        if state.agent_token is not None:
            otel_context.detach(state.agent_token)

        self._clear_state()

    # ── Cycle span ──────────────────────────────────────────────────────

    def _ensure_cycle_span(self, state: _AgentTraceState, cycle_id: str | None):
        if cycle_id is None or cycle_id == state.current_cycle_id:
            return

        self._end_cycle_span(state)

        ctx = trace_api.set_span_in_context(state.agent_span)
        span_name = f"cycle {cycle_id}"
        state.cycle_span = self._tracer.start_span(
            name=span_name,
            kind=SpanKind.INTERNAL,
            attributes={"strands.agent.cycle.id": cycle_id},
            context=ctx,
        )
        state.cycle_token = otel_context.attach(
            trace_api.set_span_in_context(state.cycle_span)
        )
        state.current_cycle_id = cycle_id

    def _end_cycle_span(self, state: _AgentTraceState):
        if state.cycle_span is not None:
            state.cycle_span.set_status(StatusCode.OK)
            state.cycle_span.end()
            state.cycle_span = None
        if state.cycle_token is not None:
            otel_context.detach(state.cycle_token)
            state.cycle_token = None
        state.current_cycle_id = None

    # ── Model span ──────────────────────────────────────────────────────

    def _before_model_call(self, event: BeforeModelCallEvent, **kwargs: Any):
        if self.disabled:
            return

        state = self._get_state()
        invocation_state = getattr(event, "invocation_state", None)

        cycle_id = None
        if invocation_state is not None:
            cycle_id = str(getattr(invocation_state, "cycle_id", None))

        self._ensure_cycle_span(state, cycle_id)

        model_id = None
        if invocation_state is not None:
            model_id = getattr(invocation_state, "model_id", None)

        span_name = f"chat {model_id or 'unknown'}"
        parent = state.cycle_span or state.agent_span
        ctx = trace_api.set_span_in_context(parent) if parent else None

        attributes = {
            **generate_base_attributes(_SYSTEM),
            **generate_request_attributes(model=model_id),
        }

        span = self._tracer.start_span(
            name=span_name,
            kind=SpanKind.CLIENT,
            attributes=attributes,
            context=ctx,
        )

        state._model_span = span
        state._model_span_token = otel_context.attach(
            trace_api.set_span_in_context(span)
        )
        state._model_start_time = time.time()

    def _after_model_call(self, event: AfterModelCallEvent, **kwargs: Any):
        if self.disabled:
            return

        state = self._get_state()
        span: Span | None = getattr(state, "_model_span", None)
        if span is None:
            return

        start_time = getattr(state, "_model_start_time", None)
        duration = (time.time() - start_time) if start_time else 0

        exception = getattr(event, "exception", None)
        if exception is not None:
            handle_span_exception(span, exception)
            token = getattr(state, "_model_span_token", None)
            if token is not None:
                otel_context.detach(token)
            state._model_span = None
            state._model_span_token = None
            return

        stop_response = getattr(event, "stop_response", None)

        input_tokens = 0
        output_tokens = 0
        finish_reason = None
        response_model = None
        cache_read = None
        cache_write = None

        if stop_response is not None:
            metrics = getattr(stop_response, "metrics", None) or {}
            if isinstance(metrics, dict):
                usage = metrics.get("usage", {})
                if isinstance(usage, dict):
                    input_tokens = usage.get("inputTokens", 0) or 0
                    output_tokens = usage.get("outputTokens", 0) or 0
                    cache_read = usage.get("cacheReadInputTokens")
                    cache_write = usage.get("cacheWriteInputTokens")

            finish_reason = getattr(stop_response, "stop_reason", None)
            response_model = getattr(stop_response, "model", None)

        state.total_input_tokens += input_tokens
        state.total_output_tokens += output_tokens

        finish_reasons = [finish_reason] if finish_reason else None
        response_attrs = generate_response_attributes(
            model=response_model,
            finish_reasons=finish_reasons,
            usage_input_tokens=input_tokens if input_tokens > 0 else None,
            usage_output_tokens=output_tokens if output_tokens > 0 else None,
        )
        for k, v in response_attrs.items():
            span.set_attribute(k, v)

        if cache_read is not None and cache_read > 0:
            span.set_attribute("gen_ai.usage.cache_read_input_tokens", cache_read)
        if cache_write is not None and cache_write > 0:
            span.set_attribute("gen_ai.usage.cache_write_input_tokens", cache_write)

        if self._capture_content or is_content_enabled():
            self._record_content_attributes(span, event, stop_response)

        self._instruments.operation_duration_histogram.record(
            duration,
            attributes={
                GenAIAttributes.GEN_AI_OPERATION_NAME: "chat",
                GenAIAttributes.GEN_AI_SYSTEM: _SYSTEM,
            },
        )
        if input_tokens > 0:
            self._instruments.token_usage_histogram.record(
                input_tokens,
                attributes={
                    GenAIAttributes.GEN_AI_OPERATION_NAME: "chat",
                    GenAIAttributes.GEN_AI_SYSTEM: _SYSTEM,
                    GenAIAttributes.GEN_AI_TOKEN_TYPE: "input",
                },
            )
        if output_tokens > 0:
            self._instruments.token_usage_histogram.record(
                output_tokens,
                attributes={
                    GenAIAttributes.GEN_AI_OPERATION_NAME: "chat",
                    GenAIAttributes.GEN_AI_SYSTEM: _SYSTEM,
                    GenAIAttributes.GEN_AI_TOKEN_TYPE: "output",
                },
            )

        span.set_status(StatusCode.OK)
        span.end()

        token = getattr(state, "_model_span_token", None)
        if token is not None:
            otel_context.detach(token)
        state._model_span = None
        state._model_span_token = None

    def _record_content_attributes(
        self, span: Span, event: AfterModelCallEvent, stop_response: Any
    ):
        invocation_state = getattr(event, "invocation_state", None)
        if invocation_state is None:
            return

        messages_raw = getattr(invocation_state, "messages", None)
        if messages_raw and isinstance(messages_raw, list):
            messages = self._convert_messages(messages_raw)
            msg_attrs = generate_message_attributes(messages, capture_content=True)
            for k, v in msg_attrs.items():
                span.set_attribute(k, v)

        if stop_response is not None:
            message = getattr(stop_response, "message", None)
            if message is not None:
                choices = self._convert_stop_response_to_choices(message, stop_response)
                choice_attrs = generate_choice_attributes(choices, capture_content=True)
                for k, v in choice_attrs.items():
                    span.set_attribute(k, v)

    def _convert_messages(self, messages_raw: list) -> list[Message]:
        messages: list[Message] = []
        for msg in messages_raw:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "user")
            content_parts = msg.get("content", [])
            text_content = None
            tool_calls_list: list[ToolCall] = []
            tool_call_id = None

            if isinstance(content_parts, str):
                text_content = content_parts
            elif isinstance(content_parts, list):
                texts = []
                for part in content_parts:
                    if isinstance(part, dict):
                        if "text" in part:
                            texts.append(part["text"])
                        elif "toolUse" in part:
                            tu = part["toolUse"]
                            tool_calls_list.append(
                                ToolCall(
                                    id=tu.get("toolUseId"),
                                    type="function",
                                    function_name=tu.get("name"),
                                    function_arguments=json.dumps(tu.get("input", {})),
                                )
                            )
                        elif "toolResult" in part:
                            tr = part["toolResult"]
                            tool_call_id = tr.get("toolUseId")
                            result_content = tr.get("content", [])
                            result_texts = []
                            for rc in result_content:
                                if isinstance(rc, dict) and "text" in rc:
                                    result_texts.append(rc["text"])
                            if result_texts:
                                text_content = "\n".join(result_texts)
                    elif isinstance(part, str):
                        texts.append(part)
                if texts and text_content is None:
                    text_content = "\n".join(texts)

            messages.append(
                Message(
                    role=role,
                    content=text_content,
                    tool_call_id=tool_call_id,
                    tool_calls=tool_calls_list if tool_calls_list else None,
                )
            )
        return messages

    def _convert_stop_response_to_choices(
        self, message: Any, stop_response: Any
    ) -> list[Choice]:
        content_parts = message.get("content", []) if isinstance(message, dict) else []
        text_content = None
        tool_calls_list: list[ToolCall] = []

        if isinstance(content_parts, str):
            text_content = content_parts
        elif isinstance(content_parts, list):
            texts = []
            for part in content_parts:
                if isinstance(part, dict):
                    if "text" in part:
                        texts.append(part["text"])
                    elif "toolUse" in part:
                        tu = part["toolUse"]
                        tool_calls_list.append(
                            ToolCall(
                                id=tu.get("toolUseId"),
                                type="function",
                                function_name=tu.get("name"),
                                function_arguments=json.dumps(tu.get("input", {})),
                            )
                        )
            if texts:
                text_content = "\n".join(texts)

        finish_reason = getattr(stop_response, "stop_reason", None)
        role = message.get("role", "assistant") if isinstance(message, dict) else "assistant"

        return [
            Choice(
                finish_reason=finish_reason,
                role=role,
                content=text_content,
                tool_calls=tool_calls_list if tool_calls_list else None,
            )
        ]

    # ── Tool span ───────────────────────────────────────────────────────

    def _before_tool_call(self, event: BeforeToolCallEvent, **kwargs: Any):
        if self.disabled:
            return

        state = self._get_state()

        tool_use = getattr(event, "tool_use", None) or {}
        tool_name = tool_use.get("name", "unknown") if isinstance(tool_use, dict) else "unknown"
        tool_use_id = tool_use.get("toolUseId") if isinstance(tool_use, dict) else None

        selected_tool = getattr(event, "selected_tool", None)
        tool_type = "function"
        if selected_tool is not None:
            is_mcp = getattr(selected_tool, "is_mcp", False)
            if is_mcp:
                tool_type = "mcp"

        span_name = f"execute_tool {tool_name}"
        parent = state.cycle_span or state.agent_span
        ctx = trace_api.set_span_in_context(parent) if parent else None

        attributes: dict[str, Any] = {
            GenAIAttributes.GEN_AI_SYSTEM: _SYSTEM,
            GenAIAttributes.GEN_AI_OPERATION_NAME: "execute_tool",
            "name": tool_name,
            "type": tool_type,
        }
        if tool_use_id:
            attributes["gen_ai.tool.call.id"] = tool_use_id

        span = self._tracer.start_span(
            name=span_name,
            kind=SpanKind.INTERNAL,
            attributes=attributes,
            context=ctx,
        )

        state._tool_span = span
        state._tool_span_token = otel_context.attach(
            trace_api.set_span_in_context(span)
        )
        state._tool_use = tool_use

    def _after_tool_call(self, event: AfterToolCallEvent, **kwargs: Any):
        if self.disabled:
            return

        state = self._get_state()
        span: Span | None = getattr(state, "_tool_span", None)
        if span is None:
            return

        exception = getattr(event, "exception", None)
        if exception is not None:
            handle_span_exception(span, exception)
            token = getattr(state, "_tool_span_token", None)
            if token is not None:
                otel_context.detach(token)
            state._tool_span = None
            state._tool_span_token = None
            return

        result = getattr(event, "result", None)
        tool_status = "success"
        if isinstance(result, dict):
            tool_status = result.get("status", "success")
        span.set_attribute("gen_ai.tool.status", tool_status)

        if self._capture_content or is_content_enabled():
            tool_use = getattr(state, "_tool_use", None)
            if isinstance(tool_use, dict):
                tool_input = tool_use.get("input")
                if tool_input is not None:
                    span.set_attribute("input", json.dumps(tool_input) if not isinstance(tool_input, str) else tool_input)
            if isinstance(result, dict):
                result_content = result.get("content", [])
                if result_content:
                    span.set_attribute("output", json.dumps(result_content) if not isinstance(result_content, str) else result_content)

        span.set_status(StatusCode.OK)
        span.end()

        token = getattr(state, "_tool_span_token", None)
        if token is not None:
            otel_context.detach(token)
        state._tool_span = None
        state._tool_span_token = None
        state._tool_use = None
