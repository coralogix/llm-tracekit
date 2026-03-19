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

"""Unit tests for Strands patch module."""

from llm_tracekit.strands.patch import (
    _build_system_prompt_text,
    _extract_text_from_content_blocks,
    _extract_tool_calls_from_content_blocks,
    _extract_user_from_model,
    _is_model_invoke_span,
    _map_role,
    _map_stop_reason,
    _parse_strands_messages,
    _parse_strands_response,
    _process_tool_specs,
)


class TestMapRole:
    def test_user_role(self):
        assert _map_role("user") == "user"

    def test_assistant_role(self):
        assert _map_role("assistant") == "assistant"

    def test_model_role_maps_to_assistant(self):
        assert _map_role("model") == "assistant"

    def test_system_role(self):
        assert _map_role("system") == "system"

    def test_unknown_role_passthrough(self):
        assert _map_role("unknown") == "unknown"

    def test_empty_role(self):
        assert _map_role("") == "user"

    def test_case_insensitive(self):
        assert _map_role("USER") == "user"
        assert _map_role("Assistant") == "assistant"


class TestMapStopReason:
    def test_end_turn_maps_to_stop(self):
        assert _map_stop_reason("end_turn") == "stop"

    def test_tool_use_maps_to_tool_calls(self):
        assert _map_stop_reason("tool_use") == "tool_calls"

    def test_max_tokens_maps_to_length(self):
        assert _map_stop_reason("max_tokens") == "length"

    def test_cancelled_maps_to_stop(self):
        assert _map_stop_reason("cancelled") == "stop"

    def test_none_maps_to_stop(self):
        assert _map_stop_reason(None) == "stop"

    def test_unknown_passthrough(self):
        assert _map_stop_reason("custom_reason") == "custom_reason"


class TestExtractTextFromContentBlocks:
    def test_single_text_block(self):
        content_blocks = [{"text": "Hello, world!"}]
        assert _extract_text_from_content_blocks(content_blocks) == "Hello, world!"

    def test_multiple_text_blocks(self):
        content_blocks = [{"text": "Hello"}, {"text": "world"}]
        assert _extract_text_from_content_blocks(content_blocks) == "Hello world"

    def test_empty_content(self):
        assert _extract_text_from_content_blocks([]) is None

    def test_no_text_blocks(self):
        content_blocks = [{"toolUse": {"name": "test"}}]
        assert _extract_text_from_content_blocks(content_blocks) is None

    def test_mixed_blocks(self):
        content_blocks = [
            {"text": "Using tool"},
            {"toolUse": {"name": "calculator", "toolUseId": "123", "input": {}}},
        ]
        assert _extract_text_from_content_blocks(content_blocks) == "Using tool"


class TestExtractToolCallsFromContentBlocks:
    def test_single_tool_use(self):
        content_blocks = [
            {
                "toolUse": {
                    "name": "calculator",
                    "toolUseId": "call_123",
                    "input": {"a": 1, "b": 2},
                }
            }
        ]
        tool_calls = _extract_tool_calls_from_content_blocks(content_blocks)
        assert len(tool_calls) == 1
        assert tool_calls[0].function_name == "calculator"
        assert tool_calls[0].id == "call_123"
        assert tool_calls[0].type == "function"
        assert '"a": 1' in tool_calls[0].function_arguments

    def test_multiple_tool_uses(self):
        content_blocks = [
            {"toolUse": {"name": "tool1", "toolUseId": "1", "input": {}}},
            {"toolUse": {"name": "tool2", "toolUseId": "2", "input": {}}},
        ]
        tool_calls = _extract_tool_calls_from_content_blocks(content_blocks)
        assert len(tool_calls) == 2
        assert tool_calls[0].function_name == "tool1"
        assert tool_calls[1].function_name == "tool2"

    def test_no_tool_uses(self):
        content_blocks = [{"text": "No tools here"}]
        tool_calls = _extract_tool_calls_from_content_blocks(content_blocks)
        assert len(tool_calls) == 0


