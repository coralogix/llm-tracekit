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

"""Tests for provider fallback behavior - unknown providers should still get spans."""

from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, LLMResult


def _get_chat_spans(spans):
    return [span for span in spans if span.name.startswith("chat ")]


def test_unknown_provider_still_creates_span(span_exporter, instrument_langchain):
    """Test that unknown providers still get instrumented with the fallback system."""
    from llm_tracekit.langchain.callback import _FALLBACK_SYSTEM

    # Get the handler from the instrumentor
    handler = instrument_langchain._handler
    assert handler is not None

    # Simulate a chat model start with an unknown provider
    run_id = uuid4()
    serialized = {
        "name": "ChatUnknownProvider",
        "id": ["unknown", "ChatUnknownProvider"],
    }
    messages = [[HumanMessage(content="Hello")]]
    metadata = {"ls_provider": "unknown", "ls_model_name": "unknown-model"}
    invocation_params = {"model": "unknown-model", "model_name": "unknown-model"}

    handler.on_chat_model_start(
        serialized=serialized,
        messages=messages,
        run_id=run_id,
        parent_run_id=None,
        metadata=metadata,
        invocation_params=invocation_params,
    )

    # Verify a span was created (state exists for the run_id)
    state = handler._span_manager.get_state(run_id)
    assert state is not None, "Span should be created for unknown provider"
    assert state.span is not None

    # Simulate the LLM end
    response = LLMResult(
        generations=[
            [
                ChatGeneration(
                    message=AIMessage(content="Hi there!"),
                    generation_info={"finish_reason": "stop"},
                )
            ]
        ],
        llm_output={"model_name": "unknown-model"},
    )

    handler.on_llm_end(response=response, run_id=run_id)

    # Check the span was created with the fallback system
    spans = span_exporter.get_finished_spans()
    chat_spans = _get_chat_spans(spans)

    assert len(chat_spans) == 1, f"Expected 1 chat span, got {len(chat_spans)}"
    span = chat_spans[0]

    # Verify the system is the fallback
    assert span.attributes is not None
    assert span.attributes.get("gen_ai.system") == _FALLBACK_SYSTEM

    # Verify completion attributes exist
    completion_keys = [k for k in span.attributes.keys() if "completion" in k.lower()]
    assert len(completion_keys) > 0, (
        f"Expected completion attributes but found none. "
        f"All attributes: {list(span.attributes.keys())}"
    )

    # Verify prompt attributes exist
    prompt_keys = [k for k in span.attributes.keys() if "prompt" in k.lower()]
    assert len(prompt_keys) > 0, "Expected prompt attributes"


def test_known_provider_uses_correct_system(span_exporter, instrument_langchain):
    """Test that known providers use their specific system value."""
    from opentelemetry.semconv._incubating.attributes import (
        gen_ai_attributes as GenAIAttributes,
    )

    handler = instrument_langchain._handler
    assert handler is not None

    # Simulate a chat model start with ChatOpenAI
    run_id = uuid4()
    serialized = {
        "name": "ChatOpenAI",
        "id": ["langchain", "chat_models", "openai", "ChatOpenAI"],
    }
    messages = [[HumanMessage(content="Hello")]]
    metadata = {"ls_provider": "openai", "ls_model_name": "gpt-4o-mini"}
    invocation_params = {"model": "gpt-4o-mini", "model_name": "gpt-4o-mini"}

    handler.on_chat_model_start(
        serialized=serialized,
        messages=messages,
        run_id=run_id,
        parent_run_id=None,
        metadata=metadata,
        invocation_params=invocation_params,
    )

    # Simulate the LLM end
    response = LLMResult(
        generations=[
            [
                ChatGeneration(
                    message=AIMessage(content="Hi!"),
                    generation_info={"finish_reason": "stop"},
                )
            ]
        ],
        llm_output={"model_name": "gpt-4o-mini"},
    )

    handler.on_llm_end(response=response, run_id=run_id)

    # Check the span has the correct system
    spans = span_exporter.get_finished_spans()
    chat_spans = _get_chat_spans(spans)

    assert len(chat_spans) == 1
    span = chat_spans[0]

    assert span.attributes is not None
    assert (
        span.attributes.get("gen_ai.system")
        == GenAIAttributes.GenAiSystemValues.OPENAI.value
    )


