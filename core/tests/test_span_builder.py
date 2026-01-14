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

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

from llm_tracekit.core import (
    ToolCall,
    Message,
    Choice,
    Agent,
    generate_base_attributes,
    generate_request_attributes,
    generate_message_attributes,
    generate_response_attributes,
    generate_choice_attributes,
)


class TestGenerateBaseAttributes:
    def test_with_string_system(self):
        """Test generate_base_attributes with string system."""
        result = generate_base_attributes(system="openai")
        
        assert result[GenAIAttributes.GEN_AI_SYSTEM] == "openai"
        assert result[GenAIAttributes.GEN_AI_OPERATION_NAME] == "chat"

    def test_with_enum_system(self):
        """Test generate_base_attributes with enum system."""
        result = generate_base_attributes(
            system=GenAIAttributes.GenAiSystemValues.OPENAI
        )
        
        assert result[GenAIAttributes.GEN_AI_SYSTEM] == "openai"

    def test_with_custom_operation(self):
        """Test generate_base_attributes with custom operation."""
        result = generate_base_attributes(
            system="openai",
            operation=GenAIAttributes.GenAiOperationNameValues.TEXT_COMPLETION,
        )
        
        assert result[GenAIAttributes.GEN_AI_OPERATION_NAME] == "text_completion"


class TestGenerateRequestAttributes:
    def test_with_all_params(self):
        """Test generate_request_attributes with all parameters."""
        result = generate_request_attributes(
            model="gpt-4o",
            temperature=0.7,
            top_p=0.9,
            top_k=50,
            max_tokens=1000,
            presence_penalty=0.5,
            frequency_penalty=0.3,
        )
        
        assert result[GenAIAttributes.GEN_AI_REQUEST_MODEL] == "gpt-4o"
        assert result[GenAIAttributes.GEN_AI_REQUEST_TEMPERATURE] == 0.7
        assert result[GenAIAttributes.GEN_AI_REQUEST_TOP_P] == 0.9
        assert result[GenAIAttributes.GEN_AI_REQUEST_TOP_K] == 50
        assert result[GenAIAttributes.GEN_AI_REQUEST_MAX_TOKENS] == 1000
        assert result[GenAIAttributes.GEN_AI_REQUEST_PRESENCE_PENALTY] == 0.5
        assert result[GenAIAttributes.GEN_AI_REQUEST_FREQUENCY_PENALTY] == 0.3

    def test_with_minimal_params(self):
        """Test generate_request_attributes with only model."""
        result = generate_request_attributes(model="gpt-4o")
        
        assert result[GenAIAttributes.GEN_AI_REQUEST_MODEL] == "gpt-4o"
        # None values should be removed
        assert GenAIAttributes.GEN_AI_REQUEST_TEMPERATURE not in result
        assert GenAIAttributes.GEN_AI_REQUEST_TOP_P not in result

    def test_with_no_params(self):
        """Test generate_request_attributes with no parameters."""
        result = generate_request_attributes()
        
        assert result == {}


class TestGenerateMessageAttributes:
    def test_simple_message(self):
        """Test generate_message_attributes with a simple message."""
        messages = [Message(role="user", content="Hello")]
        result = generate_message_attributes(messages=messages, capture_content=True)
        
        assert result["gen_ai.prompt.0.role"] == "user"
        assert result["gen_ai.prompt.0.content"] == "Hello"

    def test_message_without_content_capture(self):
        """Test that content is not captured when capture_content is False."""
        messages = [Message(role="user", content="Hello")]
        result = generate_message_attributes(messages=messages, capture_content=False)
        
        assert result["gen_ai.prompt.0.role"] == "user"
        assert "gen_ai.prompt.0.content" not in result

    def test_multiple_messages(self):
        """Test generate_message_attributes with multiple messages."""
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
            Message(role="user", content="How are you?"),
        ]
        result = generate_message_attributes(messages=messages, capture_content=True)
        
        assert result["gen_ai.prompt.0.role"] == "user"
        assert result["gen_ai.prompt.0.content"] == "Hello"
        assert result["gen_ai.prompt.1.role"] == "assistant"
        assert result["gen_ai.prompt.1.content"] == "Hi there!"
        assert result["gen_ai.prompt.2.role"] == "user"
        assert result["gen_ai.prompt.2.content"] == "How are you?"

    def test_message_with_tool_calls(self):
        """Test generate_message_attributes with tool calls."""
        tool_call = ToolCall(
            id="call_123",
            type="function",
            function_name="get_weather",
            function_arguments='{"location": "London"}',
        )
        messages = [Message(role="assistant", tool_calls=[tool_call])]
        result = generate_message_attributes(messages=messages, capture_content=True)
        
        assert result["gen_ai.prompt.0.role"] == "assistant"
        assert result["gen_ai.prompt.0.tool_calls.0.id"] == "call_123"
        assert result["gen_ai.prompt.0.tool_calls.0.type"] == "function"
        assert result["gen_ai.prompt.0.tool_calls.0.function.name"] == "get_weather"
        assert result["gen_ai.prompt.0.tool_calls.0.function.arguments"] == '{"location": "London"}'