class TestParseStrandsMessages:
    def test_simple_user_message(self):
        messages = [{"role": "user", "content": [{"text": "Hello"}]}]
        parsed = _parse_strands_messages(messages)
        assert len(parsed) == 1
        assert parsed[0].role == "user"
        assert parsed[0].content == "Hello"

    def test_assistant_message(self):
        messages = [{"role": "assistant", "content": [{"text": "Hi there!"}]}]
        parsed = _parse_strands_messages(messages)
        assert len(parsed) == 1
        assert parsed[0].role == "assistant"
        assert parsed[0].content == "Hi there!"

    def test_tool_result_message(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "toolUseId": "call_123",
                            "content": [{"text": "Result: 42"}],
                        }
                    }
                ],
            }
        ]
        parsed = _parse_strands_messages(messages)
        assert len(parsed) == 1
        assert parsed[0].role == "tool"
        assert parsed[0].tool_call_id == "call_123"
        assert parsed[0].content == "Result: 42"

    def test_assistant_with_tool_use(self):
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "name": "calculator",
                            "toolUseId": "call_456",
                            "input": {"operation": "add"},
                        }
                    }
                ],
            }
        ]
        parsed = _parse_strands_messages(messages)
        assert len(parsed) == 1
        assert parsed[0].role == "assistant"
        assert parsed[0].tool_calls is not None
        assert len(parsed[0].tool_calls) == 1
        assert parsed[0].tool_calls[0].function_name == "calculator"

    def test_multi_turn_conversation(self):
        messages = [
            {"role": "user", "content": [{"text": "Question 1"}]},
            {"role": "assistant", "content": [{"text": "Answer 1"}]},
            {"role": "user", "content": [{"text": "Question 2"}]},
        ]
        parsed = _parse_strands_messages(messages)
        assert len(parsed) == 3
        assert parsed[0].role == "user"
        assert parsed[1].role == "assistant"
        assert parsed[2].role == "user"


class TestParseStrandsResponse:
    def test_simple_response(self):
        message = {"role": "assistant", "content": [{"text": "Response text"}]}
        choice = _parse_strands_response(message, "end_turn")
        assert choice.role == "assistant"
        assert choice.content == "Response text"
        assert choice.finish_reason == "stop"

    def test_tool_use_response(self):
        message = {
            "role": "assistant",
            "content": [
                {
                    "toolUse": {
                        "name": "get_weather",
                        "toolUseId": "call_789",
                        "input": {"city": "Paris"},
                    }
                }
            ],
        }
        choice = _parse_strands_response(message, "tool_use")
        assert choice.role == "assistant"
        assert choice.finish_reason == "tool_calls"
        assert choice.tool_calls is not None
        assert len(choice.tool_calls) == 1
        assert choice.tool_calls[0].function_name == "get_weather"

    def test_max_tokens_response(self):
        message = {"role": "assistant", "content": [{"text": "Truncated..."}]}
        choice = _parse_strands_response(message, "max_tokens")
        assert choice.finish_reason == "length"


class TestProcessToolSpecs:
    def test_single_tool(self):
        tool_specs = [
            {
                "name": "calculator",
                "description": "Perform calculations",
                "inputSchema": {
                    "type": "object",
                    "properties": {"expr": {"type": "string"}},
                },
            }
        ]
        attrs = _process_tool_specs(tool_specs)
        assert attrs["gen_ai.request.tools.0.type"] == "function"
        assert attrs["gen_ai.request.tools.0.function.name"] == "calculator"
        assert (
            attrs["gen_ai.request.tools.0.function.description"]
            == "Perform calculations"
        )
        assert "gen_ai.request.tools.0.function.parameters" in attrs

    def test_multiple_tools(self):
        tool_specs = [
            {"name": "tool1", "description": "First tool"},
            {"name": "tool2", "description": "Second tool"},
        ]
        attrs = _process_tool_specs(tool_specs)
        assert attrs["gen_ai.request.tools.0.function.name"] == "tool1"
        assert attrs["gen_ai.request.tools.1.function.name"] == "tool2"

    def test_empty_tools(self):
        attrs = _process_tool_specs([])
        assert attrs == {}

    def test_tool_without_parameters(self):
        tool_specs = [{"name": "simple_tool", "description": "No params"}]
        attrs = _process_tool_specs(tool_specs)
        assert attrs["gen_ai.request.tools.0.function.name"] == "simple_tool"
        assert "gen_ai.request.tools.0.function.parameters" not in attrs


