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

"""Utilities for extracting LangGraph-specific span attributes."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)


class LangGraphSpanAttributes:
    """Attribute keys emitted for LangGraph node spans."""

    NODE = "gen_ai.langgraph.node"
    STEP = "gen_ai.langgraph.step"
    TRIGGERS = "gen_ai.langgraph.triggers"
    PATH = "gen_ai.langgraph.path"
    CHECKPOINT_NS = "gen_ai.langgraph.checkpoint_ns"
    THREAD_ID = "gen_ai.thread.id"
    TASK_ID = "gen_ai.task.id"
    STATUS = "gen_ai.langgraph.status"
    TAGS = "gen_ai.tags"


def build_node_span_name(node_name: str | None) -> str:
    """Return a descriptive span name for a LangGraph node."""

    if node_name:
        return f"LangGraph Node {node_name}"
    return "LangGraph Node"


def extract_node_attributes(
    metadata: Mapping[str, Any] | None,
    tags: list[str] | None,
) -> tuple[str | None, dict[str, Any]] | None:
    """Extract OTEL attributes for a LangGraph node span.

    Returns the node name (if present) and the attribute dictionary. If the
    provided metadata does not represent a LangGraph node execution, ``None``
    is returned.
    """

    if not metadata or "langgraph_node" not in metadata:
        return None

    node_name = _safe_str(metadata.get("langgraph_node"))
    attributes: dict[str, Any] = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: "langgraph.node",
    }
    if node_name:
        attributes[LangGraphSpanAttributes.NODE] = node_name

    step = _maybe_int(metadata.get("langgraph_step"))
    if step is not None:
        attributes[LangGraphSpanAttributes.STEP] = step

    triggers = metadata.get("langgraph_triggers")
    if isinstance(triggers, (list, tuple)):
        attributes[LangGraphSpanAttributes.TRIGGERS] = list(triggers)

    path = metadata.get("langgraph_path")
    path_value = _safe_str(path)
    if path_value is not None:
        attributes[LangGraphSpanAttributes.PATH] = path_value

    checkpoint_ns = _safe_str(metadata.get("langgraph_checkpoint_ns"))
    if checkpoint_ns is not None:
        attributes[LangGraphSpanAttributes.CHECKPOINT_NS] = checkpoint_ns

    thread_id = _safe_str(
        metadata.get("thread_id") or metadata.get("langgraph_thread_id")
    )
    if thread_id is not None:
        attributes[LangGraphSpanAttributes.THREAD_ID] = thread_id

    task_id = _safe_str(metadata.get("langgraph_task_id"))
    if task_id is not None:
        attributes[LangGraphSpanAttributes.TASK_ID] = task_id

    if tags:
        attributes[LangGraphSpanAttributes.TAGS] = list(tags)

    _merge_user_metadata(metadata, attributes)
    return node_name, attributes


def _merge_user_metadata(
    metadata: Mapping[str, Any],
    attributes: MutableMapping[str, Any],
) -> None:
    for key, value in metadata.items():
        if key.startswith("langgraph_"):
            continue
        if key in {"thread_id", "langgraph_thread_id", "langgraph_task_id"}:
            continue
        attributes.setdefault(f"langgraph.metadata.{key}", value)


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def _maybe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
