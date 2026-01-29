# Copyright The OpenTelemetry Authors
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

import os

import openai
import pytest

from llm_tracekit.core import OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT
from llm_tracekit.openai.instrumentor import OpenAIInstrumentor

from .test_embeddings import _DummyEmbeddingResponse
from .utils import assert_all_attributes, assert_messages_in_span


@pytest.mark.asyncio()
async def test_async_embeddings_create_with_content(
    span_exporter, async_openai_client, tracer_provider, meter_provider, monkeypatch
):
    llm_model_value = "text-embedding-3-small"
    input_value = "Say this is a test"

    async def _fake_create(self, *args, **kwargs):
        return _DummyEmbeddingResponse(model=kwargs.get("model"))

    monkeypatch.setattr(
        openai.resources.embeddings.AsyncEmbeddings, "create", _fake_create, raising=True
    )

    os.environ.update({OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT: "True"})
    instrumentor = OpenAIInstrumentor()
    instrumentor.instrument(tracer_provider=tracer_provider, meter_provider=meter_provider)
    try:
        response = await async_openai_client.embeddings.create(
            model=llm_model_value, input=input_value
        )

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert_all_attributes(
            span=spans[0],
            request_model=llm_model_value,
            response_id=response.id,
            response_model=response.model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=None,
            operation_name="embedding",
        )

        user_message = {"role": "user", "content": input_value}
        assert_messages_in_span(
            span=spans[0], expected_messages=[user_message], expect_content=True
        )
    finally:
        os.environ.pop(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, None)
        instrumentor.uninstrument()