class TestBuildSystemPromptText:
    def test_simple_string_system_prompt(self):
        result = _build_system_prompt_text("You are a helpful assistant.", None)
        assert result == "You are a helpful assistant."

    def test_system_prompt_content_blocks(self):
        system_prompt_content = [
            {"text": "You are a helpful assistant."},
            {"text": "Be concise."},
        ]
        result = _build_system_prompt_text(None, system_prompt_content)
        assert result == "You are a helpful assistant. Be concise."

    def test_system_prompt_content_takes_priority(self):
        system_prompt_content = [{"text": "Priority prompt"}]
        result = _build_system_prompt_text("Fallback prompt", system_prompt_content)
        assert result == "Priority prompt"

    def test_no_system_prompt(self):
        result = _build_system_prompt_text(None, None)
        assert result is None

    def test_empty_system_prompt_content_falls_back_to_string(self):
        result = _build_system_prompt_text("Fallback", [])
        assert result == "Fallback"

    def test_empty_string_system_prompt(self):
        result = _build_system_prompt_text("", None)
        assert result is None

    def test_system_prompt_content_ignores_non_text_blocks(self):
        system_prompt_content = [
            {"text": "Instructions"},
            {"image": "some_image_data"},
            {"text": "More instructions"},
        ]
        result = _build_system_prompt_text(None, system_prompt_content)
        assert result == "Instructions More instructions"


class TestIsModelInvokeSpan:
    def test_chat_operation_is_model_invoke(self):
        class MockSpan:
            attributes = {"gen_ai.operation.name": "chat"}
            name = "chat"

        assert _is_model_invoke_span(MockSpan()) is True

    def test_execute_tool_operation_is_not_model_invoke(self):
        class MockSpan:
            attributes = {"gen_ai.operation.name": "execute_tool"}
            name = "execute_tool get_weather"

        assert _is_model_invoke_span(MockSpan()) is False

    def test_invoke_agent_operation_is_not_model_invoke(self):
        class MockSpan:
            attributes = {"gen_ai.operation.name": "invoke_agent"}
            name = "Agent"

        assert _is_model_invoke_span(MockSpan()) is False

    def test_invoke_swarm_operation_is_not_model_invoke(self):
        class MockSpan:
            attributes = {"gen_ai.operation.name": "invoke_swarm"}
            name = "invoke_swarm"

        assert _is_model_invoke_span(MockSpan()) is False

    def test_fallback_to_span_name_when_no_attributes(self):
        class MockSpan:
            attributes = None
            name = "chat"

        assert _is_model_invoke_span(MockSpan()) is True

    def test_fallback_non_chat_name_returns_false(self):
        class MockSpan:
            attributes = None
            name = "Agent"

        assert _is_model_invoke_span(MockSpan()) is False

    def test_span_without_attributes_or_name(self):
        class MockSpan:
            pass

        assert _is_model_invoke_span(MockSpan()) is False

    def test_empty_attributes_uses_fallback(self):
        class MockSpan:
            attributes = {}
            name = "chat"

        assert _is_model_invoke_span(MockSpan()) is True

    def test_empty_attributes_non_chat_name(self):
        class MockSpan:
            attributes = {}
            name = "execute_tool"

        assert _is_model_invoke_span(MockSpan()) is False


class TestExtractUserFromModel:
    def test_extract_user_from_params(self):
        class MockModel:
            config = {"params": {"user": "user@example.com"}}

        assert _extract_user_from_model(MockModel()) == "user@example.com"

    def test_extract_user_with_other_params(self):
        class MockModel:
            config = {
                "model_id": "gpt-4",
                "params": {"user": "test-user", "max_tokens": 100},
            }

        assert _extract_user_from_model(MockModel()) == "test-user"

    def test_no_user_in_params(self):
        class MockModel:
            config = {"params": {"max_tokens": 100}}

        assert _extract_user_from_model(MockModel()) is None

    def test_no_params_in_config(self):
        class MockModel:
            config = {"model_id": "gpt-4"}

        assert _extract_user_from_model(MockModel()) is None

    def test_no_config(self):
        class MockModel:
            pass

        assert _extract_user_from_model(MockModel()) is None

    def test_none_config(self):
        class MockModel:
            config = None

        assert _extract_user_from_model(MockModel()) is None

    def test_empty_config(self):
        class MockModel:
            config = {}

        assert _extract_user_from_model(MockModel()) is None

    def test_params_not_dict(self):
        class MockModel:
            config = {"params": "not_a_dict"}

        assert _extract_user_from_model(MockModel()) is None

    def test_user_as_integer_converted_to_string(self):
        class MockModel:
            config = {"params": {"user": 12345}}

        assert _extract_user_from_model(MockModel()) == "12345"

    def test_empty_user_string(self):
        class MockModel:
            config = {"params": {"user": ""}}

        assert _extract_user_from_model(MockModel()) is None

    def test_none_user(self):
        class MockModel:
            config = {"params": {"user": None}}

        assert _extract_user_from_model(MockModel()) is None
