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

"""LangGraph callback handler emitting OTEL spans per node."""

from __future__ import annotations

import json
from collections.abc import Mapping
from timeit import default_timer
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler  # type: ignore
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.trace import Span, Status, StatusCode, Tracer

import llm_tracekit.core._extended_gen_ai_attributes as ExtendedGenAIAttributes
from llm_tracekit.core import handle_span_exception
from llm_tracekit.core._metrics import Instruments
from llm_tracekit.langgraph.span_manager import LangGraphSpanManager
from llm_tracekit.langgraph.utils import (
    LangGraphSpanAttributes,
    build_node_span_name,
    extract_node_attributes,
)


class LangGraphCallbackHandler(BaseCallbackHandler):  # type: ignore[misc]
    """LangChain callback handler that creates OpenTelemetry spans for LangGraph node runs.

    Only creates spans when chain metadata contains \"langgraph_node\". Use with
    LangGraphInstrumentor for automatic injection, or add this handler to your
    run's callback list when invoking a compiled graph.
    """

    def __init__(
        self,
        tracer: Tracer,
        capture_content: bool = False,
        instruments: Instruments | None = None,
    ) -> None:  # type: ignore[override]
        super().__init__()  # type: ignore
        self._span_manager = LangGraphSpanManager(tracer)
        self._capture_content = capture_content
        self._instruments = instruments

    def on_chain_start(  # type: ignore[override]
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        node_info = extract_node_attributes(metadata, tags)
        if node_info is None:
            return None

        node_name, attributes = node_info
        span_name = build_node_span_name(node_name)
        tool_definitions = _find_tool_definitions(serialized, metadata, inputs, kwargs)
        tool_attributes = _generate_available_tools_attributes(tool_definitions)
        if tool_attributes:
            attributes.update(tool_attributes)

        self._span_manager.create_node_span(
            run_id=run_id,
            parent_run_id=parent_run_id,
            span_name=span_name,
            attributes=attributes,
            node_name=node_name,
        )
        if self._capture_content:
            state = self._span_manager.get_state(run_id)
            if state is not None:
                _set_prompt_attributes_from_inputs(state.span, inputs)
        return None

    def on_chain_end(  # type: ignore[override]
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> Any:
        if self._capture_content:
            state = self._span_manager.get_state(run_id)
            if state is not None:
                _set_completion_attributes_from_outputs(state.span, outputs)
        self._finish_span(
            run_id, status=LangGraphSpanAttributes.STATUS, value="success"
        )
        return None

    def on_chain_error(  # type: ignore[override]
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> Any:
        state = self._span_manager.pop_state(run_id)
        if state is None:
            return None

        duration = max(default_timer() - state.start_time, 0.0)
        if self._instruments is not None:
            attrs: dict[str, Any] = {
                GenAIAttributes.GEN_AI_OPERATION_NAME: "langgraph.node",
            }
            if state.node_name:
                attrs[LangGraphSpanAttributes.NODE] = state.node_name
            self._instruments.operation_duration_histogram.record(
                duration, attributes=attrs
            )

        state.span.set_attribute(LangGraphSpanAttributes.STATUS, "error")
        handle_span_exception(state.span, error)
        return None

    def _finish_span(self, run_id: UUID, status: str, value: str) -> None:
        state = self._span_manager.pop_state(run_id)
        if state is None:
            return

        duration = max(default_timer() - state.start_time, 0.0)
        if self._instruments is not None:
            attrs: dict[str, Any] = {
                GenAIAttributes.GEN_AI_OPERATION_NAME: "langgraph.node",
            }
            if state.node_name:
                attrs[LangGraphSpanAttributes.NODE] = state.node_name
            self._instruments.operation_duration_histogram.record(
                duration, attributes=attrs
            )

        state.span.set_status(Status(StatusCode.OK))
        state.span.set_attribute(status, value)
        state.span.end()


def _normalize_message(msg: Any) -> tuple[str | None, str | None]:
    """Extract role and content from a message (dict or object with content)."""
    if isinstance(msg, Mapping):
        role = msg.get("role") if isinstance(msg.get("role"), str) else None
        content = msg.get("content")
        if content is not None and not isinstance(content, str):
            content = json.dumps(content) if content else None
        return role, content
    role = getattr(msg, "type", None) or getattr(msg, "role", None)
    content = getattr(msg, "content", None)
    if isinstance(content, str):
        pass
    elif content is not None:
        try:
            content = json.dumps(content)
        except (TypeError, ValueError):
            content = str(content)
    return role, content


def _messages_from_state(state: dict[str, Any]) -> list[tuple[str | None, str | None]]:
    """Return list of (role, content) from state's messages key."""
    messages = state.get("messages")
    if not isinstance(messages, list):
        return []
    return [_normalize_message(m) for m in messages]


def _set_prompt_attributes_from_inputs(span: Span, inputs: dict[str, Any]) -> None:
    """Set gen_ai.prompt.* attributes from node inputs (e.g. state messages)."""
    for idx, (role, content) in enumerate(_messages_from_state(inputs)):
        if role is not None:
            span.set_attribute(
                ExtendedGenAIAttributes.GEN_AI_PROMPT_ROLE.format(prompt_index=idx),
                role,
            )
        if content is not None:
            span.set_attribute(
                ExtendedGenAIAttributes.GEN_AI_PROMPT_CONTENT.format(prompt_index=idx),
                content,
            )


def _set_completion_attributes_from_outputs(
    span: Span, outputs: dict[str, Any]
) -> None:
    """Set gen_ai.completion.* attributes from node outputs (e.g. new messages)."""
    for idx, (role, content) in enumerate(_messages_from_state(outputs)):
        if role is not None:
            span.set_attribute(
                ExtendedGenAIAttributes.GEN_AI_COMPLETION_ROLE.format(
                    completion_index=idx
                ),
                role,
            )
        if content is not None:
            span.set_attribute(
                ExtendedGenAIAttributes.GEN_AI_COMPLETION_CONTENT.format(
                    completion_index=idx
                ),
                content,
            )


_TOOL_KEYS = (
    "tools",
    "available_tools",
    "agent_tools",
    "function_tools",
    "tool_specs",
    "functions",
)


def _find_tool_definitions(*payloads: Any) -> Any:
    for payload in payloads:
        if payload is None:
            continue
        result = _detect_tool_list(payload, set())
        if result:
            return result
    return None


def _detect_tool_list(obj: Any, visited: set[int]) -> Any:
    obj_id = id(obj)
    if obj_id in visited:
        return None
    visited.add(obj_id)

    if isinstance(obj, list):
        return obj if _is_tool_list(obj) else _search_list(obj, visited)
    if isinstance(obj, Mapping):
        for key in _TOOL_KEYS:
            value = obj.get(key)
            if isinstance(value, list):
                return value
        for value in obj.values():
            found = _detect_tool_list(value, visited)
            if found:
                return found
    return None


def _search_list(items: list[Any], visited: set[int]) -> Any:
    for item in items:
        found = _detect_tool_list(item, visited)
        if found:
            return found
    return None


def _is_tool_list(value: list[Any]) -> bool:
    if not value:
        return False
    first = value[0]
    return isinstance(first, Mapping)


def _generate_available_tools_attributes(tool_definitions: Any) -> dict[str, Any]:
    if not isinstance(tool_definitions, list):
        return {}

    attributes: dict[str, Any] = {}
    for tool_index, tool in enumerate(tool_definitions):
        if not isinstance(tool, Mapping):
            continue

        tool_type = tool.get("type") or "function"
        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_TYPE.format(
                tool_index=tool_index
            )
        ] = tool_type

        function = tool.get("function")
        if isinstance(function, Mapping):
            name = function.get("name")
            description = function.get("description")
            parameters = function.get("parameters")
        else:
            name = tool.get("name")
            description = tool.get("description")
            parameters = (
                tool.get("parameters")
                or tool.get("input_schema")
                or tool.get("inputSchema")
            )
            if parameters is None and isinstance(tool.get("definition"), Mapping):
                parameters = tool["definition"].get("parameters")

        if name is not None:
            attributes[
                ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_NAME.format(
                    tool_index=tool_index
                )
            ] = name

        if description is not None:
            attributes[
                ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_DESCRIPTION.format(
                    tool_index=tool_index
                )
            ] = description

        if parameters is None:
            continue

        try:
            serialized_parameters = json.dumps(parameters)
        except (TypeError, ValueError):
            serialized_parameters = str(parameters)

        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_PARAMETERS.format(
                tool_index=tool_index
            )
        ] = serialized_parameters

    return attributes
