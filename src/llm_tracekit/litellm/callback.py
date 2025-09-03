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


from litellm.proxy._types import SpanAttributes
from litellm.integrations.opentelemetry import OpenTelemetry, OpenTelemetryConfig
from litellm.types.utils import (
    Function,
    StandardLoggingPayload,
)

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

from typing import List, Dict, Any, Optional
from opentelemetry.trace import Span

class LitellmCallback(OpenTelemetry):
    def __init__(self, capture_content: bool, config: Optional[OpenTelemetryConfig]):
        super().__init__(config=config)
        self.capture_content = capture_content

    def set_attributes(  # noqa: PLR0915
        self, span: Span, kwargs, response_obj: Optional[Any]
    ):
        try:
            optional_params = kwargs.get("optional_params", {})
            litellm_params = kwargs.get("litellm_params", {}) or {}
            standard_logging_payload: Optional[StandardLoggingPayload] = kwargs.get(
                "standard_logging_object"
            )
            if standard_logging_payload is None:
                raise ValueError("standard_logging_object not found in kwargs")

            if kwargs.get("model"):
                self.safe_set_attribute(
                    span=span,
                    key=SpanAttributes.LLM_REQUEST_MODEL.value,
                    value=kwargs.get("model"),
                )

            self.safe_set_attribute(
                span=span,
                key=SpanAttributes.LLM_SYSTEM.value,
                value=litellm_params.get("custom_llm_provider", "Unknown"),
            )

            self.safe_set_attribute(
                span=span,
                key=GenAIAttributes.GEN_AI_OPERATION_NAME,
                value=GenAIAttributes.GenAiOperationNameValues.CHAT.value,
            )

            if optional_params.get("max_tokens"):
                self.safe_set_attribute(
                    span=span,
                    key=SpanAttributes.LLM_REQUEST_MAX_TOKENS.value,
                    value=optional_params.get("max_tokens"),
                )

            if optional_params.get("temperature"):
                self.safe_set_attribute(
                    span=span,
                    key=SpanAttributes.LLM_REQUEST_TEMPERATURE.value,
                    value=optional_params.get("temperature"),
                )

            if optional_params.get("top_p"):
                self.safe_set_attribute(
                    span=span,
                    key=SpanAttributes.LLM_REQUEST_TOP_P.value,
                    value=optional_params.get("top_p"),
                )

            if response_obj and response_obj.get("id"):
                self.safe_set_attribute(
                    span=span, key="gen_ai.response.id", value=response_obj.get("id")
                )

            if response_obj and response_obj.get("model"):
                self.safe_set_attribute(
                    span=span,
                    key=SpanAttributes.LLM_RESPONSE_MODEL.value,
                    value=response_obj.get("model"),
                )

            usage = response_obj and response_obj.get("usage")
            if usage:
                self.safe_set_attribute(
                    span=span,
                    key=GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS,
                    value=usage.get("completion_tokens"),
                )

                self.safe_set_attribute(
                    span=span,
                    key=GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS,
                    value=usage.get("prompt_tokens"),
                )

            if kwargs.get("messages"):
                for idx, prompt in enumerate(kwargs.get("messages")):
                    if prompt.get("role"):
                        self.safe_set_attribute(
                            span=span,
                            key=f"{SpanAttributes.LLM_PROMPTS.value}.{idx}.role",
                            value=prompt.get("role"),
                        )

                    if prompt.get("content") and self.capture_content:
                        if not isinstance(prompt.get("content"), str):
                            prompt["content"] = str(prompt.get("content"))
                        self.safe_set_attribute(
                            span=span,
                            key=f"{SpanAttributes.LLM_PROMPTS.value}.{idx}.content",
                            value=prompt.get("content"),
                        )

                    if prompt.get("tool_calls"):
                        for tool_idx, tool_call in enumerate(prompt.get("tool_calls")):
                            self.safe_set_attribute(
                                span=span,
                                key=f"{SpanAttributes.LLM_PROMPTS.value}.{idx}.tool_calls.{tool_idx}.id",
                                value=tool_call.get("id"),
                            )
                            self.safe_set_attribute(
                                span=span,
                                key=f"{SpanAttributes.LLM_PROMPTS.value}.{idx}.tool_calls.{tool_idx}.type",
                                value=tool_call.get("type"),
                            )
                            self.safe_set_attribute(
                                span=span,
                                key=f"{SpanAttributes.LLM_PROMPTS.value}.{idx}.tool_calls.{tool_idx}.function.name",
                                value=tool_call.get("function").get("name"),
                            )
                            if self.capture_content:
                                self.safe_set_attribute(
                                    span=span,
                                    key=f"{SpanAttributes.LLM_PROMPTS.value}.{idx}.tool_calls.{tool_idx}.function.arguments",
                                    value=tool_call.get("function").get("arguments"),
                                )
                    
                    if prompt.get("tool_call_id"):
                        self.safe_set_attribute(
                            span=span,
                            key=f"{SpanAttributes.LLM_PROMPTS.value}.{idx}.tool_call_id",
                            value=prompt.get("tool_call_id"),
                        )
                        
            if response_obj is not None:
                if response_obj.get("choices"):
                    for choice_idx, choice in enumerate(response_obj.get("choices")):
                        if choice.get("finish_reason"):
                            self.safe_set_attribute(
                                span=span,
                                key=f"{SpanAttributes.LLM_COMPLETIONS.value}.{choice_idx}.finish_reason",
                                value=choice.get("finish_reason"),
                            )
                        if choice.get("message"):
                            if choice.get("message").get("role"):
                                self.safe_set_attribute(
                                    span=span,
                                    key=f"{SpanAttributes.LLM_COMPLETIONS.value}.{choice_idx}.role",
                                    value=choice.get("message").get("role"),
                                )
                            if choice.get("message").get("content") and self.capture_content:
                                if not isinstance(
                                    choice.get("message").get("content"), str
                                ):
                                    choice["message"]["content"] = str(
                                        choice.get("message").get("content")
                                    )
                                self.safe_set_attribute(
                                    span=span,
                                    key=f"{SpanAttributes.LLM_COMPLETIONS.value}.{choice_idx}.content",
                                    value=choice.get("message").get("content"),
                                )

                            message = choice.get("message")
                            tool_calls = message.get("tool_calls")
                            if tool_calls:
                                kv_pairs = self.__class__._tool_calls_kv_pair(tool_calls, choice_idx, self.capture_content)  # type: ignore
                                for key, value in kv_pairs.items():
                                    self.safe_set_attribute(
                                        span=span,
                                        key=key,
                                        value=value,
                                    )
        except Exception:
            pass

    @staticmethod
    def _tool_calls_kv_pair(
        tool_calls: List[dict],
        choice_idx: int,
        capture_content: bool
    ) -> Dict[str, Any]:
        kv_pairs: Dict[str, Any] = {}
        for tool_idx, tool_call in enumerate(tool_calls):
            _function = tool_call.get("function")
            if not _function:
                continue

            keys = Function.__annotations__.keys()
            for key in keys:
                _value = _function.get(key)
                if _value:
                    if key == "arguments" and not capture_content:
                        continue
                    kv_pairs[
                        f"{SpanAttributes.LLM_COMPLETIONS.value}.{choice_idx}.tool_calls.{tool_idx}.function.{key}"
                    ] = _value

            tool_call_id = tool_call.get("id")
            tool_call_type = tool_call.get("type")

            if tool_call_id:
                kv_pairs[
                    f"{SpanAttributes.LLM_COMPLETIONS.value}.{choice_idx}.tool_calls.{tool_idx}.id"
                ] = tool_call_id
            
            if tool_call_type:
                kv_pairs[
                    f"{SpanAttributes.LLM_COMPLETIONS.value}.{choice_idx}.tool_calls.{tool_idx}.type"
                ] = tool_call_type

        return kv_pairs