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

import llm_tracekit.core._extended_gen_ai_attributes as ExtendedGenAIAttributes


def assert_base_chat_span(
    span: ReadableSpan,
    *,
    request_model: str,
):
    assert span.attributes is not None
    assert span.name == f"chat {request_model}"
    assert (
        span.attributes[GenAIAttributes.GEN_AI_OPERATION_NAME]
        == GenAIAttributes.GenAiOperationNameValues.CHAT.value
    )
    assert (
        span.attributes[GenAIAttributes.GEN_AI_SYSTEM]
        == GenAIAttributes.GenAiSystemValues.ANTHROPIC.value
    )
    assert span.attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL] == request_model


def assert_prompt_messages(
    span: ReadableSpan,
    expected: list[dict[str, object]],
    *,
    expect_content: bool,
):
    assert span.attributes is not None
    for index, message in enumerate(expected):
        role_key = ExtendedGenAIAttributes.GEN_AI_PROMPT_ROLE.format(prompt_index=index)
        assert span.attributes[role_key] == message["role"]
        if "content" in message and message["content"] is not None:
            content_key = ExtendedGenAIAttributes.GEN_AI_PROMPT_CONTENT.format(
                prompt_index=index
            )
            if expect_content:
                assert span.attributes[content_key] == message["content"]
            else:
                assert content_key not in span.attributes


def assert_completion(
    span: ReadableSpan,
    *,
    finish_reason: str | None = None,
    role: str = "assistant",
    content: str | None = None,
    expect_content: bool,
):
    assert span.attributes is not None
    idx = 0
    if finish_reason is not None:
        assert (
            span.attributes[
                ExtendedGenAIAttributes.GEN_AI_COMPLETION_FINISH_REASON.format(
                    completion_index=idx
                )
            ]
            == finish_reason
        )
    assert (
        span.attributes[
            ExtendedGenAIAttributes.GEN_AI_COMPLETION_ROLE.format(completion_index=idx)
        ]
        == role
    )
    content_key = ExtendedGenAIAttributes.GEN_AI_COMPLETION_CONTENT.format(
        completion_index=idx
    )
    if expect_content and content is not None:
        assert span.attributes.get(content_key) == content
    elif not expect_content:
        assert content_key not in span.attributes
