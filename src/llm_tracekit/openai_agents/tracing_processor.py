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


from dataclasses import dataclass, field
from contextvars import Token
from typing import Any, Optional, Dict, List, Tuple, Union, Callable, Type

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

from openai.types.responses import ResponseInputItemParam, ResponseOutputMessage

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
    generate_response_attributes
)

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)


@dataclass
class _TraceState:
    parent_span: Optional[OTELSpan] = None
    parent_context: Optional[Token] = None
    open_spans: Dict[str, Tuple[OTELSpan, Token]] = field(default_factory=dict)
    agents: Dict[str, Agent] = field(default_factory=dict)
    last_agent: Optional[Agent] = None


@dataclass
class ChatHistoryResult:
    prompt_history: List[Message] = field(default_factory=list)
    completion_history: List[Choice] = field(default_factory=list)


class OpenAIAgentsTracingProcessor(TracingProcessor):
    def __init__(self, tracer, capture_content: bool):
        self.disabled = False
        self.tracer = tracer
        self.capture_content = capture_content
        self._span_processors: Dict[Type[Any], Callable[..., Dict[str, Any]]] = {
            AgentSpanData: self._process_agent_span,
            FunctionSpanData: self._process_function_span,
            ResponseSpanData: self._process_response_span,
            GuardrailSpanData: self._process_guardrail_span,
            HandoffSpanData: self._process_handoff_span
        }
        self._trace_states: Dict[str, _TraceState] = {}

    def _get_or_create_state(self, trace_id: str) -> _TraceState:
        if trace_id not in self._trace_states:
            self._trace_states[trace_id] = _TraceState()
        return self._trace_states[trace_id]
        
    def _pop_state(self, trace_id: str) -> Optional[_TraceState]:
        return self._trace_states.pop(trace_id, None)

    def _process_chat_history(self, span_data: ResponseSpanData) -> ChatHistoryResult:
        input_messages: Union[List[ResponseInputItemParam], str, None]  = span_data.input
        history: List[Message] = []
        choices: List[Choice] = []

        if span_data.response is not None:
            if isinstance(span_data.response.instructions, str):
                    history.append(Message(role='system', content=span_data.response.instructions))

        if isinstance(input_messages, list):
            idx = 0
            while idx < len(input_messages):
                msg = input_messages[idx]
                if msg.get('role') == 'user':
                    history.append(Message(role='user', content=str(msg.get('content'))))
                    idx += 1
                    continue

                if msg.get('role') == 'assistant' and msg.get('type') == 'message':
                    content: str = ""
                    msg_content = msg.get('content')
                    if msg_content is not None and isinstance(msg_content, list) and len(msg_content) > 0:
                        content = msg_content[0].get('text', '')
                    history.append(Message(role='assistant', content=content))
                    idx += 1
                    continue
                    
                if msg.get('type') == 'function_call':
                    tool_call_buffer = []
                    
                    # Agents SDK separates multiple tool calls into different messages
                    # This nested loop is used to merge them back into a single message 
                    while idx < len(input_messages) and input_messages[idx].get('type') == 'function_call':
                        tool_call_msg = input_messages[idx]
                        try:
                            tool_call = ToolCall.model_validate({
                            'id': tool_call_msg.get('call_id'),
                            'type': tool_call_msg.get('type'),
                            'function_name': tool_call_msg.get('name'),
                            'function_arguments': tool_call_msg.get('arguments')
                            })
                        except Exception:
                            idx += 1
                            continue
                        tool_call_buffer.append(tool_call)
                        idx += 1
                    assistant_tool_message = Message(role='assistant', content=None, tool_calls=tool_call_buffer)
                    history.append(assistant_tool_message)
                    continue

                if msg.get('type') == 'function_call_output':
                    history.append(Message(
                        role='tool',
                        tool_call_id=str(msg.get('call_id')),
                        content=str(msg.get('output'))
                    ))
                    idx += 1
                    continue
                idx += 1

        elif isinstance(input_messages, str):
            history.append(Message(role='user', content=input_messages))

        if span_data.response is not None:
            response = span_data.response
            response_content: Optional[str] = None
            response_tool_calls: Optional[List[ToolCall]] = None
            response_role = 'assistant'

            if response.output is not None and isinstance(response.output, list) and len(response.output) > 0:
                for output_item in response.output:
                    if isinstance(output_item, ResponseOutputMessage):
                        if hasattr(output_item, 'role'):
                            response_role = output_item.role
                        if hasattr(output_item, 'content') and isinstance(output_item.content, list):
                            for content_part in output_item.content:
                                if hasattr(content_part, 'text') and isinstance(content_part.text, str) and content_part.text:
                                    text_part = content_part.text
                                    if response_content is None:
                                        response_content = text_part
                                    else:
                                        response_content = f"{response_content} {text_part}"

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
                finish_reason="stop",
                role=response_role,
                content=response_content,
                tool_calls=response_tool_calls
            )
            choices.append(choice)
        return ChatHistoryResult(prompt_history=history, completion_history=choices)

    def _process_agent_span(self, span_data: AgentSpanData) -> Dict[str, Any]:
        attributes: Dict[str, Any] = {
            "type": span_data.type,
            "agent_name": span_data.name,
            "handoffs": span_data.handoffs,
            "output_type": span_data.output_type
        }
        if span_data.tools is not None:
            attributes["tools"] = span_data.tools
        return attributes

    def _process_function_span(self, span_data: FunctionSpanData) -> Dict[str, Any]:
        attributes: Dict[str, Any] = {
            "type": span_data.type,
            "name": span_data.name
        }
        if span_data.input is not None and self.capture_content:
            attributes["input"] = span_data.input
        if span_data.output is not None and self.capture_content:
            attributes["output"] = span_data.output
        if span_data.mcp_data is not None and self.capture_content: 
            attributes["mcp_data"] = span_data.mcp_data
        return attributes

    def _process_response_span(
            self, span_data: ResponseSpanData, state: _TraceState, parent_id: str
    ) -> Dict[str, Any]:
        chat_result = self._process_chat_history(span_data)
        active_agent = state.agents.get(parent_id)
        if active_agent is None:
            active_agent = Agent(name="unknown")
        else:
            state.last_agent = active_agent

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
        
        attributes: Dict[str, Any] = {
            **generate_base_attributes(
                operation=GenAIAttributes.GenAiOperationNameValues.CHAT,
                system=GenAIAttributes.GenAiSystemValues.OPENAI
            ),
            **generate_message_attributes(
                messages=chat_result.prompt_history,
                capture_content=self.capture_content
            ),
            **generate_choice_attributes(
                choices=chat_result.completion_history,
                capture_content=self.capture_content
            ),
            **generate_request_attributes(
                model=response_model,
                top_p=top_p,
                temperature=temperature
            ),
            **generate_response_attributes(
                usage_input_tokens=usage_input_tokens,
                usage_output_tokens=usage_output_tokens,
                id=response_id,
                model=response_model
            ),
            **active_agent.generate_attributes()
        }
        return attributes
    
    def _process_guardrail_span(self, span_data: GuardrailSpanData) -> Dict[str, Any]:
        attributes: Dict[str, Any] = {
            "type": span_data.type,
            "name": span_data.name,
            "triggered": span_data.triggered
        }
        return attributes

    def _process_handoff_span(self, span_data: HandoffSpanData) -> Dict[str, Any]:
        attributes: Dict[str, Any] = {
            "type": span_data.type,
            "from_agent": span_data.from_agent,
        }
        if span_data.to_agent is not None:
            attributes["to_agent"] = span_data.to_agent
        return attributes

    def on_trace_start(self, trace: Trace) -> None:
        if self.disabled:
            return
        state = self._get_or_create_state(trace.trace_id)

        state.parent_span = self.tracer.start_span(
            name="openai.agent",
            kind=SpanKind.CLIENT,
        )
        state.parent_context = attach(set_value(_SPAN_KEY, state.parent_span))

    def on_trace_end(self, trace: Trace) -> None:
        if self.disabled:
            return
        state = self._pop_state(trace.trace_id)
        if not state:
            return
        
        if state.parent_context is not None:
            detach(state.parent_context)
        if state.parent_span is not None:
            state.parent_span.end()

        for _, (span, context_token) in reversed(list(state.open_spans.items())):
            detach(context_token)
            span.end()

    def on_span_start(self, span: Span[Any]) -> None:
        """Called when a span is started.

         Args:
             span: The span that started.
         """
        if self.disabled:
            return
        trace_id = span.trace_id 
        state = self._get_or_create_state(trace_id)

        initial_attributes = {}
        processor = self._span_processors.get(type(span.span_data))
        if processor is not None:
            if isinstance(span.span_data, ResponseSpanData):
                initial_attributes = generate_base_attributes(
                    operation=GenAIAttributes.GenAiOperationNameValues.CHAT,
                    system=GenAIAttributes.GenAiSystemValues.OPENAI
                )
            else:
                initial_attributes = processor(span.span_data)

        if isinstance(span.span_data, AgentSpanData):
            new_span_name = f"Agent - {span.span_data.name}"
        elif isinstance(span.span_data, FunctionSpanData):
            new_span_name = f"Tool - {span.span_data.name}"
        elif isinstance(span.span_data, GuardrailSpanData):
            new_span_name = f"Guardrail - {span.span_data.name}"
        elif isinstance(span.span_data, ResponseSpanData):
            new_span_name = "Response"
        elif isinstance(span.span_data, HandoffSpanData):
            new_span_name = "Handoff"
        else:
            new_span_name = type(span.span_data).__name__

        new_span = self.tracer.start_span(
            name=new_span_name,
            kind=SpanKind.INTERNAL,
            attributes=initial_attributes
        )
        context_token = attach(set_value(_SPAN_KEY, new_span))
        state.open_spans[span.span_id] = (new_span, context_token)
        if isinstance(span.span_data, AgentSpanData):
            state.agents[span.span_id] = Agent(name=span.span_data.name)

    def on_span_end(self, span: Span[Any]) -> None:
        """Called when a span is finished. Should not block or raise exceptions.

        Args:
            span: The span that finished.
        """
        if self.disabled:
            return
        trace_id = span.trace_id
        state = self._get_or_create_state(trace_id)

        if span.span_id not in state.open_spans:
            return

        open_span, context_token = state.open_spans.pop(span.span_id)

        try:
            processor = self._span_processors.get(type(span.span_data))
            if processor is not None:
                if isinstance(span.span_data, ResponseSpanData):
                    attributes = processor(span.span_data, state, span.parent_id)
                else:
                    attributes = processor(span.span_data)
                open_span.set_attributes(attributes)

            if span.error is not None:
                open_span.set_status(
                    status=Status(
                        status_code=StatusCode.ERROR, description=span.error["message"]
                    )
                )
        except Exception:
            pass
        finally:
            detach(context_token)
            open_span.end()


    def shutdown(self) -> None:
        """Called when the application stops."""
        for trace_id, state in list(self._trace_states.items()):
            for _, (span, context_token) in reversed(list(state.open_spans.items())):
                detach(context_token)
                span.end()
            if state.parent_span:
                state.parent_span.end()
        self._trace_states.clear()

    def force_flush(self) -> None:
        """Forces an immediate flush of all queued spans/traces."""
        pass