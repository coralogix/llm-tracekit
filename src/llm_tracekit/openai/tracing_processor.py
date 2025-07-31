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

import json
from dataclasses import dataclass, field
from contextvars import Token
from typing import Any, Optional, Dict, List, Tuple

from agents import (
    AgentSpanData,
    FunctionSpanData,
    GuardrailSpanData,
    HandoffSpanData,
    Span,
    Trace,
    TracingProcessor
)
from agents.tracing import ResponseSpanData

from opentelemetry.context import attach, detach, set_value
from opentelemetry.trace import Span as OTELSpan
from opentelemetry.trace import (
    Status,
    StatusCode,
    SpanKind,
)
from opentelemetry.trace.propagation import _SPAN_KEY

from llm_tracekit.span_builder import (
    Choice,
    Message,
    ToolCall,
    Agent,
    generate_base_attributes,
    generate_choice_attributes,
    generate_message_attributes,
    generate_request_attributes,
    generate_response_attributes,
    generate_agent_attributes,
)

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)


@dataclass
class ChatHistoryResult:
    prompt_history: List[Message] = field(default_factory=list)
    completion_history: List[Choice] = field(default_factory=list)


class OpenAIAgentsTracingProcessor(TracingProcessor):
    def __init__(self, tracer):
        self.tracer = tracer
        self._request_model: Optional[str] = None
        self._parent_span: Optional[OTELSpan] = None
        self._parent_context: Optional[Token] = None
        self._open_spans: Dict[str, Tuple[OTELSpan, Token]] = {}
        self._span_processors = {
            AgentSpanData: self._process_agent_span,
            FunctionSpanData: self._process_function_span,
            ResponseSpanData: self._process_response_span,
            GuardrailSpanData: self._process_guardrail_span,
            HandoffSpanData: self._process_handoff_span
        }
        self._unassigned_agents: List[Agent] = []
        self._last_agent: Optional[Agent] = None

    def _process_chat_history(self, span_data: ResponseSpanData) -> ChatHistoryResult:
        input_messages: Any = span_data.input
        history: List[Message] = []
        choices: List[Choice] = []
        
        idx = 0
        while idx < len(input_messages):
            msg = input_messages[idx]

            if msg.get('role') == 'user':
                history.append(Message(role='user', content=msg.get('content')))
                idx += 1
                continue

            if msg.get('role') == 'assistant' and msg.get('type') == 'message':
                content: str = ""
                msg_content = msg.get('content')
                if msg_content is not None and isinstance(msg_content, list) and len(msg_content) > 0:
                    text_content = msg_content[0].get('text', '')
                    try:
                        parsed_json = json.loads(text_content)
                        content = parsed_json.get('response', text_content)
                    except (json.JSONDecodeError, TypeError):
                        content = text_content
                history.append(Message(role='assistant', content=content))
                idx += 1
                continue
                
            if msg.get('type') == 'function_call':
                tool_call_buffer = []
                
                while idx < len(input_messages) and input_messages[idx].get('type') == 'function_call':
                    tool_call_msg = input_messages[idx]
                    tool_call = ToolCall(
                        id=tool_call_msg.get('call_id'),
                        type=tool_call_msg.get('type'),
                        function_name=tool_call_msg.get('name'),
                        function_arguments=tool_call_msg.get('arguments')
                    )
                    tool_call_buffer.append(tool_call)
                    idx += 1
                assistant_tool_message = Message(role='assistant', content=None, tool_calls=tool_call_buffer)
                history.append(assistant_tool_message)
                continue

            if msg.get('type') == 'function_call_output':
                history.append(Message(
                    role='tool',
                    tool_call_id=msg.get('call_id'),
                    content=msg.get('output')
                ))
                idx += 1
                continue
            idx += 1
        
        if span_data.response is not None:
            response = span_data.response
            response_content: Optional[str] = None
            response_tool_calls: Optional[List[ToolCall]] = None
            response_role = 'assistant'
            
            if isinstance(response.instructions, str):
                history.insert(0, Message(role='system', content=response.instructions))

            if response.output is not None and isinstance(response.output, list) and len(response.output) > 0:
                message_part = response.output[0]
                if hasattr(message_part, 'role'):
                    response_role = message_part.role
                
                if (hasattr(message_part, 'content') and 
                    isinstance(message_part.content, list) and 
                    len(message_part.content) > 0 and
                    hasattr(message_part.content[0], 'text')):
                        response_content = message_part.content[0].text

                current_tool_calls = []
                for part in response.output:
                    if hasattr(part, "type") and part.type == "function_call":
                        tool_call = ToolCall(
                            id=part.call_id,
                            type=part.type,
                            function_name=part.name,
                            function_arguments=part.arguments
                        )
                        current_tool_calls.append(tool_call)
                
                if current_tool_calls:
                    response_tool_calls = current_tool_calls

            choice = Choice(
                finish_reason=response.status,
                role=response_role,
                content=response_content,
                tool_calls=response_tool_calls
            )
            choices.append(choice)
        return ChatHistoryResult(prompt_history=history, completion_history=choices)

    def _process_agent_span(self, span_data: AgentSpanData) -> Dict[str, Any]:
        attributes = {
            "type": span_data.type,
            "agent_name": span_data.name,
            "handoffs": span_data.handoffs,
            "tools": span_data.tools,
            "output_type": span_data.output_type
        }
        return attributes

    def _process_function_span(self, span_data: FunctionSpanData) -> Dict[str, Any]:
        attributes = {
            "type": span_data.type,
            "name": span_data.name,
            "input": span_data.input,
            "output": span_data.output
        }
        if span_data.mcp_data is not None: 
            attributes["mcp_data"] = span_data.mcp_data
        return attributes

    def _process_response_span(self, span_data: ResponseSpanData) -> Dict[str, Any]:
        if self._request_model is None and span_data.response is not None:
            self._request_model = span_data.response.model
        
        chat_result = self._process_chat_history(span_data)

        active_agent = self._unassigned_agents.pop(0) if self._unassigned_agents else self._last_agent
        if active_agent is None:
            active_agent = Agent(name="unknown")
        else:
            self._last_agent = active_agent

        top_p: Optional[float] = None
        temperature: Optional[float] = None
        response_model: Optional[str] = None
        usage_input_tokens: Optional[int] = None
        usage_output_tokens: Optional[int] = None

        if span_data.response is not None:
            top_p = span_data.response.top_p
            temperature = span_data.response.temperature
            response_id = span_data.response.id
            response_model = span_data.response.model
            if span_data.response.usage is not None:
                usage_input_tokens = span_data.response.usage.input_tokens
                usage_output_tokens = span_data.response.usage.output_tokens
        
        attributes = {
            **generate_base_attributes(
                operation=GenAIAttributes.GenAiOperationNameValues.CHAT,
                system=GenAIAttributes.GenAiSystemValues.OPENAI
            ),
            **generate_message_attributes(
                messages=chat_result.prompt_history,
                capture_content=True
            ),
            **generate_choice_attributes(
                choices=chat_result.completion_history,
                capture_content=True
            ),
            **generate_request_attributes(
                top_p=top_p,
                temperature=temperature,
                model=self._request_model
            ),
            **generate_response_attributes(
                usage_input_tokens=usage_input_tokens,
                usage_output_tokens=usage_output_tokens,
                id=response_id,
                model=response_model
            ),
            **generate_agent_attributes(
                agent=active_agent
            )
        }
        return attributes
    
    def _process_guardrail_span(self, span_data: GuardrailSpanData) -> Dict[str, Any]:
        attributes = {
            "type": span_data.type,
            "name": span_data.name,
            "triggered": span_data.triggered
        }
        return attributes

    def _process_handoff_span(self, span_data: HandoffSpanData) -> Dict[str, Any]:
        attributes = {
            "type": span_data.type,
            "from_agent": span_data.from_agent,
            "to_agent": span_data.to_agent
        }
        return attributes

    def on_trace_start(self, trace: Trace) -> None:
        self._parent_span = self.tracer.start_span(
            name="openai.agent",
            kind=SpanKind.CLIENT,
        )
        self._parent_context = attach(set_value(_SPAN_KEY, self._parent_span))
        
    def on_trace_end(self, trace: Trace) -> None:
        if self._parent_context is not None:
            detach(self._parent_context)
        if self._parent_span is not None:
            self._parent_span.end()
        
        self._parent_span = None
        self._parent_context = None
        self._request_model = None
        self._open_spans.clear()
        self._unassigned_agents.clear()
        self._last_agent = None

    def on_span_start(self, span: Span[Any]) -> None:
        if isinstance(span.span_data, AgentSpanData):
            self._unassigned_agents.append(Agent(
                name=span.span_data.name
            ))
        new_span = self.tracer.start_span(
            name=type(span.span_data).__name__,
            kind=SpanKind.CLIENT,
        )
        context_token = attach(set_value(_SPAN_KEY, new_span))
        self._open_spans[span.span_id] = (new_span, context_token)

    def on_span_end(self, span: Span[Any]) -> None:
        """Called when a span is finished. Should not block or raise exceptions.

        Args:
            span: The span that finished.
        """
        if span.span_id not in self._open_spans:
            return

        open_span, context_token = self._open_spans.pop(span.span_id)

        try:
            processor = self._span_processors.get(type(span.span_data))
            if processor is not None:
                attributes = processor(span.span_data)
                open_span.set_attributes(attributes)

            if span.error is not None:
                open_span.set_status(
                    status=Status(
                        status_code=StatusCode.ERROR, description=span.error["message"]
                    )
                )
        except Exception as e:
            open_span.set_status(
                Status(StatusCode.ERROR, description=f"Trace processing error: {e}")
            )
        finally:
            detach(context_token)
            open_span.end()


    def shutdown(self) -> None:
        """Called when the application stops."""
        for _, (span, context_token) in self._open_spans.items():
            detach(context_token)
            span.end()
        self._open_spans.clear()

    def force_flush(self) -> None:
        """Forces an immediate flush of all queued spans/traces."""
        pass

class OpenAIAgentsTracingProcessorUninstrumented(TracingProcessor):
    def on_trace_start(self, trace: Trace) -> None:
        pass

    def on_trace_end(self, trace: Trace) -> None:
        pass

    def on_span_start(self, span: Span[Any]) -> None:
        pass

    def on_span_end(self, span: Span[Any]) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def force_flush(self) -> None:
        pass