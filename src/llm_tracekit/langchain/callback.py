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
from collections.abc import Mapping
from timeit import default_timer
from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler  # type: ignore
from langchain_core.messages import BaseMessage  # type: ignore
from langchain_core.outputs import LLMResult  # type: ignore
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

from llm_tracekit import extended_gen_ai_attributes as ExtendedGenAIAttributes
from llm_tracekit.instrumentation_utils import handle_span_exception
from llm_tracekit.instruments import Instruments
from llm_tracekit.langchain.span_manager import LangChainSpanManager, LangChainSpanState
from llm_tracekit.langchain.utils import (
    build_prompt_history,
    build_response_choices,
    flatten_message_batches,
)
from llm_tracekit.span_builder import (
    generate_base_attributes,
    generate_choice_attributes,
    generate_message_attributes,
    generate_request_attributes,
    generate_response_attributes,
)

_PROVIDER_SYSTEM_MAP = {
    "ChatOpenAI": GenAIAttributes.GenAiSystemValues.OPENAI,
    "ChatBedrock": GenAIAttributes.GenAiSystemValues.AWS_BEDROCK,
}

_PROVIDER_ATTRIBUTE = "gen_ai.provider.name"


class LangChainCallbackHandler(BaseCallbackHandler):  # type: ignore[misc]
    def __init__(
        self,
        tracer,
        instruments: Instruments,
        capture_content: bool,
    ) -> None:
        super().__init__()  # type: ignore
        self._span_manager = LangChainSpanManager(tracer)
        self._instruments = instruments
        self._capture_content = capture_content

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        provider_name = serialized.get("name")
        if not isinstance(provider_name, str):
            return None
        system_value = _PROVIDER_SYSTEM_MAP.get(provider_name)
        if system_value is None:
            return None

        invocation_params = _extract_invocation_params(kwargs)
        request_model = _extract_request_model(invocation_params, metadata)
        if request_model is None:
            return None

        prompt_history = build_prompt_history(
            flatten_message_batches(messages)
        )

        request_attributes = generate_request_attributes(
            model=request_model,
            temperature=_get_value(invocation_params, metadata, "temperature", "ls_temperature"),
            top_p=_get_value(invocation_params, metadata, "top_p"),
            top_k=_get_value(invocation_params, metadata, "top_k"),
            max_tokens=_get_value(invocation_params, metadata, "max_tokens", "ls_max_tokens"),
            presence_penalty=_get_value(invocation_params, metadata, "presence_penalty"),
            frequency_penalty=_get_value(invocation_params, metadata, "frequency_penalty"),
        )

        span_attributes: Dict[str, Any] = {
            **generate_base_attributes(system=system_value),
            **request_attributes,
            **generate_message_attributes(
                messages=prompt_history, capture_content=self._capture_content
            ),
        }

        available_tool_attributes = _generate_available_tools_attributes(invocation_params)
        if available_tool_attributes:
            span_attributes.update(available_tool_attributes)

        stop_sequences = _get_value(invocation_params, metadata, "stop")
        if stop_sequences is not None:
            span_attributes[GenAIAttributes.GEN_AI_REQUEST_STOP_SEQUENCES] = stop_sequences

        seed = _get_value(invocation_params, metadata, "seed")
        if seed is not None:
            span_attributes[GenAIAttributes.GEN_AI_REQUEST_SEED] = seed

        provider_attr = (metadata or {}).get("ls_provider")
        if provider_attr:
            span_attributes[_PROVIDER_ATTRIBUTE] = provider_attr

        span_name = f"{GenAIAttributes.GenAiOperationNameValues.CHAT.value} {request_model}"
        self._span_manager.create_chat_span(
            run_id=run_id,
            parent_run_id=parent_run_id,
            span_name=span_name,
            attributes=span_attributes,
        )

        state = self._span_manager.get_state(run_id)
        if state:
            state.request_model = request_model
        return None

    def on_llm_end(
        self,
        response: LLMResult,  # type: ignore[override]
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> Any:
        state = self._span_manager.get_state(run_id)
        if state is None:
            return None

        generations = response.generations or []
        choices, finish_reasons, input_tokens, output_tokens = build_response_choices(
            generations
        )

        llm_output = getattr(response, "llm_output", None)
        response_model = _extract_response_model(llm_output)
        if response_model is None:
            response_model = state.request_model
        response_id = _extract_response_id(llm_output)

        response_attributes = {
            **generate_response_attributes(
                model=response_model,
                finish_reasons=finish_reasons or None,
                id=response_id,
                usage_input_tokens=input_tokens,
                usage_output_tokens=output_tokens,
            ),
            **generate_choice_attributes(
                choices=choices, capture_content=self._capture_content
            ),
        }

        state.span.set_attributes(response_attributes)
        state.span_attributes.update(response_attributes)

        duration = max(default_timer() - state.start_time, 0)
        self._record_metrics(
            state,
            duration=duration,
            response_model=response_model,
            usage_input_tokens=input_tokens,
            usage_output_tokens=output_tokens,
            error_type=None,
        )

        self._span_manager.end_span(run_id)
        return None

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> Any:
        state = self._span_manager.get_state(run_id)
        if state is None:
            return None

        handle_span_exception(state.span, error)

        duration = max(default_timer() - state.start_time, 0)
        error_type = type(error).__qualname__
        self._record_metrics(
            state,
            duration=duration,
            response_model=None,
            usage_input_tokens=None,
            usage_output_tokens=None,
            error_type=error_type,
        )

        self._span_manager.end_span(run_id)

    def _record_metrics(
        self,
        state: LangChainSpanState,
        *,
        duration: float,
        response_model: Optional[str],
        usage_input_tokens: Optional[int],
        usage_output_tokens: Optional[int],
        error_type: Optional[str],
    ) -> None:
        if self._instruments is None:
            return

        system_value = state.system_value
        if isinstance(system_value, GenAIAttributes.GenAiSystemValues):
            system_value = system_value.value

        common_attributes: Dict[str, Any] = {
            GenAIAttributes.GEN_AI_OPERATION_NAME: GenAIAttributes.GenAiOperationNameValues.CHAT.value,
        }
        if system_value is not None:
            common_attributes[GenAIAttributes.GEN_AI_SYSTEM] = system_value
        if state.request_model:
            common_attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL] = state.request_model
        if response_model:
            common_attributes[GenAIAttributes.GEN_AI_RESPONSE_MODEL] = response_model
        if error_type:
            common_attributes["error.type"] = error_type

        self._instruments.operation_duration_histogram.record(
            duration,
            attributes=common_attributes,
        )

        if usage_input_tokens is not None:
            input_attributes = {
                **common_attributes,
                GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.INPUT.value,
            }
            self._instruments.token_usage_histogram.record(
                usage_input_tokens,
                attributes=input_attributes,
            )

        if usage_output_tokens is not None:
            completion_attributes = {
                **common_attributes,
                GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.COMPLETION.value,
            }
            self._instruments.token_usage_histogram.record(
                usage_output_tokens,
                attributes=completion_attributes,
            )


