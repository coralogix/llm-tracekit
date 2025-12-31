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

import pytest
from assertpy import assert_that
from dataclasses import dataclass
from typing import List, Optional, Any

from guardrails import (
    convert_litellm,
    convert_openai_agents,
    convert_bedrock_converse,
    Message,
    Role,
)


class TestConvertLiteLLM:
    def test_convert_simple_conversation(self):
        messages = [
            {"role": "user", "content": "Hello!"},
        ]
        response = {
            "choices": [
                {"message": {"role": "assistant", "content": "Hi there!"}}
            ]
        }
        
        result = convert_litellm(response, messages)
        
        assert_that(result).is_length(2)
        assert_that(result[0].role).is_equal_to(Role.User)
        assert_that(result[0].content).is_equal_to("Hello!")
        assert_that(result[1].role).is_equal_to(Role.Assistant)
        assert_that(result[1].content).is_equal_to("Hi there!")

    def test_convert_multi_turn_conversation(self):
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "How are you?"},
        ]
        response = {
            "choices": [
                {"message": {"role": "assistant", "content": "I'm doing well!"}}
            ]
        }
        
        result = convert_litellm(response, messages)
        
        assert_that(result).is_length(5)
        assert_that(result[0].role).is_equal_to(Role.System)
        assert_that(result[4].role).is_equal_to(Role.Assistant)
        assert_that(result[4].content).is_equal_to("I'm doing well!")

    def test_convert_no_input_messages(self):
        response = {
            "choices": [
                {"message": {"role": "assistant", "content": "Response only"}}
            ]
        }
        
        result = convert_litellm(response)
        
        assert_that(result).is_length(1)
        assert_that(result[0].role).is_equal_to(Role.Assistant)

    def test_convert_empty_response(self):
        messages = [{"role": "user", "content": "Hello"}]
        response = {"choices": []}
        
        result = convert_litellm(response, messages)
        
        assert_that(result).is_length(1)
        assert_that(result[0].role).is_equal_to(Role.User)


class TestConvertOpenAIAgents:
    def test_convert_simple_response(self):
        @dataclass
        class MockContentPart:
            text: str
            
        @dataclass
        class MockOutputMessage:
            content: List[Any]
            role: str = "assistant"
            
        @dataclass
        class MockResponse:
            instructions: str
            output: List[Any]
        
        response = MockResponse(
            instructions="Be helpful",
            output=[MockOutputMessage(content=[MockContentPart(text="Hello!")])]
        )
        input_items = [
            {"role": "user", "content": "Hi there!", "type": "message"}
        ]
        
        result = convert_openai_agents(response, input_items)
        
        assert_that(result).is_length(3)
        assert_that(result[0].role).is_equal_to(Role.System)
        assert_that(result[0].content).is_equal_to("Be helpful")
        assert_that(result[1].role).is_equal_to(Role.User)
        assert_that(result[2].role).is_equal_to(Role.Assistant)

    def test_convert_with_function_output(self):
        @dataclass
        class MockResponse:
            instructions: Optional[str] = None
            output: Optional[List[Any]] = None
        
        response = MockResponse()
        input_items = [
            {"role": "user", "content": "Calculate 2+2"},
            {"type": "function_call_output", "output": "4"},
        ]
        
        result = convert_openai_agents(response, input_items)
        
        assert_that(result).is_length(2)
        assert_that(result[0].role).is_equal_to(Role.User)
        assert_that(result[1].role).is_equal_to(Role.Tool)
        assert_that(result[1].content).is_equal_to("4")

    def test_convert_no_response(self):
        input_items = [
            {"role": "user", "content": "Hello"}
        ]
        
        result = convert_openai_agents(None, input_items)
        
        assert_that(result).is_length(1)
        assert_that(result[0].role).is_equal_to(Role.User)


class TestConvertBedrockConverse:
    def test_convert_simple_conversation(self):
        messages = [
            {"role": "user", "content": [{"text": "Hello!"}]}
        ]
        system = [{"text": "Be helpful"}]
        response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Hi there!"}]
                }
            }
        }
        
        result = convert_bedrock_converse(response, messages, system)
        
        assert_that(result).is_length(3)
        assert_that(result[0].role).is_equal_to(Role.System)
        assert_that(result[0].content).is_equal_to("Be helpful")
        assert_that(result[1].role).is_equal_to(Role.User)
        assert_that(result[1].content).is_equal_to("Hello!")
        assert_that(result[2].role).is_equal_to(Role.Assistant)
        assert_that(result[2].content).is_equal_to("Hi there!")

    def test_convert_with_tool_result(self):
        messages = [
            {"role": "user", "content": [{"text": "What's the weather?"}]},
            {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "toolUseId": "123",
                            "content": [{"text": "Sunny, 72F"}]
                        }
                    }
                ]
            }
        ]
        response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "The weather is sunny!"}]
                }
            }
        }
        
        result = convert_bedrock_converse(response, messages)
        
        assert_that(result).is_length(3)
        assert_that(result[0].role).is_equal_to(Role.User)
        assert_that(result[1].role).is_equal_to(Role.Tool)
        assert_that(result[1].content).is_equal_to("Sunny, 72F")
        assert_that(result[2].role).is_equal_to(Role.Assistant)

    def test_convert_no_system_messages(self):
        messages = [
            {"role": "user", "content": [{"text": "Hello"}]}
        ]
        response = {
            "output": {
                "message": {
                    "role": "assistant", 
                    "content": [{"text": "Hi!"}]
                }
            }
        }
        
        result = convert_bedrock_converse(response, messages)
        
        assert_that(result).is_length(2)
        assert_that(result[0].role).is_equal_to(Role.User)
        assert_that(result[1].role).is_equal_to(Role.Assistant)

    def test_convert_empty_response(self):
        messages = [
            {"role": "user", "content": [{"text": "Hello"}]}
        ]
        response = {"output": {}}
        
        result = convert_bedrock_converse(response, messages)
        
        assert_that(result).is_length(1)
        assert_that(result[0].role).is_equal_to(Role.User)

