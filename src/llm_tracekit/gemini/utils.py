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

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

from llm_tracekit.span_builder import (
    Choice,
    Message,
    ToolCall,
    generate_base_attributes,
    generate_choice_attributes,
    generate_message_attributes,
    generate_request_attributes,
    generate_response_attributes,
)

_GOOGLE_GENAI_SYSTEM = GenAIAttributes.GenAiSystemValues.GEMINI.value
_OPERATION_NAME_VALUE = GenAIAttributes.GenAiOperationNameValues.CHAT.value


@dataclass
class GeminiUsage:
    prompt_tokens: Optional[int] = None
    candidates_tokens: Optional[int] = None


@dataclass
class GeminiRequestDetails:
    span_name: str
    span_attributes: Dict[str, Any]
    model: Optional[str]


@dataclass
class GeminiResponseDetails:
    span_attributes: Dict[str, Any]
    model: Optional[str]
    response_id: Optional[str]
    finish_reasons: List[str] = field(default_factory=list)
    usage: GeminiUsage = field(default_factory=GeminiUsage)
    choices: List[Choice] = field(default_factory=list)


@dataclass
class GeminiPartialToolCall:
    index: int
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    arguments: Optional[str] = None


@dataclass
class GeminiToolResponsePart:
    index: int
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    result: Optional[str] = None
    raw_content: Optional[str] = None


@dataclass
class GeminiToolCallBuffer:
    index: int
    tool_call_id: Optional[str] = None
    function_name: Optional[str] = None
    arguments: List[str] = field(default_factory=list)

    def add_arguments(self, value: Optional[str], capture_content: bool) -> None:
        if not capture_content:
            return
        if value is None:
            return
        self.arguments.append(value)

    def to_tool_call(self, capture_content: bool) -> ToolCall:
        arguments_value: Optional[str] = None
        if capture_content and self.arguments:
            arguments_value = "".join(self.arguments)

        return ToolCall(
            id=self.tool_call_id,
            type="function",
            function_name=self.function_name,
            function_arguments=arguments_value,
        )


@dataclass
class GeminiCandidateBuffer:
    index: int
    role: Optional[str] = None
    finish_reason: Optional[str] = None
    text_parts: List[str] = field(default_factory=list)
    tool_calls: Dict[int, GeminiToolCallBuffer] = field(default_factory=dict)

    def append_text(self, text: Optional[str]) -> None:
        if text is None:
            return
        self.text_parts.append(text)

    def upsert_tool_call(
        self, tool_call: GeminiPartialToolCall, capture_content: bool
    ) -> None:
        call_index = tool_call.index
        if call_index not in self.tool_calls:
            self.tool_calls[call_index] = GeminiToolCallBuffer(index=call_index)

        buffer = self.tool_calls[call_index]
        if tool_call.tool_call_id is not None:
            buffer.tool_call_id = tool_call.tool_call_id
        if tool_call.name is not None:
            buffer.function_name = tool_call.name
        buffer.add_arguments(tool_call.arguments, capture_content)

    def to_choice(self, capture_content: bool) -> Choice:
        content_value: Optional[str] = None
        if self.text_parts:
            content_value = "".join(self.text_parts)

        tool_calls_list: Optional[List[ToolCall]] = None
        if self.tool_calls:
            tool_calls_list = [
                self.tool_calls[index].to_tool_call(capture_content)
                for index in sorted(self.tool_calls)
            ]

        return Choice(
            finish_reason=self.finish_reason,
            role=self.role,
            content=content_value,
            tool_calls=tool_calls_list,
        )


