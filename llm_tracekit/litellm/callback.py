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


from litellm.integrations.opentelemetry import OpenTelemetry, OpenTelemetryConfig
from litellm.types.utils import (
    StandardLoggingPayload,
)

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

from typing import List, Dict, Any, Optional
from opentelemetry.trace import Span

from llm_tracekit.span_builder import (
    Choice,
    Message,
    ToolCall,
    generate_base_attributes,
    generate_choice_attributes,
    generate_message_attributes,
    generate_request_attributes,
    generate_response_attributes
)

class LitellmCallback(OpenTelemetry):
    def __init__(self, capture_content: bool, config: Optional[OpenTelemetryConfig]):
        super().__init__(config=config)
        self.capture_content = capture_content

    def parse_messages(self, raw_messages: List[Dict[str, Any]]) -> List[Message]:
        messages: List[Message] = []
        for prompt in raw_messages:
            content = prompt.get("content")
            if content is not None and not isinstance(content, str):
                content = str(content)

            tool_calls_data = prompt.get("tool_calls")
            tool_calls_list = None
            
            if tool_calls_data:
                tool_calls_list = [
                    ToolCall(
                        id=tool_call.get("id"),
                        type=tool_call.get("type"),
                        function_name=tool_call.get("function", {}).get("name"),
                        function_arguments=tool_call.get("function", {}).get("arguments"),
                    )
                    for tool_call in tool_calls_data
                ]

            message = Message(
                role=prompt.get("role"),
                content=content,
                tool_call_id=prompt.get("tool_call_id"),
                tool_calls=tool_calls_list,
            )
            messages.append(message)
        return messages
    
    def parse_choices(self, raw_choices: List[Dict[str, Any]]) -> List[Choice]:
        choices: List[Choice] = []
        for choice_dict in raw_choices:
            choice_message = choice_dict.get("message", {}) or {}
            tool_calls_list = None

            tool_calls = choice_message.get("tool_calls")

            if tool_calls:
                tool_calls_list = [
                    ToolCall(
                        id=tool_call.get("id"),
                        type=tool_call.get("type"),
                        function_name=tool_call.get("function", {}).get("name"),
                        function_arguments=tool_call.get("function", {}).get("arguments"),
                    )
                    for tool_call in tool_calls
                ]

            content = choice_message.get("content")
            if content is not None and not isinstance(content, str):
                content = str(content)

            choice = Choice(
                finish_reason=choice_dict.get("finish_reason"),
                role=choice_message.get("role"),
                content=content,
                tool_calls=tool_calls_list,
            )
            choices.append(choice)
        return choices

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

            messages: List[Message] = []
            choices: List[Choice] = []

            response_attributes: Dict[str, Any] = {}

            if "messages" in kwargs:
                messages = self.parse_messages(kwargs.get("messages"))

            if response_obj is not None:
                response_attributes = generate_response_attributes(
                    model=response_obj.get("model"),
                    id=response_obj.get("id"),
                    usage_input_tokens=response_obj.get("usage").get("prompt_tokens"),
                    usage_output_tokens=response_obj.get("usage").get("completion_tokens")
                )
                if "choices" in response_obj:
                    raw_choices = response_obj.get("choices")
                    choices = self.parse_choices(raw_choices)

            attributes = {
                **generate_base_attributes(
                    system=litellm_params.get("custom_llm_provider", "Unknown"),
                    operation=GenAIAttributes.GenAiOperationNameValues.CHAT
                ),
                **generate_request_attributes(
                    model=kwargs.get("model"),
                    temperature=optional_params.get("temperature"),
                    top_p=optional_params.get("top_p"),
                    max_tokens=optional_params.get("max_tokens")
                ),
                **generate_message_attributes(
                    messages=messages,
                    capture_content=self.capture_content
                ),
                **generate_choice_attributes(
                    choices=choices,
                    capture_content=self.capture_content
                ),
                **response_attributes
            }

            for key, value in attributes.items():
                if value is not None:
                    self.safe_set_attribute(
                        span=span,
                        key=key,
                        value=value,
                    )
        
        except Exception:
            pass