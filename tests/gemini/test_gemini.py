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

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

from tests.gemini.utils import assert_attributes
from tests.utils import assert_choices_in_span, assert_messages_in_span


@pytest.mark.vcr()
def test_gemini_completion(span_exporter, instrument):
    client = genai.Client()
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents="Say this is a test",
        )
    finally:
        client.close()

    spans = span_exporter.get_finished_spans()
    assert len(spans) > 0
    span = spans[0]

    assert_attributes(
        span,
        "gemini",
        "chat",
        "gemini-2.0-flash-lite",
        response.model_version,
        response.response_id,
        response.usage_metadata.prompt_token_count,
        response.usage_metadata.candidates_token_count,
    )

    user_message = {"role": "user", "content": "Say this is a test"}
    assert_messages_in_span(
        span=span, expected_messages=[user_message], expect_content=True
    )

    choice = {
        "finish_reason": "STOP",
        "message": {
            "role": "model",
            "content": response.candidates[0].content.parts[0].text,
        },
    }
    assert_choices_in_span(span=span, expected_choices=[choice], expect_content=True)


@pytest.mark.vcr()
def test_gemini_completion_stream(span_exporter, instrument):
    client = genai.Client()
    try:
        stream = client.models.generate_content_stream(
            model="gemini-2.0-flash-lite",
            contents="Say this is a test",
        )

        collected_text = []
        for chunk in stream:
            for candidate in chunk.candidates:
                for part in getattr(candidate.content, "parts", []):
                    text_value = getattr(part, "text", None)
                    if text_value:
                        collected_text.append(text_value)
    finally:
        client.close()

    spans = span_exporter.get_finished_spans()
    assert len(spans) > 0
    span = spans[0]

    assert_attributes(
        span,
        "gemini",
        "chat",
        "gemini-2.0-flash-lite",
        span.attributes.get(GenAIAttributes.GEN_AI_RESPONSE_MODEL),
        span.attributes.get(GenAIAttributes.GEN_AI_RESPONSE_ID),
    )

    user_message = {"role": "user", "content": "Say this is a test"}
    assert_messages_in_span(
        span=span, expected_messages=[user_message], expect_content=True
    )

    choice = {
        "finish_reason": "STOP",
        "message": {
            "role": "model",
            "content": "".join(collected_text),
        },
    }
    assert_choices_in_span(span=span, expected_choices=[choice], expect_content=True)


@pytest.mark.vcr()
@pytest.mark.asyncio()
async def test_gemini_async_completion(span_exporter, instrument):
    with genai.Client() as client:
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents="Say this is a test",
        )
        await client.aio.aclose()

    spans = span_exporter.get_finished_spans()
    assert len(spans) > 0
    span = spans[0]

    assert_attributes(
        span,
        "gemini",
        "chat",
        "gemini-2.0-flash-lite",
        response.model_version,
        response.response_id,
        response.usage_metadata.prompt_token_count,
        response.usage_metadata.candidates_token_count,
    )

    user_message = {"role": "user", "content": "Say this is a test"}
    assert_messages_in_span(
        span=span, expected_messages=[user_message], expect_content=True
    )

    choice = {
        "finish_reason": "STOP",
        "message": {
            "role": "model",
            "content": response.candidates[0].content.parts[0].text,
        },
    }
    assert_choices_in_span(span=span, expected_choices=[choice], expect_content=True)


@pytest.mark.vcr()
def test_gemini_tool_usage(span_exporter, instrument):
    def get_current_temperature(location: str) -> int:
        return "The current temperature in " + location + " is 22 degrees Celsius."
    
    weather_function = {
        "name": "get_current_temperature",
        "description": "Gets the current temperature for a given location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city name, e.g. Tel Aviv",
                },
            },
            "required": ["location"],
        },
    }

    client = genai.Client()
    tools = types.Tool(function_declarations=[weather_function])
    config = types.GenerateContentConfig(tools=[tools])

    contents = [
        {
            "role": "user",
            "parts": [
                {
                    "text": "What's the temperature in Tel Aviv?"
                }
            ],
        }
    ]

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=contents,
            config=config,
        )
        function_call = response.candidates[0].content.parts[0].function_call
        
        result = get_current_temperature(**function_call.args)

        function_response_part = types.Part.from_function_response(
            name=function_call.name,
            response={"result": result},
        )

        contents.append(response.candidates[0].content)
        contents.append(types.Content(role="tool", parts=[function_response_part]))

        final_response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=contents,
            config=config,
        )
    finally:
        client.close()

    spans = span_exporter.get_finished_spans()
    assert len(spans) > 0
    first_span = spans[0]
    second_span = spans[1]

    messages = [
        {
            "role": "user", 
            "content": "What's the temperature in Tel Aviv?"
        }
    ]

    assert_messages_in_span(
        span=first_span, expected_messages=messages, expect_content=True
    )

    assert_attributes(
        second_span,
        "gemini",
        "chat",
        "gemini-2.0-flash-lite",
        final_response.model_version,
        final_response.response_id,
        final_response.usage_metadata.prompt_token_count,
        final_response.usage_metadata.candidates_token_count,
    )

    choice = {
        "finish_reason": "STOP",
        "message": {
            "role": "model",
            "content": final_response.candidates[0].content.parts[0].text,
        },
    }
    assert_choices_in_span(span=second_span, expected_choices=[choice], expect_content=True)