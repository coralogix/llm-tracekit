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

import llm_tracekit.extended_gen_ai_attributes as ExtendedGenAIAttributes


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
                        ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_TYPE.format(
                            prompt_index=index, tool_call_index=tool_index
                        )
                    ]
                    == tool_call["type"]
                )
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_FUNCTION_NAME.format(
                            prompt_index=index, tool_call_index=tool_index
                        )
                    ]
                    == tool_call["function"]["name"]
                )
                if expect_content:
                    assert (
                        span.attributes[
                            ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_FUNCTION_ARGUMENTS.format(
                                prompt_index=index, tool_call_index=tool_index
                            )
                        ]
                        == tool_call["function"]["arguments"]
                    )
                else:
                    assert (
                        ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_FUNCTION_ARGUMENTS.format(
                            prompt_index=index, tool_call_index=tool_index
                        )
                        not in span.attributes
                    )
        else:
            assert (
                ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALLS_ID.format(
                    prompt_index=index, tool_call_index=0
                )
                not in span.attributes
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
        else:
            assert (
                ExtendedGenAIAttributes.GEN_AI_PROMPT_TOOL_CALL_ID.format(
                    prompt_index=index
                )
                not in span.attributes
            )

    # Check that there aren't any additional messages
    assert (
        ExtendedGenAIAttributes.GEN_AI_PROMPT_ROLE.format(prompt_index=index + 1)
        not in span.attributes
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
                        ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_TYPE.format(
                            completion_index=index, tool_call_index=tool_index
                        )
                    ]
                    == tool_call["type"]
                )
                assert (
                    span.attributes[
                        ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_FUNCTION_NAME.format(
                            completion_index=index, tool_call_index=tool_index
                        )
                    ]
                    == tool_call["function"]["name"]
                )
                if expect_content:
                    assert (
                        span.attributes[
                            ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_FUNCTION_ARGUMENTS.format(
                                completion_index=index, tool_call_index=tool_index
                            )
                        ]
                        == tool_call["function"]["arguments"]
                    )
                else:
                    assert (
                        ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_FUNCTION_ARGUMENTS.format(
                            completion_index=index, tool_call_index=tool_index
                        )
                        not in span.attributes
                    )
        else:
            assert (
                ExtendedGenAIAttributes.GEN_AI_COMPLETION_TOOL_CALLS_ID.format(
                    completion_index=index, tool_call_index=0
                )
                not in span.attributes
            )

    # Check that there aren't any additional choices
    assert (
        ExtendedGenAIAttributes.GEN_AI_COMPLETION_ROLE.format(
            completion_index=index + 1
        )
        not in span.attributes
    )
