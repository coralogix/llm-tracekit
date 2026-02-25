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
from unittest.mock import AsyncMock, patch

from .utils import get_chat_spans


async def _fake_receive_messages():
    from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock

    yield AssistantMessage(
        content=[TextBlock(text="Hello back!")],
        model="claude-3-5-sonnet",
    )
    yield ResultMessage(
        subtype="result",
        duration_ms=200,
        duration_api_ms=180,
        is_error=False,
        num_turns=1,
        session_id="client-session",
        usage={"input_tokens": 5, "output_tokens": 10},
    )


@pytest.fixture
def mock_client_connect():
    """Patch connect (no subprocess) and receive_messages (fake stream of Message objects)."""

    async def fake_connect(self, prompt=None):
        self._query = type("Q", (), {"close": AsyncMock()})()
        self._transport = type("FakeTransport", (), {"write": AsyncMock()})()

    def fake_receive_messages(self):
        return _fake_receive_messages()

    with (
        patch("claude_agent_sdk.client.ClaudeSDKClient.connect", fake_connect),
        patch(
            "claude_agent_sdk.client.ClaudeSDKClient.receive_messages",
            fake_receive_messages,
        ),
    ):
        yield


@pytest.mark.asyncio
async def test_client_one_turn_span(span_exporter, instrument, mock_client_connect):
    """One query() + receive_response() produces one span with turn prompt and completion."""
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

    options = ClaudeAgentOptions(system_prompt="Be brief.")
    async with ClaudeSDKClient(options) as client:
        await client.query("Hello!")
        async for msg in client.receive_response():
            pass

    spans = span_exporter.get_finished_spans()
    chat_spans = get_chat_spans(spans)
    assert len(chat_spans) == 1
    span = chat_spans[0]
    assert span.attributes is not None
    assert span.attributes.get("gen_ai.prompt.0.role") == "system"
    assert span.attributes.get("gen_ai.prompt.1.role") == "user"
    assert span.attributes.get("gen_ai.prompt.1.content") == "Hello!"
    assert span.attributes.get("gen_ai.completion.0.role") == "assistant"
    assert "Hello back" in str(span.attributes.get("gen_ai.completion.0.content", ""))
    assert span.attributes.get("gen_ai.completion.0.finish_reason") == "stop"
