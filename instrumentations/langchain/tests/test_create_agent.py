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

"""Tests for create_agent() flow instrumentation."""

import pytest
from langchain.agents import create_agent


def _get_chat_spans(spans):
    return [span for span in spans if span.name.startswith("chat ")]


@pytest.mark.vcr()
def test_create_agent_invoke(span_exporter, instrument_langchain):
    """Test that create_agent().invoke() creates proper spans with completion attributes."""
    agent = create_agent(
        model="openai:gpt-4o-mini",
        tools=[],
        system_prompt="You are a helpful assistant. Answer in one word.",
    )

    result = agent.invoke({"messages": [{"role": "user", "content": "Say hello!"}]})

    # Check we got a response
    assert "messages" in result
    messages = result["messages"]
    assert len(messages) >= 2  # At least user message and assistant response

    # Get all spans
    spans = span_exporter.get_finished_spans()
    chat_spans = _get_chat_spans(spans)

    print(f"\n=== Total spans: {len(spans)} ===")
    for i, span in enumerate(spans):
        print(f"Span {i}: {span.name}")
        if span.attributes:
            completion_attrs = [
                k for k in span.attributes.keys() if "completion" in k.lower()
            ]
            prompt_attrs = [k for k in span.attributes.keys() if "prompt" in k.lower()]
            print(f"  Completion attrs: {completion_attrs}")
            print(f"  Prompt attrs: {prompt_attrs}")

    # We should have at least one chat span
    assert len(chat_spans) >= 1, (
        f"Expected at least 1 chat span, got {len(chat_spans)}. All spans: {[s.name for s in spans]}"
    )

    # Check the chat span has completion attributes
    span = chat_spans[-1]
    assert span.attributes is not None

    # Verify completion attributes exist
    completion_keys = [k for k in span.attributes.keys() if "completion" in k.lower()]
    assert len(completion_keys) > 0, (
        f"Expected completion attributes but found none. "
        f"All attributes: {list(span.attributes.keys())}"
    )

    # Check that there are prompt attributes for the system message and user message
    assert "gen_ai.prompt.0.role" in span.attributes
    assert "gen_ai.prompt.1.role" in span.attributes  # system + user
