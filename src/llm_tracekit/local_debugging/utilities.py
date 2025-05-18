from datetime import datetime
from typing import Dict, List


def is_prefix(a: List, b: List) -> bool:
    return len(a) < len(b) and all(x == y for x, y in zip(a, b))


def split_to_sessions(spans: List[dict]) -> List[Dict]:
    for span in spans:
        span["history"] = parse_conversation_from_span(span)
        span["contains_other_span"] = False
        span["should_delete"] = False

    # Sorting the spans from oldest to newest
    spans = sorted(spans, key=lambda t: t["timestamp"])

    # Going through the spans from oldest (= smallest) to newest (= biggest)
    # If span i is a prefix of a newer span j, mark span i for deletion.
    # We only allow span j to delete a single span, because we might have a case where
    # there are 2 same spans (span A), where only one of the spans is being used as a message history for the next span (span B).
    # in that case, we want to show 2 conversations - span A and span B.
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            if (
                is_prefix(spans[i]["history"], spans[j]["history"])
                and not spans[j]["contains_other_span"]
            ):
                spans[j]["contains_other_span"] = True
                spans[i]["should_delete"] = True

    sessions = [span for span in spans if not span["should_delete"]]
    for session in sessions:
        session.pop("contains_other_span")
        session.pop("should_delete")

    return sessions


def format_timestamp(timestamp_ms: int) -> str:
    dt = datetime.fromtimestamp(timestamp_ms / 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_conversation_from_span(span: dict) -> List[Dict]:
    span_attributes = span["attributes"]

    prompt_messages = _extract_messages(span_attributes, "prompt")
    completion_messages = _extract_messages(span_attributes, "completion")

    return prompt_messages + completion_messages


def _extract_messages(span_attributes: dict, section: str) -> List[Dict[str, str]]:
    messages = []
    index = 0
    while f"gen_ai.{section}.{index}.role" in span_attributes:
        content = span_attributes.get(f"gen_ai.{section}.{index}.content")

        # Found tool calls
        if (
            content is None
            and f"gen_ai.{section}.{index}.tool_calls.0.id" in span_attributes
        ):
            messages.extend(
                _extract_tool_calls_requests(index, span_attributes, section)
            )
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
    message_index: int, span_attributes: dict, section
) -> List[Dict[str, str]]:
    tool_calls = []

    tool_call_index = 0

    while (
        f"gen_ai.{section}.{message_index}.tool_calls.{tool_call_index}.id"
        in span_attributes
    ):
        tool_id = span_attributes[
            f"gen_ai.{section}.{message_index}.tool_calls.{tool_call_index}.id"
        ]

        tool_name = span_attributes[
            f"gen_ai.{section}.{message_index}.tool_calls.{tool_call_index}.function.name"
        ]

        tool_args = span_attributes[
            f"gen_ai.{section}.{message_index}.tool_calls.{tool_call_index}.function.arguments"
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