def test_anthropic_provider_recognized(span_exporter, instrument_langchain):
    """Test that ChatAnthropic is properly recognized."""
    from opentelemetry.semconv._incubating.attributes import (
        gen_ai_attributes as GenAIAttributes,
    )

    handler = instrument_langchain._handler
    assert handler is not None

    run_id = uuid4()
    serialized = {
        "name": "ChatAnthropic",
        "id": ["langchain_anthropic", "ChatAnthropic"],
    }
    messages = [[HumanMessage(content="Hello")]]
    metadata = {"ls_provider": "anthropic", "ls_model_name": "claude-3-opus"}
    invocation_params = {"model": "claude-3-opus", "model_name": "claude-3-opus"}

    handler.on_chat_model_start(
        serialized=serialized,
        messages=messages,
        run_id=run_id,
        parent_run_id=None,
        metadata=metadata,
        invocation_params=invocation_params,
    )

    response = LLMResult(
        generations=[
            [
                ChatGeneration(
                    message=AIMessage(content="Hello!"),
                    generation_info={"finish_reason": "stop"},
                )
            ]
        ],
        llm_output={"model_name": "claude-3-opus"},
    )

    handler.on_llm_end(response=response, run_id=run_id)

    spans = span_exporter.get_finished_spans()
    chat_spans = _get_chat_spans(spans)

    assert len(chat_spans) == 1
    span = chat_spans[0]

    assert span.attributes is not None
    assert (
        span.attributes.get("gen_ai.system")
        == GenAIAttributes.GenAiSystemValues.ANTHROPIC.value
    )


def test_request_model_fallback_when_not_in_standard_keys(
    span_exporter, instrument_langchain
):
    """When model is not in params.model_name/model/model_id or metadata, fallback is used."""
    handler = instrument_langchain._handler
    assert handler is not None

    # Provider that puts model only in metadata.ls_model_name (LangSmith-style)
    run_id = uuid4()
    serialized = {"name": "ChatCustom"}
    messages = [[HumanMessage(content="Hi")]]
    metadata = {"ls_model_name": "my-custom-model"}
    invocation_params = {}  # no model in standard keys

    handler.on_chat_model_start(
        serialized=serialized,
        messages=messages,
        run_id=run_id,
        parent_run_id=None,
        metadata=metadata,
        invocation_params=invocation_params,
    )

    response = LLMResult(
        generations=[
            [
                ChatGeneration(
                    message=AIMessage(content="Hello!"),
                    generation_info={"finish_reason": "stop"},
                )
            ]
        ],
        llm_output={},
    )
    handler.on_llm_end(response=response, run_id=run_id)

    spans = span_exporter.get_finished_spans()
    chat_spans = _get_chat_spans(spans)

    assert len(chat_spans) == 1
    span = chat_spans[0]
    assert span.attributes is not None
    # Fallback uses ls_model_name from metadata
    assert span.attributes.get("gen_ai.request.model") == "my-custom-model"
    assert span.name == "chat my-custom-model"


def test_request_model_fallback_uses_provider_name_when_no_metadata(
    span_exporter, instrument_langchain
):
    """When no model in params or metadata, fallback uses provider class name."""
    handler = instrument_langchain._handler
    assert handler is not None

    run_id = uuid4()
    serialized = {"name": "ChatExoticProvider"}
    messages = [[HumanMessage(content="Hi")]]
    metadata = None
    invocation_params = {}

    handler.on_chat_model_start(
        serialized=serialized,
        messages=messages,
        run_id=run_id,
        parent_run_id=None,
        metadata=metadata,
        invocation_params=invocation_params,
    )

    response = LLMResult(
        generations=[
            [
                ChatGeneration(
                    message=AIMessage(content="Hi!"),
                    generation_info={"finish_reason": "stop"},
                )
            ]
        ],
        llm_output={},
    )
    handler.on_llm_end(response=response, run_id=run_id)

    spans = span_exporter.get_finished_spans()
    chat_spans = _get_chat_spans(spans)

    assert len(chat_spans) == 1
    span = chat_spans[0]
    assert span.attributes is not None
    assert span.attributes.get("gen_ai.request.model") == "ChatExoticProvider"
    assert span.name == "chat ChatExoticProvider"