def _extract_invocation_params(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    invocation_params = kwargs.get("invocation_params")
    if isinstance(invocation_params, dict):
        params = invocation_params.get("params")
        if isinstance(params, dict):
            return params
        return invocation_params
    return kwargs


def _extract_request_model(
    params: Dict[str, Any], metadata: Optional[Dict[str, Any]]
) -> Optional[str]:
    for key in ("model_name", "model", "model_id"):
        value = params.get(key)
        if isinstance(value, str):
            return value
    if metadata:
        for key in ("model_name", "model", "model_id"):
            value = metadata.get(key)
            if isinstance(value, str):
                return value
    return None


def _extract_response_model(llm_output: Optional[Dict[str, Any]]) -> Optional[str]:
    if isinstance(llm_output, dict):
        for key in ("model_name", "model"):
            value = llm_output.get(key)
            if value is not None:
                return str(value)
    return None


def _extract_response_id(llm_output: Optional[Dict[str, Any]]) -> Optional[str]:
    if isinstance(llm_output, dict):
        response_id = llm_output.get("id")
        if response_id is not None:
            return str(response_id)
    return None


def _get_value(
    params: Dict[str, Any], metadata: Optional[Dict[str, Any]], *keys: str
) -> Optional[Any]:
    for key in keys:
        if key in params and params[key] is not None:
            return params[key]
    if metadata:
        for key in keys:
            if key in metadata and metadata[key] is not None:
                return metadata[key]
    return None


def _generate_available_tools_attributes(invocation_params: Dict[str, Any]) -> Dict[str, Any]:
    tools = invocation_params.get("tools")
    if not isinstance(tools, list):
        return {}

    attributes: Dict[str, Any] = {}
    for tool_index, tool in enumerate(tools):
        if not isinstance(tool, Mapping):
            continue

        tool_type = tool.get("type") or "function"
        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_TYPE.format(
                tool_index=tool_index
            )
        ] = tool_type

        function = tool.get("function")
        if isinstance(function, Mapping):
            name = function.get("name")
            description = function.get("description")
            parameters = function.get("parameters")
        else:
            name = tool.get("name")
            description = tool.get("description")
            parameters = (
                tool.get("parameters")
                or tool.get("input_schema")
                or tool.get("inputSchema")
            )
            if parameters is None and isinstance(tool.get("definition"), Mapping):
                parameters = tool["definition"].get("parameters")

        if name is not None:
            attributes[
                ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_NAME.format(
                    tool_index=tool_index
                )
            ] = name

        if description is not None:
            attributes[
                ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_DESCRIPTION.format(
                    tool_index=tool_index
                )
            ] = description

        if parameters is None:
            continue

        try:
            serialized_parameters = json.dumps(parameters)
        except (TypeError, ValueError):
            serialized_parameters = str(parameters)

        attributes[
            ExtendedGenAIAttributes.GEN_AI_REQUEST_TOOLS_FUNCTION_PARAMETERS.format(
                tool_index=tool_index
            )
        ] = serialized_parameters

    return attributes
