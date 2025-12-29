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

from tests.utils import assert_choices_in_span, assert_messages_in_span
from tests.openai_agents.utils import assert_attributes

from agents import Agent, Runner, function_tool


@pytest.mark.vcr()
@pytest.mark.asyncio()
async def test_agent_single_turn(
    span_exporter, instrument
):
    simple_agent = Agent(
        name="SimpleAgent",
        model="gpt-4o-mini",
        instructions="Be a helpful assistant",
    )

    prompt = "Say 'This is a test.'"
    await Runner.run(simple_agent, prompt)

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 3 # response -> agent data -> parent

    final_response_span = None
    for span in spans:
        if span.name == "Response":
            final_response_span = span

    assert final_response_span is not None, "Final response span not found"

    expected_messages = [
    {
        'role': 'system',
        'content': 'Be a helpful assistant'
    },
    {
        'role': 'user',
        'content': prompt
    }
    ]

    expected_choices = [
    {
        'finish_reason': 'stop',
        'message': {
            'role': 'assistant',
            'content': 'This is a test.'
        }
    }
    ]
    print(final_response_span.attributes)

    assert_messages_in_span(
        span=final_response_span,
        expected_messages=expected_messages,
        expect_content=True
        )
    
    assert_choices_in_span(
        span=final_response_span,
        expected_choices=expected_choices,
        expect_content=True
        )

    assert_attributes(
        span=final_response_span,
        response_model="gpt-4o-mini-2024-07-18",
        agent_name=simple_agent.name
    )

@pytest.mark.vcr()
@pytest.mark.asyncio()
async def test_agent_tool_usage(
    span_exporter, instrument
):
    @function_tool
    async def get_weather(city: str) -> str:
        return f"The weather in {city} is currently 25°C and clear."
    
    weather_agent = Agent(
        name="WeatherAgent",
        tools=[get_weather],
        model="gpt-4o-mini",
        instructions="get weather",
    )
    
    prompt = "What is the weather in Tel Aviv? Answer in the next format: City - Temperature - Weather."
    result = await Runner.run(weather_agent, prompt)

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 5 # response -> function -> response -> agent data -> parent

    final_response_span = None
    for span in spans:
        if span.name == "Response": 
            final_response_span = span

    assert final_response_span is not None, "Final response span not found"
    
    tool_id = final_response_span.attributes["gen_ai.prompt.2.tool_calls.0.id"]
    tool_result_id = final_response_span.attributes["gen_ai.prompt.3.tool_call_id"]

    expected_messages = [
    {
        'role': 'system',
        'content': 'get weather'
    },
    {
        'role': 'user',
        'content': prompt
    },
    {
        'role': 'assistant',
        'tool_calls': [
            {
                'id':tool_id,
                'type': 'function_call',
                'function': {
                    'name': 'get_weather',
                    'arguments': '{"city":"Tel Aviv"}'
                }
            }
        ]
    },
    {
        'role': 'tool',
        'type': 'function_call_output',
        'tool_call_id': tool_result_id,
        'content': 'The weather in Tel Aviv is currently 25\u00b0C and clear.'
    }
    ]
    
    expected_choices = [
    {
        'finish_reason': 'stop',
        'message': {
            'role': 'assistant',
            'content': result.final_output
        }
    }
    ]

    assert_attributes(
        span=final_response_span,
        response_model="gpt-4o-mini-2024-07-18",
        agent_name=weather_agent.name
    )

    assert_messages_in_span(
        span=final_response_span,
        expected_messages=expected_messages,
        expect_content=True
    )

    assert_choices_in_span(
        span=final_response_span,
        expected_choices=expected_choices,
        expect_content=True
    )

@pytest.mark.vcr()
@pytest.mark.asyncio()
async def test_agent_multi_turn(
    span_exporter, instrument
):
    simple_agent = Agent(
        name="SimpleAgent",
        model="gpt-4o-mini",
        instructions="Be a helpful assistant",
    )

    prompt_1 = "Say 'This is a test."
    result = await Runner.run(simple_agent, prompt_1)
    
    prompt_2 = "Repeat your last message."

    conversation_history = result.to_input_list()
    conversation_history.append({"role": "user", "content": prompt_2})

    await Runner.run(simple_agent, conversation_history)

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 6 # response -> agent data -> parent (twice)

    final_response_span = None
    for span in spans:
        if span.name == "Response":
            final_response_span = span

    assert final_response_span is not None, "Final response span not found"

    expected_messages = [
    {
        'role': 'system',
        'content': 'Be a helpful assistant'
    },
    {
        'role': 'user',
        'content': prompt_1
    },
    {
        'role': 'assistant',
        'content': "This is a test."
    },
    {
        'role': 'user',
        'content': prompt_2
    }
    ]

    expected_choices = [
    {
        'finish_reason': 'stop',
        'message': {
            'role': 'assistant',
            'content': 'This is a test.'
        }
    }
    ]

    assert_messages_in_span(
        span=final_response_span,
        expected_messages=expected_messages,
        expect_content=True
        )
    
    assert_choices_in_span(
        span=final_response_span,
        expected_choices=expected_choices,
        expect_content=True
        )

    assert_attributes(
        span=final_response_span,
        response_model="gpt-4o-mini-2024-07-18",
        agent_name=simple_agent.name
    )