@dataclass
class GeminiStreamState:
    capture_content: bool
    model: Optional[str] = None
    response_id: Optional[str] = None
    usage: GeminiUsage = field(default_factory=GeminiUsage)
    candidate_buffers: Dict[int, GeminiCandidateBuffer] = field(default_factory=dict)

    def ingest_chunk(self, chunk: Any) -> None:
        if chunk is None:
            return

        chunk_model = _extract_model_name(chunk)
        if chunk_model is not None and self.model is None:
            self.model = chunk_model

        chunk_response_id = _safe_get(chunk, "response_id") or _safe_get(chunk, "id")
        if chunk_response_id is not None and self.response_id is None:
            self.response_id = chunk_response_id

        usage = extract_usage_metadata(chunk)
        if usage.prompt_tokens is not None:
            self.usage.prompt_tokens = usage.prompt_tokens
        if usage.candidates_tokens is not None:
            self.usage.candidates_tokens = usage.candidates_tokens

        for index, candidate in enumerate(_iter_sequence(_safe_get(chunk, "candidates"))):
            buffer = self._get_candidate_buffer(candidate_index=index)
            finish_reason_candidate = _normalize_finish_reason(
                _safe_get(candidate, "finish_reason")
            )
            if isinstance(finish_reason_candidate, str) and finish_reason_candidate:
                buffer.finish_reason = finish_reason_candidate
            content = _safe_get(candidate, "content")
            if content is None:
                continue
            role = _safe_get(content, "role")
            if role is not None:
                buffer.role = role
            for part_index, part in enumerate(_iter_parts(content)):
                text_part = _extract_text_from_part(part)
                if text_part is not None:
                    buffer.append_text(text_part)
                partial_tool_call = extract_tool_call_from_part(part, part_index)
                if partial_tool_call is not None:
                    buffer.upsert_tool_call(partial_tool_call, self.capture_content)

    def finalize(self) -> GeminiResponseDetails:
        choices = [
            buffer.to_choice(self.capture_content)
            for _, buffer in sorted(self.candidate_buffers.items())
        ]
        finish_reasons = [
            choice.finish_reason
            for choice in choices
            if choice.finish_reason is not None
        ]

        normalized_finish_reasons: List[str] = []
        for finish_reason in finish_reasons:
            normalized_value = _normalize_finish_reason(finish_reason)
            if normalized_value is None:
                continue
            normalized_finish_reasons.append(str(normalized_value))

        attributes = {
            **generate_response_attributes(
                model=self.model,
                finish_reasons=normalized_finish_reasons or None,
                id=self.response_id,
                usage_input_tokens=self.usage.prompt_tokens,
                usage_output_tokens=self.usage.candidates_tokens,
            ),
            **generate_choice_attributes(choices=choices, capture_content=self.capture_content),
        }

        return GeminiResponseDetails(
            span_attributes=attributes,
            model=self.model,
            response_id=self.response_id,
            finish_reasons=normalized_finish_reasons,
            usage=self.usage,
            choices=choices,
        )

    def _get_candidate_buffer(self, candidate_index: int) -> GeminiCandidateBuffer:
        if candidate_index not in self.candidate_buffers:
            self.candidate_buffers[candidate_index] = GeminiCandidateBuffer(
                index=candidate_index
            )
        return self.candidate_buffers[candidate_index]


def build_request_details(
    model: Optional[str],
    contents: Any,
    system_instruction: Any,
    config: Any,
    capture_content: bool,
) -> GeminiRequestDetails:
    messages = []
    if system_instruction is not None:
        messages.append(
            Message(
                role="system",
                content=_stringify_value(system_instruction),
            )
        )

    messages.extend(_contents_to_messages(contents))

    request_attributes = generate_request_attributes(
        model=model,
        temperature=_safe_get(config, "temperature"),
        top_p=_safe_get(config, "top_p"),
        top_k=_safe_get(config, "top_k"),
        max_tokens=_safe_get(config, "max_output_tokens"),
    )

    message_attributes = generate_message_attributes(
        messages=messages,
        capture_content=capture_content,
    )

    attributes: Dict[str, Any] = {
        **generate_base_attributes(system=_GOOGLE_GENAI_SYSTEM),
        **request_attributes,
        **message_attributes,
    }

    config_attributes = _config_to_request_attributes(config)
    if config_attributes:
        attributes.update(config_attributes)

    span_name = f"{_OPERATION_NAME_VALUE}"

    return GeminiRequestDetails(
        span_name=span_name,
        span_attributes=attributes,
        model=model,
    )


def build_response_details(
    response: Any,
    capture_content: bool,
) -> GeminiResponseDetails:
    state = GeminiStreamState(capture_content=capture_content)
    state.ingest_chunk(response)
    if state.model is None:
        state.model = _extract_model_name(response)
    return state.finalize()


def extract_tool_call_from_part(
    part: Any,
    fallback_index: int,
) -> Optional[GeminiPartialToolCall]:
    function_call = _safe_get(part, "function_call")
    if function_call is None:
        return None

    call_index = _safe_get(function_call, "index")
    if call_index is None:
        call_index = fallback_index

    arguments_value = _normalize_arguments(_safe_get(function_call, "args"))
    if arguments_value is None:
        arguments_value = _normalize_arguments(_safe_get(function_call, "arguments"))

    return GeminiPartialToolCall(
        index=call_index,
        tool_call_id=_safe_get(function_call, "id"),
        name=_safe_get(function_call, "name"),
        arguments=arguments_value,
    )


