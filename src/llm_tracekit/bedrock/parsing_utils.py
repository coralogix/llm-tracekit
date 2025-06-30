import json
import logging
import re
from typing import Optional

from llm_tracekit.span_builder import ToolCall

logger = logging.getLogger(__name__)

# Pre-compile regex for efficiency at the module level.
_CONTENT_PATTERN = re.compile(r"text=([^\]}]+)", re.DOTALL)
_ANSWER_PATTERN = re.compile(r"<answer>(.*?)</answer>", re.DOTALL)
_TOOL_USE_PATTERN = re.compile(
    r"\{\s*"
    r"input=(?P<function_arguments>\{.*\})\s*,\s*"
    r"name=(?P<function_name>[^,]+?)\s*,\s*"
    r"id=(?P<id>[^,]+?)\s*,\s*"
    r"type=(?P<type>tool_use)"
    r"\s*\}",
    re.DOTALL | re.IGNORECASE,
)
_TYPE_SUFFIX_PATTERN = re.compile(r",\s*type=\w+$")


def parse_content(raw_content: str) -> str:
    """Extracts the primary text content from a raw content string."""
    match = _CONTENT_PATTERN.search(raw_content)
    return match.group(1).strip() if match is not None else raw_content


def clean_user_content(content: str) -> str:
    """Removes the trailing ', type=text' suffix from user content."""
    return _TYPE_SUFFIX_PATTERN.sub("", content)


def extract_final_answer(content: str) -> str:
    """Extracts the content from within <answer> tags."""
    match = _ANSWER_PATTERN.search(content)
    return match.group(1).strip() if match is not None else content


def parse_tool_use(raw_content: str) -> Optional[ToolCall]:
    """Attempts to parse a tool call from the raw content string."""
    match = _TOOL_USE_PATTERN.search(raw_content)
    if match is None:
        return None

    extracted_data = match.groupdict()
    try:
        extracted_data["function_arguments"] = json.loads(
            extracted_data["function_arguments"]
        )
    except (json.JSONDecodeError, TypeError):
        logger.debug(
            "Could not parse tool call arguments as JSON: %s",
            extracted_data["function_arguments"],
        )
    return ToolCall(**extracted_data)