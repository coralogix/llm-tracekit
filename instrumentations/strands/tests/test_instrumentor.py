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

"""Integration tests for Strands instrumentation."""

import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# Set up tracer provider BEFORE importing strands
_span_exporter = InMemorySpanExporter()
_tracer_provider = TracerProvider()
_tracer_provider.add_span_processor(SimpleSpanProcessor(_span_exporter))
trace.set_tracer_provider(_tracer_provider)

# Enable content capture
os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

# Instrument BEFORE importing strands
from llm_tracekit.strands import StrandsInstrumentor  # noqa: E402

_instrumentor = StrandsInstrumentor()
_instrumentor.instrument()


class TestInstrumentor:
    def setup_method(self):
        _span_exporter.clear()

    def test_instrumentor_instruments_tracer_methods(self):
        """Test that the instrumentor patches the tracer methods."""
        import strands.telemetry.tracer as tracer_module

        # The methods should be wrapped
        start_method = tracer_module.Tracer.start_model_invoke_span
        end_method = tracer_module.Tracer.end_model_invoke_span

        # Check that the methods are wrapped (they should be our wrapped functions)
        assert "wrapped_start_model_invoke_span" in start_method.__name__
        assert "wrapped_end_model_invoke_span" in end_method.__name__

    def test_instrumentor_instruments_stream_messages(self):
        """Test that the instrumentor patches stream_messages."""
        import strands.event_loop.streaming as streaming_module

        # The function should be wrapped
        stream_fn = streaming_module.stream_messages
        assert "wrapped_stream_messages" in stream_fn.__name__

    def test_parse_messages_adds_prompt_attributes(self):
        """Test that parsing messages generates correct prompt attributes."""
        from llm_tracekit.strands.patch import _parse_strands_messages
        from llm_tracekit.core import generate_message_attributes

        messages = [
            {"role": "user", "content": [{"text": "Hello, how are you?"}]},
            {"role": "assistant", "content": [{"text": "I am fine, thank you!"}]},
        ]

        parsed = _parse_strands_messages(messages)
        attrs = generate_message_attributes(parsed, capture_content=True)

        assert attrs["gen_ai.prompt.0.role"] == "user"
        assert attrs["gen_ai.prompt.0.content"] == "Hello, how are you?"
        assert attrs["gen_ai.prompt.1.role"] == "assistant"
        assert attrs["gen_ai.prompt.1.content"] == "I am fine, thank you!"

    def test_parse_response_adds_completion_attributes(self):
        """Test that parsing response generates correct completion attributes."""
        from llm_tracekit.strands.patch import _parse_strands_response
        from llm_tracekit.core import generate_choice_attributes

        message = {
            "role": "assistant",
            "content": [{"text": "The answer is 42."}],
        }

        choice = _parse_strands_response(message, "end_turn")
        attrs = generate_choice_attributes([choice], capture_content=True)

        assert attrs["gen_ai.completion.0.role"] == "assistant"
        assert attrs["gen_ai.completion.0.content"] == "The answer is 42."
        assert attrs["gen_ai.completion.0.finish_reason"] == "stop"

    def test_parse_tool_call_response(self):
        """Test that tool call responses are parsed correctly."""
        from llm_tracekit.strands.patch import _parse_strands_response
        from llm_tracekit.core import generate_choice_attributes

        message = {
            "role": "assistant",
            "content": [
                {
                    "toolUse": {
                        "name": "get_weather",
                        "toolUseId": "call_123",
                        "input": {"city": "Paris"},
                    }
                }
            ],
        }

        choice = _parse_strands_response(message, "tool_use")
        attrs = generate_choice_attributes([choice], capture_content=True)

        assert attrs["gen_ai.completion.0.role"] == "assistant"
        assert attrs["gen_ai.completion.0.finish_reason"] == "tool_calls"
        assert attrs["gen_ai.completion.0.tool_calls.0.function.name"] == "get_weather"
        assert attrs["gen_ai.completion.0.tool_calls.0.id"] == "call_123"
        assert (
            '"city": "Paris"'
            in attrs["gen_ai.completion.0.tool_calls.0.function.arguments"]
        )

    def test_tool_result_message_parsing(self):
        """Test that tool result messages are parsed correctly."""
        from llm_tracekit.strands.patch import _parse_strands_messages
        from llm_tracekit.core import generate_message_attributes

        messages = [
            {"role": "user", "content": [{"text": "What is the weather?"}]},
            {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "name": "get_weather",
                            "toolUseId": "call_456",
                            "input": {"city": "London"},
                        }
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "toolUseId": "call_456",
                            "content": [{"text": "Sunny, 20°C"}],
                        }
                    }
                ],
            },
        ]

        parsed = _parse_strands_messages(messages)
        attrs = generate_message_attributes(parsed, capture_content=True)

        # First message: user question
        assert attrs["gen_ai.prompt.0.role"] == "user"
        assert attrs["gen_ai.prompt.0.content"] == "What is the weather?"

        # Second message: assistant with tool call
        assert attrs["gen_ai.prompt.1.role"] == "assistant"
        assert attrs["gen_ai.prompt.1.tool_calls.0.function.name"] == "get_weather"

        # Third message: tool result
        assert attrs["gen_ai.prompt.2.role"] == "tool"
        assert attrs["gen_ai.prompt.2.tool_call_id"] == "call_456"
        assert attrs["gen_ai.prompt.2.content"] == "Sunny, 20°C"

    def test_system_prompt_is_first_message(self):
        """Test that system prompt is captured as gen_ai.prompt.0 with role=system."""
        from llm_tracekit.strands.patch import (
            _parse_strands_messages,
            _build_system_prompt_text,
        )
        from llm_tracekit.core import generate_message_attributes, Message

        # Simulate what stream_messages does: system prompt + messages
        system_prompt = "You are a helpful assistant."
        messages = [{"role": "user", "content": [{"text": "Hello!"}]}]

        # Build system prompt text
        system_text = _build_system_prompt_text(system_prompt, None)
        parsed_messages = _parse_strands_messages(messages)

        # Prepend system message
        system_message = Message(role="system", content=system_text)
        all_messages = [system_message] + parsed_messages

        attrs = generate_message_attributes(all_messages, capture_content=True)

        # System prompt should be at index 0
        assert attrs["gen_ai.prompt.0.role"] == "system"
        assert attrs["gen_ai.prompt.0.content"] == "You are a helpful assistant."

        # User message should be at index 1
        assert attrs["gen_ai.prompt.1.role"] == "user"
        assert attrs["gen_ai.prompt.1.content"] == "Hello!"

    def test_system_prompt_content_blocks_as_first_message(self):
        """Test that system_prompt_content blocks are captured as gen_ai.prompt.0."""
        from llm_tracekit.strands.patch import (
            _parse_strands_messages,
            _build_system_prompt_text,
        )
        from llm_tracekit.core import generate_message_attributes, Message

        # Use system_prompt_content (the authoritative format)
        system_prompt_content = [
            {"text": "You are a financial assistant."},
            {"text": "Be concise and accurate."},
        ]
        messages = [
            {"role": "user", "content": [{"text": "What is my balance?"}]},
            {"role": "assistant", "content": [{"text": "Your balance is $100."}]},
        ]

        system_text = _build_system_prompt_text(None, system_prompt_content)
        parsed_messages = _parse_strands_messages(messages)

        system_message = Message(role="system", content=system_text)
        all_messages = [system_message] + parsed_messages

        attrs = generate_message_attributes(all_messages, capture_content=True)

        # System prompt at index 0
        assert attrs["gen_ai.prompt.0.role"] == "system"
        assert (
            attrs["gen_ai.prompt.0.content"]
            == "You are a financial assistant. Be concise and accurate."
        )

        # User at index 1
        assert attrs["gen_ai.prompt.1.role"] == "user"
        assert attrs["gen_ai.prompt.1.content"] == "What is my balance?"

        # Assistant at index 2
        assert attrs["gen_ai.prompt.2.role"] == "assistant"
        assert attrs["gen_ai.prompt.2.content"] == "Your balance is $100."

    def test_no_system_prompt_user_is_index_0(self):
        """Test that user message is at index 0 when no system prompt is provided."""
        from llm_tracekit.strands.patch import (
            _parse_strands_messages,
            _build_system_prompt_text,
        )
        from llm_tracekit.core import generate_message_attributes, Message

        messages = [
            {"role": "user", "content": [{"text": "Hello!"}]},
            {"role": "assistant", "content": [{"text": "Hi there!"}]},
        ]

        # No system prompt
        system_text = _build_system_prompt_text(None, None)
        parsed_messages = _parse_strands_messages(messages)

        # Same logic as in stream_messages wrapper
        if system_text:
            system_message = Message(role="system", content=system_text)
            all_messages = [system_message] + parsed_messages
        else:
            all_messages = parsed_messages

        attrs = generate_message_attributes(all_messages, capture_content=True)

        # User should be at index 0 (no system prompt)
        assert attrs["gen_ai.prompt.0.role"] == "user"
        assert attrs["gen_ai.prompt.0.content"] == "Hello!"

        # Assistant at index 1
        assert attrs["gen_ai.prompt.1.role"] == "assistant"
        assert attrs["gen_ai.prompt.1.content"] == "Hi there!"

        # No system role should exist
        assert "gen_ai.prompt.2.role" not in attrs


def teardown_module():
    """Clean up after all tests."""
    _instrumentor.uninstrument()
    os.environ.pop("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", None)