def extract_tool_response_from_part(
    part: Any,
    fallback_index: int,
) -> Optional[GeminiToolResponsePart]:
    function_response = _safe_get(part, "function_response")
    if function_response is None:
        return None

    response_index = _safe_get(function_response, "index")
    if response_index is None:
        response_index = fallback_index

    response_payload = _safe_get(function_response, "response")
    result_value: Optional[str] = None
    raw_content_value: Optional[str] = None

    if response_payload is not None:
        result_candidate = _safe_get(response_payload, "result")
        if isinstance(result_candidate, str):
            result_value = result_candidate
        elif result_candidate is not None:
            raw_content_value = _stringify_value(result_candidate)

    if result_value is None and isinstance(response_payload, str):
        result_value = response_payload

    if raw_content_value is None and response_payload is not None and not isinstance(response_payload, str):
        raw_content_value = _stringify_value(response_payload)

    return GeminiToolResponsePart(
        index=response_index,
        tool_call_id=_safe_get(function_response, "id"),
        name=_safe_get(function_response, "name"),
        result=result_value,
        raw_content=raw_content_value,
    )


def extract_usage_metadata(value: Any) -> GeminiUsage:
    metadata = _safe_get(value, "usage_metadata")
    if metadata is None:
        return GeminiUsage()

    prompt_tokens = _as_int(_safe_get(metadata, "prompt_token_count"))
    if prompt_tokens is None:
        prompt_tokens = _as_int(_safe_get(metadata, "input_token_count"))

    candidates_tokens = _as_int(_safe_get(metadata, "candidates_token_count"))
    if candidates_tokens is None:
        candidates_tokens = _as_int(_safe_get(metadata, "output_token_count"))

    return GeminiUsage(
        prompt_tokens=prompt_tokens,
        candidates_tokens=candidates_tokens,
    )


def _config_to_request_attributes(config: Any) -> Dict[str, Any]:
    if config is None:
        return {}

    attributes: Dict[str, Any] = {}

    candidate_count = _safe_get(config, "candidate_count")
    if candidate_count is not None and hasattr(GenAIAttributes, "GEN_AI_REQUEST_CANDIDATE_COUNT"):
        attributes[getattr(GenAIAttributes, "GEN_AI_REQUEST_CANDIDATE_COUNT")] = candidate_count

    stop_sequences = _safe_get(config, "stop_sequences")
    if stop_sequences is not None and hasattr(GenAIAttributes, "GEN_AI_REQUEST_STOP_SEQUENCES"):
        attributes[getattr(GenAIAttributes, "GEN_AI_REQUEST_STOP_SEQUENCES")] = list(
            _iter_sequence(stop_sequences)
        )

    response_mime_type = _safe_get(config, "response_mime_type")
    if response_mime_type is not None and hasattr(GenAIAttributes, "GEN_AI_RESPONSE_CONTENT_TYPE"):
        attributes[getattr(GenAIAttributes, "GEN_AI_RESPONSE_CONTENT_TYPE")] = response_mime_type

    return attributes


def _contents_to_messages(contents: Any) -> List[Message]:
    messages: List[Message] = []
    for entry in _iter_sequence(contents):
        if entry is None:
            continue

        if isinstance(entry, str):
            messages.append(
                Message(
                    role="user",
                    content=entry,
                )
            )
            continue

        role = _safe_get(entry, "role")

        if role == "tool":
            tool_responses: List[GeminiToolResponsePart] = []
            tool_text_fragments: List[str] = []
            for part_index, part in enumerate(_iter_parts(entry)):
                tool_response = extract_tool_response_from_part(part, part_index)
                if tool_response is not None:
                    tool_responses.append(tool_response)
                    continue

                text_value = _extract_text_from_part(part)
                if text_value is not None:
                    tool_text_fragments.append(text_value)

            if tool_responses:
                for response_part in tool_responses:
                    tool_content_value = response_part.result or response_part.raw_content
                    if tool_content_value is None:
                        continue
                    messages.append(
                        Message(
                            role="tool",
                            content=tool_content_value,
                            tool_call_id=response_part.tool_call_id,
                        )
                    )

                if tool_text_fragments:
                    messages.append(
                        Message(
                            role="tool",
                            content="".join(tool_text_fragments),
                        )
                    )

                continue

        text_fragments: List[str] = []
        tool_call_buffers: Dict[int, GeminiToolCallBuffer] = {}
        message_tool_call_id: Optional[str] = None
        for part_index, part in enumerate(_iter_parts(entry)):
            text_value = _extract_text_from_part(part)
            if text_value is not None:
                text_fragments.append(text_value)

            partial_tool_call = extract_tool_call_from_part(part, part_index)
            if partial_tool_call is not None:
                buffer = tool_call_buffers.get(partial_tool_call.index)
                if buffer is None:
                    buffer = GeminiToolCallBuffer(index=partial_tool_call.index)
                    tool_call_buffers[partial_tool_call.index] = buffer

                if partial_tool_call.tool_call_id is not None:
                    buffer.tool_call_id = partial_tool_call.tool_call_id
                if partial_tool_call.name is not None:
                    buffer.function_name = partial_tool_call.name
                buffer.add_arguments(partial_tool_call.arguments, capture_content=True)

        content_value: Optional[str] = None
        if text_fragments:
            content_value = "".join(text_fragments)
        elif not tool_call_buffers:
            content_value = _stringify_value(entry)

        tool_calls_list: Optional[List[ToolCall]] = None
        if tool_call_buffers:
            sorted_buffers = [buffer for _, buffer in sorted(tool_call_buffers.items())]
            for buffer in sorted_buffers:
                if buffer.tool_call_id is not None and message_tool_call_id is None:
                    message_tool_call_id = buffer.tool_call_id
                    break

            tool_calls_list = [
                ToolCall(
                    id=buffer.tool_call_id,
                    type="function",
                    function_name=buffer.function_name,
                    function_arguments="".join(buffer.arguments) if buffer.arguments else None,
                )
                for buffer in sorted_buffers
            ]

        messages.append(
            Message(
                role=role or "user",
                content=content_value,
                tool_call_id=message_tool_call_id,
                tool_calls=tool_calls_list,
            )
        )

    return messages


