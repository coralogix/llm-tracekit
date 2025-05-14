

from datetime import datetime
from typing import Dict, List


def _format_timestamp(timestamp_ms: int) -> str:
    dt = datetime.fromtimestamp(timestamp_ms / 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse_conversation_from_span(span: dict) -> list[dict]:
    span_attributes = span["attributes"]

    prompt_messages = _extract_messages(span_attributes, "prompt")
    completion_messages = _extract_messages(span_attributes, "completion")

    return prompt_messages + completion_messages


def _extract_messages(span_attributes: dict, section: str) -> list[Dict[str, str]]:
    messages = []
    index = 0
    while f"gen_ai.{section}.{index}.role" in span_attributes:
        content = span_attributes.get(f"gen_ai.{section}.{index}.content")

        # Found tool calls
        if (
            content is None
            and f"gen_ai.{section}.{index}.tool_calls.0.id" in span_attributes
        ):
            messages.extend(_extract_tool_calls_requests(index, span_attributes))
        elif content is not None:
            messages.append(
                {
                    "role": span_attributes[f"gen_ai.{section}.{index}.role"],
                    "content": content,
                }
            )

        index += 1

    return messages


def _extract_tool_calls_requests(
    message_index: int, span_attributes: dict
) -> List[Dict[str, str]]:
    tool_calls = []

    tool_call_index = 0

    while (
        f"gen_ai.completion.{message_index}.tool_calls.{tool_call_index}.id"
        in span_attributes
    ):
        tool_id = span_attributes[
            f"gen_ai.completion.{message_index}.tool_calls.{tool_call_index}.id"
        ]

        tool_name = span_attributes[
            f"gen_ai.completion.{message_index}.tool_calls.{tool_call_index}.function.name"
        ]

        tool_args = span_attributes[
            f"gen_ai.completion.{message_index}.tool_calls.{tool_call_index}.function.arguments"
        ]

        tool_calls.append(
            {
                "type": "tool_call",
                "role": "assistant",
                "tool_name": tool_name,
                "tool_arguments": tool_args,
                "tool_id": tool_id,
            }
        )

        tool_call_index += 1

    return tool_calls