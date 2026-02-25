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
from unittest.mock import patch
from opentelemetry.trace.status import StatusCode

from .utils import assert_base_attributes, get_chat_spans


async def _fake_process_query(self, prompt, options, transport=None):
    """Fake process_query that yields canned messages without calling the CLI."""
    from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock

    yield AssistantMessage(
        content=[TextBlock(text="The answer is 4.")],
        model="claude-3-5-sonnet-20241022",
    )
    yield ResultMessage(
        subtype="result",
        duration_ms=150,
        duration_api_ms=120,
        is_error=False,
        num_turns=1,
        session_id="test-session",
        total_cost_usd=0.001,
        usage={"input_tokens": 12, "output_tokens": 8},
    )


@pytest.mark.asyncio
async def test_query_one_span_and_attributes(span_exporter, instrument):
    """One call to query() produces one span with prompt and completion."""
    with patch(
        "claude_agent_sdk.query.InternalClient.process_query",
        _fake_process_query,
    ):
        from claude_agent_sdk.query import query
        from claude_agent_sdk import ClaudeAgentOptions

        options = ClaudeAgentOptions(system_prompt="You are helpful.")
        messages = []
        async for msg in query(prompt="What is 2+2?", options=options):
            messages.append(msg)

    assert len(messages) >= 2  # AssistantMessage + ResultMessage
    spans = span_exporter.get_finished_spans()
    chat_spans = get_chat_spans(spans)
    assert len(chat_spans) == 1
    span = chat_spans[0]

    assert_base_attributes(span, system="claude.agent_sdk")
    assert span.attributes is not None
    assert span.attributes.get("gen_ai.prompt.0.role") == "system"
    assert "You are helpful" in str(span.attributes.get("gen_ai.prompt.0.content", ""))
    assert span.attributes.get("gen_ai.prompt.1.role") == "user"
    assert span.attributes.get("gen_ai.prompt.1.content") == "What is 2+2?"
    assert span.attributes.get("gen_ai.completion.0.role") == "assistant"
    assert span.attributes.get("gen_ai.completion.0.finish_reason") == "stop"
    assert "The answer is 4" in str(
        span.attributes.get("gen_ai.completion.0.content", "")
    )
    assert span.attributes.get("gen_ai.claude_agent_sdk.result.num_turns") == 1
    assert span.attributes.get("gen_ai.claude_agent_sdk.result.duration_ms") == 150


@pytest.mark.asyncio
async def test_query_content_capture_off(span_exporter, instrument_no_content):
    """With content capture off, prompt/completion content and tool arguments are not set."""
    with patch(
        "claude_agent_sdk.query.InternalClient.process_query",
        _fake_process_query,
    ):
        from claude_agent_sdk.query import query
        from claude_agent_sdk import ClaudeAgentOptions

        async for _ in query(prompt="Secret?", options=ClaudeAgentOptions()):
            pass

    spans = span_exporter.get_finished_spans()
    chat_spans = get_chat_spans(spans)
    assert len(chat_spans) == 1
    span = chat_spans[0]
    assert span.attributes is not None
    assert span.attributes.get("gen_ai.prompt.0.role") == "user"
    assert span.attributes.get("gen_ai.completion.0.role") == "assistant"


@pytest.mark.asyncio
async def test_query_error_finalizes_span(span_exporter, instrument):
    """When the stream raises, the span is ended with exception."""

    async def fake_process_query_error(self, prompt, options, transport=None):
        from claude_agent_sdk.types import AssistantMessage, TextBlock

        yield AssistantMessage(
            content=[TextBlock(text="Partial")],
            model="claude",
        )
        raise RuntimeError("Stream failed")

    with patch(
        "claude_agent_sdk.query.InternalClient.process_query",
        fake_process_query_error,
    ):
        from claude_agent_sdk.query import query
        from claude_agent_sdk import ClaudeAgentOptions

        with pytest.raises(RuntimeError, match="Stream failed"):
            async for _ in query(prompt="Hi", options=ClaudeAgentOptions()):
                pass

    spans = span_exporter.get_finished_spans()
    chat_spans = get_chat_spans(spans)
    assert len(chat_spans) == 1
    span = chat_spans[0]
    assert span.attributes is not None
    assert span.status.status_code is StatusCode.ERROR
