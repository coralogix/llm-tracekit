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

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

import llm_tracekit.core._extended_gen_ai_attributes as ExtendedGenAIAttributes


def get_spans_by_name_prefix(
    exporter: InMemorySpanExporter, prefix: str
) -> list[ReadableSpan]:
    return [s for s in exporter.get_finished_spans() if s.name.startswith(prefix)]


def get_agent_spans(exporter: InMemorySpanExporter) -> list[ReadableSpan]:
    return get_spans_by_name_prefix(exporter, "invoke_agent")


def get_cycle_spans(exporter: InMemorySpanExporter) -> list[ReadableSpan]:
    return get_spans_by_name_prefix(exporter, "cycle")


def get_chat_spans(exporter: InMemorySpanExporter) -> list[ReadableSpan]:
    return get_spans_by_name_prefix(exporter, "chat")


def get_tool_spans(exporter: InMemorySpanExporter) -> list[ReadableSpan]:
    return get_spans_by_name_prefix(exporter, "execute_tool")


def assert_agent_span_attributes(
    span: ReadableSpan,
    agent_name: str,
    model: str | None = None,
):
    assert span.attributes is not None
    assert span.attributes[GenAIAttributes.GEN_AI_SYSTEM] == "strands"
    assert span.attributes[GenAIAttributes.GEN_AI_OPERATION_NAME] == "invoke_agent"
    assert span.attributes[GenAIAttributes.GEN_AI_AGENT_NAME] == agent_name
    if model:
        assert span.attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL] == model


def assert_chat_span_attributes(
    span: ReadableSpan,
    request_model: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
):
    assert span.attributes is not None
    assert span.attributes[GenAIAttributes.GEN_AI_SYSTEM] == "strands"
    assert span.attributes[GenAIAttributes.GEN_AI_OPERATION_NAME] == "chat"
    assert span.attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL] == request_model
    if input_tokens is not None:
        assert (
            span.attributes[GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS] == input_tokens
        )
    if output_tokens is not None:
        assert (
            span.attributes[GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS] == output_tokens
        )


def assert_tool_span_attributes(
    span: ReadableSpan,
    tool_name: str,
):
    assert span.attributes is not None
    assert span.attributes[GenAIAttributes.GEN_AI_SYSTEM] == "strands"
    assert span.attributes[GenAIAttributes.GEN_AI_OPERATION_NAME] == "execute_tool"
    assert span.attributes["name"] == tool_name
    assert span.attributes["type"] == "function"


def assert_messages_in_span(
    span: ReadableSpan, expected_messages: list, expect_content: bool
):
    assert span.attributes is not None

    for index, message in enumerate(expected_messages):
        assert (
            span.attributes[
                ExtendedGenAIAttributes.GEN_AI_PROMPT_ROLE.format(prompt_index=index)
            ]
            == message["role"]
        )

        if "content" in message:
            if expect_content:
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_PROMPT_CONTENT.format(
                            prompt_index=index
                        )
                    ]
                    == message["content"]
                )
            else:
                assert (
                    ExtendedGenAIAttributes.GEN_AI_PROMPT_CONTENT.format(
                        prompt_index=index
                    )
                    not in span.attributes
                )

        if "tool_calls" in message:
            for tool_index, tool_call in enumerate(message["tool_calls"]):
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_ID.format(
                            prompt_index=index, tool_call_index=tool_index
                        )
                    ]
                    == tool_call["id"]
                )
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_FUNCTION_NAME.format(
                            prompt_index=index, tool_call_index=tool_index
                        )
                    ]
                    == tool_call["function"]["name"]
                )

        if "tool_call_id" in message:
            assert (
                span.attributes[
                    ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALL_ID.format(
                        prompt_index=index
                    )
                ]
                == message["tool_call_id"]
            )


def assert_choices_in_span(
    span: ReadableSpan, expected_choices: list, expect_content: bool
):
    assert span.attributes is not None

    for index, choice in enumerate(expected_choices):
        assert (
            span.attributes[
                ExtendedGenAIAttributes.GEN_AI_COMPLETION_ROLE.format(
                    completion_index=index
                )
            ]
            == choice["message"]["role"]
        )
        if "finish_reason" in choice:
            assert (
                span.attributes[
                    ExtendedGenAIAttributes.GEN_AI_COMPLETION_FINISH_REASON.format(
                        completion_index=index
                    )
                ]
                == choice["finish_reason"]
            )
        if "content" in choice["message"]:
            if expect_content:
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_COMPLETION_CONTENT.format(
                            completion_index=index
                        )
                    ]
                    == choice["message"]["content"]
                )
            else:
                assert (
                    ExtendedGenAIAttributes.GEN_AI_COMPLETION_CONTENT.format(
                        completion_index=index
                    )
                    not in span.attributes
                )

        if "tool_calls" in choice["message"]:
            for tool_index, tool_call in enumerate(choice["message"]["tool_calls"]):
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_ID.format(
                            completion_index=index, tool_call_index=tool_index
                        )
                    ]
                    == tool_call["id"]
                )
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_FUNCTION_NAME.format(
                            completion_index=index, tool_call_index=tool_index
                        )
                    ]
                    == tool_call["function"]["name"]
                )
