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

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.trace import SpanKind, StatusCode

SYSTEM = "microsoft_foundry"


def assert_base_chat_span(span: ReadableSpan, request_model: str):
    assert span.kind == SpanKind.CLIENT
    assert span.status.status_code in (StatusCode.UNSET, StatusCode.OK)
    assert span.name == f"chat {request_model}"
    assert span.attributes[GenAIAttributes.GEN_AI_OPERATION_NAME] == "chat"
    assert span.attributes[GenAIAttributes.GEN_AI_SYSTEM] == SYSTEM
    assert span.attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL] == request_model


def assert_base_responses_span(span: ReadableSpan, request_model: str):
    assert span.kind == SpanKind.CLIENT
    assert span.status.status_code in (StatusCode.UNSET, StatusCode.OK)
    assert span.name == f"chat {request_model}"
    assert span.attributes[GenAIAttributes.GEN_AI_OPERATION_NAME] == "chat"
    assert span.attributes[GenAIAttributes.GEN_AI_SYSTEM] == SYSTEM
    assert span.attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL] == request_model


def assert_base_embeddings_span(span: ReadableSpan, request_model: str):
    assert span.kind == SpanKind.CLIENT
    assert span.status.status_code in (StatusCode.UNSET, StatusCode.OK)
    assert span.name == f"embeddings {request_model}"
    assert span.attributes[GenAIAttributes.GEN_AI_OPERATION_NAME] == "embeddings"
    assert span.attributes[GenAIAttributes.GEN_AI_SYSTEM] == SYSTEM
    assert span.attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL] == request_model


def assert_prompt_messages(
    span: ReadableSpan,
    expected: list[dict],
    expect_content: bool,
):
    """Assert prompt messages in span attributes."""
    for i, msg in enumerate(expected):
        role_key = f"gen_ai.prompt.{i}.role"
        content_key = f"gen_ai.prompt.{i}.content"

        assert span.attributes.get(role_key) == msg["role"], (
            f"Expected role {msg['role']} at index {i}, got {span.attributes.get(role_key)}"
        )

        if expect_content and "content" in msg:
            assert content_key in span.attributes, f"Expected content at index {i}"
            assert span.attributes[content_key] == msg["content"]
        elif not expect_content:
            pass


def assert_completion(
    span: ReadableSpan,
    role: str = "assistant",
    finish_reason: str | None = None,
    expect_content: bool = True,
    content: str | None = None,
):
    """Assert completion (response) attributes in span."""
    assert span.attributes.get("gen_ai.completion.0.role") == role

    if finish_reason is not None:
        assert span.attributes.get("gen_ai.completion.0.finish_reason") == finish_reason

    if expect_content:
        actual_content = span.attributes.get("gen_ai.completion.0.content")
        assert actual_content is not None, "Expected content in completion"
        if content is not None:
            assert actual_content == content


def assert_tool_calls(
    span: ReadableSpan,
    expected_tools: list[dict],
    prefix: str = "gen_ai.completion.0",
):
    """Assert tool calls in span attributes."""
    for i, tool in enumerate(expected_tools):
        base = f"{prefix}.tool_calls.{i}"
        assert span.attributes.get(f"{base}.type") == tool.get("type", "function")
        assert span.attributes.get(f"{base}.function.name") == tool["name"]
        if "arguments" in tool:
            assert span.attributes.get(f"{base}.function.arguments") == tool["arguments"]


def assert_request_tools(span: ReadableSpan, expected_tools: list[dict]):
    """Assert tool definitions in span attributes."""
    for i, tool in enumerate(expected_tools):
        base = f"gen_ai.request.tools.{i}"
        assert span.attributes.get(f"{base}.type") == tool.get("type", "function")
        assert span.attributes.get(f"{base}.function.name") == tool["name"]
        if "description" in tool:
            assert span.attributes.get(f"{base}.function.description") == tool["description"]


def assert_error_span(span: ReadableSpan, error_type: str | None = None):
    """Assert span has error status."""
    assert span.status.status_code == StatusCode.ERROR
    if error_type:
        assert error_type in span.attributes.get("error.type", "")