def _iter_parts(content: Any) -> Iterable[Any]:
    if content is None:
        return ()

    parts = _safe_get(content, "parts")
    if parts is None:
        return _iter_sequence(content)

    return _iter_sequence(parts)


def _iter_sequence(value: Any) -> Iterable[Any]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return value
    if isinstance(value, Iterable):
        return value
    return (value,)


def _extract_text_from_part(part: Any) -> Optional[str]:
    if part is None:
        return None
    if isinstance(part, str):
        return part

    text_value = _safe_get(part, "text")
    if isinstance(text_value, str):
        return text_value

    return None


def _normalize_arguments(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return str(value)


def _normalize_finish_reason(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value.split(".")[-1]

    name_attr = _safe_get(value, "name")
    if isinstance(name_attr, str) and name_attr:
        return name_attr.split(".")[-1]

    value_attr = _safe_get(value, "value")
    if isinstance(value_attr, str) and value_attr:
        return value_attr.split(".")[-1]

    stringified = str(value)
    if not stringified:
        return None
    if "." in stringified:
        candidate = stringified.split(".")[-1]
        if candidate:
            return candidate

    return stringified


def _safe_get(obj: Any, attribute: str) -> Any:
    if obj is None:
        return None

    if isinstance(obj, dict):
        return obj.get(attribute)

    return getattr(obj, attribute, None)


def _stringify_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)

    if hasattr(value, "model_dump"):
        try:
            if hasattr(value, "model_dump_json"):
                return value.model_dump_json()
            return json.dumps(value.model_dump())
        except (TypeError, ValueError):
            return str(value.model_dump())

    if hasattr(value, "to_dict"):
        try:
            return json.dumps(value.to_dict())
        except (TypeError, ValueError):
            return str(value.to_dict())

    if isinstance(value, (list, tuple, dict)):
        try:
            return json.dumps(value)
        except (TypeError, ValueError):
            pass

    return str(value)


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_model_name(candidate: Any) -> Optional[str]:
    if candidate is None:
        return None
    if isinstance(candidate, str):
        return candidate
    if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes)):
        for item in candidate:
            coerced = _coerce_model_name(item)
            if coerced:
                return coerced
        return None

    for attribute in ("name", "model", "model_name", "model_version"):
        nested_value = _safe_get(candidate, attribute)
        if isinstance(nested_value, str) and nested_value:
            return nested_value

    return None


def _extract_model_name(value: Any) -> Optional[str]:
    if value is None:
        return None

    for attribute in ("model", "model_name", "model_version"):
        model_candidate = _coerce_model_name(_safe_get(value, attribute))
        if model_candidate:
            return model_candidate

    response_metadata = _safe_get(value, "response_metadata")
    if response_metadata is not None:
        model_candidate = _coerce_model_name(response_metadata)
        if model_candidate:
            return model_candidate
        model_candidate = _coerce_model_name(_safe_get(response_metadata, "model_version"))
        if model_candidate:
            return model_candidate

    candidates = _safe_get(value, "candidates")
    for candidate in _iter_sequence(candidates):
        model_candidate = _coerce_model_name(_safe_get(candidate, "model"))
        if model_candidate:
            return model_candidate
        candidate_metadata = _safe_get(candidate, "metadata")
        model_candidate = _coerce_model_name(_safe_get(candidate_metadata, "model_version"))
        if model_candidate:
            return model_candidate

    return None
