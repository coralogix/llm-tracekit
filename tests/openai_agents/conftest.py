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

import os
import pytest

from llm_tracekit.openai.instrumentor import OpenAIInstrumentor
from agents import Agent, function_tool


@pytest.fixture(autouse=True)
def openai_env_vars():
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "test_openai_api_key"

@pytest.fixture(scope="function")
def instrument(tracer_provider, meter_provider):
    instrumentor = OpenAIInstrumentor()
    
    instrumentor.instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    yield instrumentor

    instrumentor.uninstrument()

@pytest.fixture
def weather_tool():
    @function_tool
    async def get_weather(city: str) -> str:
        return f"The weather in {city} is currently 25°C and clear."
    return get_weather

@pytest.fixture
def failing_tool():
    @function_tool
    async def failing_weather_tool(city: str) -> str:
        raise ValueError("Tool failed as intended for testing")
    return failing_weather_tool

@pytest.fixture
def weather_agent(weather_tool):
    return Agent(
        name="WeatherAgent",
        tools=[weather_tool],
        model="gpt-4o-mini",
        instructions="get weather",
    )

@pytest.fixture
def failing_agent(failing_tool):
    return Agent(
        name="FailingAgent",
        tools=[failing_tool],
        model="gpt-4o-mini",
        instructions="to fail",
    )

@pytest.fixture
def simple_agent():
    return Agent(
        name="SimpleAgent",
        model="gpt-4o-mini",
        instructions="Be a helpful assistant",
    )

@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": [
            "authorization",
            "Idempotency-Key",
            "x-stainless-arch",
            "x-stainless-lang",
            "x-stainless-os",
            "x-stainless-package-version",
            "x-stainless-runtime",
            "x-stainless-runtime-version",
            "user-agent",
        ],
        "decode_compressed_response": True,
    }