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

from typing import Any, Mapping


class LangGraphSpanAttributes:
    """Attribute keys for LangGraph node spans (node name and step)."""

    NODE = "gen_ai.langgraph.node"
    STEP = "gen_ai.langgraph.step"


def build_node_span_name(node_name: str | None) -> str:
    """Return a descriptive span name for a LangGraph node."""

    if node_name:
        return f"LangGraph Node {node_name}"
    return "LangGraph Node"


def extract_node_attributes(
    metadata: Mapping[str, Any] | None,
) -> tuple[str | None, dict[str, Any]] | None:
    """Extract node name and attributes for a LangGraph node span.

    Returns the node name (if present) and a dict with NODE and STEP when set.
    If the metadata does not represent a LangGraph node execution, returns None.
    """

    if not isinstance(metadata, Mapping) or "langgraph_node" not in metadata:
        return None

    path = metadata.get("langgraph_path")
    path_value = _safe_str(path)
    # Only create a span for top-level node runs. Conditional edges (and other
    # sub-invocations) can be reported with the same langgraph_node; they often
    # have a path with more than two segments (e.g. "root.llm_call.conditional").
    # Skip those so we get one span per node execution.
    if path_value is not None:
        segments = [s for s in path_value.split(".") if s]
        if len(segments) > 2:
            return None

    node_name = _safe_str(metadata.get("langgraph_node"))
    attributes: dict[str, Any] = {}
    if node_name:
        attributes[LangGraphSpanAttributes.NODE] = node_name

    step = _maybe_int(metadata.get("langgraph_step"))
    if step is not None:
        attributes[LangGraphSpanAttributes.STEP] = step

    return node_name, attributes


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