@pytest.mark.vcr()
@pytest.mark.asyncio()
async def test_agent_tool_execution_error(
    span_exporter, instrument
):
    @function_tool
    async def failing_weather_tool(city: str) -> str:
        raise ValueError("Tool failed as intended for testing")

    failing_agent = Agent(
        name="FailingAgent",
        tools=[failing_weather_tool],
        model="gpt-4o-mini",
        instructions="to fail",
    )
    
    prompt = "What is the weather in Tel Aviv?"
    result = await Runner.run(failing_agent, prompt)

    spans = span_exporter.get_finished_spans()
    
    assert len(spans) == 5 

    final_response_span = None
    for span in spans:
        if span.name == "Response":
            final_response_span = span

    assert final_response_span is not None, "Final response span not found"

    tool_id = final_response_span.attributes.get("gen_ai.prompt.2.tool_calls.0.id")
    tool_result_id = final_response_span.attributes.get("gen_ai.prompt.3.tool_call_id")

    expected_messages = [
        {
        'role': 'system',
        'content': 'to fail'
        },
        {
            'role': 'user',
            'content': prompt
        },
        {
            'role': 'assistant',
            'tool_calls': [
                {
                    'id': tool_id,
                    'type': 'function_call',
                    'function': {
                        'name': 'failing_weather_tool',
                        'arguments': '{"city":"Tel Aviv"}'
                    }
                }
            ]
        },
        {
            'role': 'tool',
            'tool_call_id': tool_result_id,
            'content': 'An error occurred while running the tool. Please try again. Error: Tool failed as intended for testing'
        }
    ]

    expected_choices = [
        {
            'finish_reason': 'stop',
            'message': {
                'role': 'assistant',
                'content': result.final_output
            }
        }
    ]

    assert_messages_in_span(
        span=final_response_span,
        expected_messages=expected_messages,
        expect_content=True
    )

    assert_choices_in_span(
        span=final_response_span,
        expected_choices=expected_choices,
        expect_content=True
    )

    assert_attributes(
        span=final_response_span,
        response_model="gpt-4o-mini-2024-07-18",
        agent_name=failing_agent.name
    )


@pytest.mark.vcr()
@pytest.mark.asyncio()
async def test_agent_nested_agent(
    span_exporter, instrument
):
    @function_tool
    async def get_weather(city: str) -> str:
        return f"The weather in {city} is currently 25°C and clear."
    
    weather_agent = Agent(
        name="WeatherAgent",
        tools=[get_weather],
        model="gpt-4o-mini",
        instructions="get weather",
    )
    
    @function_tool
    async def call_weather_agent(city: str) -> str:
        prompt = f"What is the weather in {city}?"
        result = await Runner.run(weather_agent, prompt)
        return result.final_output

    main_agent = Agent(
        name="Assistant",
        tools=[call_weather_agent],
        model="gpt-4o-mini",
        instructions="Be a helpful assistant. If the user asks about weather, call the weather agent."
    )

    prompt = "What is the weather in Tel Aviv?"
    result = await Runner.run(main_agent, prompt)

    spans = span_exporter.get_finished_spans()
    
    assert len(spans) == 9 # response -> response -> function -> response -> agent data ->
                           # -> function -> response -> agent data -> parent

    assert sum(1 for span in spans if span.name == "Response") == 4
    assert sum(1 for span in spans if span.name == "Tool - call_weather_agent") == 1
    assert sum(1 for span in spans if span.name == "Tool - get_weather") == 1
    assert sum(1 for span in spans if span.name == "Agent - WeatherAgent") == 1
    assert sum(1 for span in spans if span.name == "Agent - Assistant") == 1

    final_response_span = None
    for span in spans:
        if span.name == "Response":
            final_response_span = span

    assert final_response_span is not None, "Final response span not found"

    tool_id = final_response_span.attributes.get("gen_ai.prompt.2.tool_calls.0.id")
    tool_result_id = final_response_span.attributes.get("gen_ai.prompt.3.tool_call_id")

    expected_messages = [
        {
            'role': 'system',
            'content': 'Be a helpful assistant. If the user asks about weather, call the weather agent.'
        },
        {
            "role": "user",
            "content": "What is the weather in Tel Aviv?"
        },
        {
            "role": "assistant",
            "tool_calls": [
            {
                "id": tool_id,
                "type": "function_call",
                "function": {
                "name": "call_weather_agent",
                "arguments": "{\"city\":\"Tel Aviv\"}"
                }
            }
            ]
        },
        {
            "role": "tool",
            "tool_call_id": tool_result_id,
            "content": "The weather in Tel Aviv is currently 35°C and sunny."
        }
    ]

    expected_choices = [
        {
            'finish_reason': 'stop',
            'message': {
                'role': 'assistant',
                'content': result.final_output
            }
        }
    ]

    assert_messages_in_span(
        span=final_response_span,
        expected_messages=expected_messages,
        expect_content=True
    )

    assert_choices_in_span(
        span=final_response_span,
        expected_choices=expected_choices,
        expect_content=True
    )

    assert_attributes(
        span=final_response_span,
        response_model="gpt-4o-mini-2024-07-18",
        agent_name=main_agent.name
    )