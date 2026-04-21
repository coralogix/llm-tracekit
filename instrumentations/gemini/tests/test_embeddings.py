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

from google import genai
from google.genai import types

import llm_tracekit.core._extended_gen_ai_attributes as ExtendedGenAIAttributes

from .utils import assert_attributes, assert_messages_in_span


@pytest.mark.vcr()
def test_embed_content_single(span_exporter, instrument):
    client = genai.Client()
    try:
        client.models.embed_content(
            model="gemini-embedding-001",
            contents="Why is the sky blue?",
        )
    finally:
        client.close()

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    span = spans[0]
    assert span.name == "embeddings gemini-embedding-001"

    assert_attributes(
        span=span,
        system="gemini",
        operation_name="embeddings",
        request_model="gemini-embedding-001",
    )

    user_message = {"role": "user", "content": "Why is the sky blue?"}
    assert_messages_in_span(
        span=span, expected_messages=[user_message], expect_content=True
    )

    vector_key = ExtendedGenAIAttributes.GEN_AI_EMBEDDING_VECTOR.format(
        embedding_index=0
    )
    assert vector_key in span.attributes
    assert len(span.attributes[vector_key]) > 0


@pytest.mark.vcr()
def test_embed_content_no_content(span_exporter, instrument_no_content):
    client = genai.Client()
    try:
        client.models.embed_content(
            model="gemini-embedding-001",
            contents="Why is the sky blue?",
        )
    finally:
        client.close()

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    span = spans[0]
    assert span.name == "embeddings gemini-embedding-001"

    assert_attributes(
        span=span,
        system="gemini",
        operation_name="embeddings",
        request_model="gemini-embedding-001",
    )

    user_message = {"role": "user", "content": "Why is the sky blue?"}
    assert_messages_in_span(
        span=span, expected_messages=[user_message], expect_content=False
    )

    vector_key = ExtendedGenAIAttributes.GEN_AI_EMBEDDING_VECTOR.format(
        embedding_index=0
    )
    assert vector_key not in span.attributes


@pytest.mark.vcr()
def test_embed_content_batch(span_exporter, instrument):
    client = genai.Client()
    try:
        response = client.models.embed_content(
            model="gemini-embedding-001",
            contents=["First text", "Second text", "Third text"],
        )
    finally:
        client.close()

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    span = spans[0]

    expected_messages = [
        {"role": "user", "content": "First text"},
        {"role": "user", "content": "Second text"},
        {"role": "user", "content": "Third text"},
    ]
    assert_messages_in_span(
        span=span, expected_messages=expected_messages, expect_content=True
    )

    assert len(response.embeddings) == 3
    for i in range(3):
        vector_key = ExtendedGenAIAttributes.GEN_AI_EMBEDDING_VECTOR.format(
            embedding_index=i
        )
        assert vector_key in span.attributes
        assert len(span.attributes[vector_key]) > 0


@pytest.mark.vcr()
def test_embed_content_with_dimensionality(span_exporter, instrument):
    client = genai.Client()
    try:
        client.models.embed_content(
            model="gemini-embedding-001",
            contents="Test text for dimensionality",
            config=types.EmbedContentConfig(output_dimensionality=256),
        )
    finally:
        client.close()

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    span = spans[0]
    assert (
        span.attributes[ExtendedGenAIAttributes.GEN_AI_EMBEDDINGS_DIMENSION_COUNT]
        == 256
    )

    vector_key = ExtendedGenAIAttributes.GEN_AI_EMBEDDING_VECTOR.format(
        embedding_index=0
    )
    assert vector_key in span.attributes
    assert len(span.attributes[vector_key]) == 256


@pytest.mark.vcr()
@pytest.mark.asyncio()
async def test_async_embed_content(span_exporter, instrument):
    client = genai.Client()
    try:
        await client.aio.models.embed_content(
            model="gemini-embedding-001",
            contents="Why is the sky blue?",
        )
        await client.aio.aclose()
    finally:
        client.close()

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    span = spans[0]
    assert span.name == "embeddings gemini-embedding-001"

    assert_attributes(
        span=span,
        system="gemini",
        operation_name="embeddings",
        request_model="gemini-embedding-001",
    )

    user_message = {"role": "user", "content": "Why is the sky blue?"}
    assert_messages_in_span(
        span=span, expected_messages=[user_message], expect_content=True
    )

    vector_key = ExtendedGenAIAttributes.GEN_AI_EMBEDDING_VECTOR.format(
        embedding_index=0
    )
    assert vector_key in span.attributes
    assert len(span.attributes[vector_key]) > 0
