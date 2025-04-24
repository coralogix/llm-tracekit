from typing import Optional

from openai.types.chat import ChatCompletion
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.semconv._incubating.attributes import (
    server_attributes as ServerAttributes,
)

import llm_tracekit.extended_gen_ai_attributes as ExtendedGenAIAttributes


def assert_messages_in_span(span: ReadableSpan, expected_messages: list):
    assert span.attributes is not None

    for index, message in enumerate(expected_messages):
        assert (
            span.attributes[
                ExtendedGenAIAttributes.GEN_AI_PROMPT_ROLE.format(prompt_index=index)
            ]
            == message["role"]
        )

        if "content" in message:
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
                ExtendedGenAIAttributes.GEN_AI_PROMPT_CONTENT.format(prompt_index=index)
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
                if "arguments" in tool_call["function"]:
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


def assert_choices_in_span(span: ReadableSpan, expected_choices: list):
    assert span.attributes is not None

    for index, choice in enumerate(expected_choices):
        assert (
            span.attributes[
                ExtendedGenAIAttributes.GEN_AI_COMPLETION_FINISH_REASON.format(
                    completion_index=index
                )
            ]
            == choice["finish_reason"]
        )
        assert (
            span.attributes[
                ExtendedGenAIAttributes.GEN_AI_COMPLETION_ROLE.format(
                    completion_index=index
                )
            ]
            == choice["message"]["role"]
        )
        if "content" in choice["message"]:
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
                if "arguments" in tool_call["function"]:
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


def assert_completion_attributes(
    span: ReadableSpan,
    request_model: str,
    response: ChatCompletion,
    operation_name: str = "chat",
    server_address: str = "api.openai.com",
):
    return assert_all_attributes(
        span,
        request_model,
        response.id,
        response.model,
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
        operation_name,
        server_address,
    )


def assert_all_attributes(
    span: ReadableSpan,
    request_model: str,
    response_id: str = None,
    response_model: str = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    operation_name: str = "chat",
    server_address: str = "api.openai.com",
):
    assert span.name == f"{operation_name} {request_model}"
    assert operation_name == span.attributes[GenAIAttributes.GEN_AI_OPERATION_NAME]
    assert (
        GenAIAttributes.GenAiSystemValues.OPENAI.value
        == span.attributes[GenAIAttributes.GEN_AI_SYSTEM]
    )
    assert request_model == span.attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL]
    if response_model:
        assert response_model == span.attributes[GenAIAttributes.GEN_AI_RESPONSE_MODEL]
    else:
        assert GenAIAttributes.GEN_AI_RESPONSE_MODEL not in span.attributes

    if response_id:
        assert response_id == span.attributes[GenAIAttributes.GEN_AI_RESPONSE_ID]
    else:
        assert GenAIAttributes.GEN_AI_RESPONSE_ID not in span.attributes

    if input_tokens is not None:
        assert (
            input_tokens == span.attributes[GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS]
        )
    else:
        assert GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS not in span.attributes

    if output_tokens is not None:
        assert (
            output_tokens == span.attributes[GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS]
        )
    else:
        assert GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS not in span.attributes

    assert server_address == span.attributes[ServerAttributes.SERVER_ADDRESS]


def get_current_weather_tool_definition():
    return {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. Boston, MA",
                    },
                },
                "required": ["location"],
                "additionalProperties": False,
            },
        },
    }