class TestGenerateResponseAttributes:
    def test_with_all_params(self):
        """Test generate_response_attributes with all parameters."""
        result = generate_response_attributes(
            model="gpt-4o-2024-01-01",
            finish_reasons=["stop"],
            id="chatcmpl-123",
            usage_input_tokens=100,
            usage_output_tokens=50,
        )
        
        assert result[GenAIAttributes.GEN_AI_RESPONSE_MODEL] == "gpt-4o-2024-01-01"
        assert result[GenAIAttributes.GEN_AI_RESPONSE_FINISH_REASONS] == ["stop"]
        assert result[GenAIAttributes.GEN_AI_RESPONSE_ID] == "chatcmpl-123"
        assert result[GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS] == 100
        assert result[GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS] == 50

    def test_with_minimal_params(self):
        """Test generate_response_attributes with minimal parameters."""
        result = generate_response_attributes(model="gpt-4o")
        
        assert result[GenAIAttributes.GEN_AI_RESPONSE_MODEL] == "gpt-4o"
        assert GenAIAttributes.GEN_AI_RESPONSE_ID not in result


class TestGenerateChoiceAttributes:
    def test_simple_choice(self):
        """Test generate_choice_attributes with a simple choice."""
        choices = [Choice(finish_reason="stop", role="assistant", content="Hello!")]
        result = generate_choice_attributes(choices=choices, capture_content=True)
        
        assert result["gen_ai.completion.0.finish_reason"] == "stop"
        assert result["gen_ai.completion.0.role"] == "assistant"
        assert result["gen_ai.completion.0.content"] == "Hello!"

    def test_choice_without_content_capture(self):
        """Test that content is not captured when capture_content is False."""
        choices = [Choice(finish_reason="stop", role="assistant", content="Hello!")]
        result = generate_choice_attributes(choices=choices, capture_content=False)
        
        assert result["gen_ai.completion.0.finish_reason"] == "stop"
        assert result["gen_ai.completion.0.role"] == "assistant"
        assert "gen_ai.completion.0.content" not in result

    def test_choice_with_tool_calls(self):
        """Test generate_choice_attributes with tool calls."""
        tool_call = ToolCall(
            id="call_456",
            type="function",
            function_name="search",
            function_arguments='{"query": "weather"}',
        )
        choices = [Choice(finish_reason="tool_calls", role="assistant", tool_calls=[tool_call])]
        result = generate_choice_attributes(choices=choices, capture_content=True)
        
        assert result["gen_ai.completion.0.finish_reason"] == "tool_calls"
        assert result["gen_ai.completion.0.tool_calls.0.id"] == "call_456"
        assert result["gen_ai.completion.0.tool_calls.0.type"] == "function"
        assert result["gen_ai.completion.0.tool_calls.0.function.name"] == "search"
        assert result["gen_ai.completion.0.tool_calls.0.function.arguments"] == '{"query": "weather"}'


class TestAgent:
    def test_agent_attributes(self):
        """Test Agent.generate_attributes method."""
        agent = Agent(id="agent-1", name="Assistant", description="A helpful assistant")
        result = agent.generate_attributes()
        
        assert result[GenAIAttributes.GEN_AI_AGENT_ID] == "agent-1"
        assert result[GenAIAttributes.GEN_AI_AGENT_NAME] == "Assistant"
        assert result[GenAIAttributes.GEN_AI_AGENT_DESCRIPTION] == "A helpful assistant"

    def test_agent_with_minimal_params(self):
        """Test Agent with minimal parameters."""
        agent = Agent(name="Assistant")
        result = agent.generate_attributes()
        
        assert result[GenAIAttributes.GEN_AI_AGENT_NAME] == "Assistant"
        assert GenAIAttributes.GEN_AI_AGENT_ID not in result
        assert GenAIAttributes.GEN_AI_AGENT_DESCRIPTION not in result
