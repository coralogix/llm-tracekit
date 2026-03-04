"""Helper functions for LangGraph instrumentation tests."""

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

from typing import Any

from opentelemetry.sdk.trace import ReadableSpan


def assert_node_span_has_attributes(span: ReadableSpan, **expected: Any) -> None:
    """Assert that the span has the given attribute keys with the given values."""
    attrs = span.attributes or {}
    for key, value in expected.items():
        assert key in attrs, f"Missing attribute {key!r} on span {span.name}"
        assert attrs[key] == value, (
            f"Attribute {key!r}: expected {value!r}, got {attrs[key]!r}"
        )
