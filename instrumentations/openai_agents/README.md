# LLM Tracekit OpenAI Agents

OpenTelemetry instrumentation for the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/).

> **Requires Python 3.10+**

## Installation

```bash
pip install llm-tracekit-openai-agents
```

Or via the meta-package:

```bash
pip install llm-tracekit[openai-agents]
```

## Usage

```python
from agents import Agent, Runner
from llm_tracekit_core import setup_export_to_coralogix
from llm_tracekit_openai_agents import OpenAIAgentsInstrumentor

# Configure tracing
setup_export_to_coralogix(
    service_name="ai-service",
    application_name="ai-application",
    subsystem_name="ai-subsystem",
    capture_content=True,
)

# Activate instrumentation
OpenAIAgentsInstrumentor().instrument()

# Use Agents SDK as normal
agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant.",
)

result = Runner.run_sync(agent, "Hello!")
print(result.final_output)
```

### Tool Usage

```python
from agents import Agent, Runner, function_tool

@function_tool
def get_weather(location: str) -> str:
    """Get the current weather for a location."""
    return f"Weather in {location}: Sunny, 72°F"

agent = Agent(
    name="WeatherBot",
    instructions="Help users with weather information.",
    tools=[get_weather],
)

result = Runner.run_sync(agent, "What's the weather in Paris?")
```

### Agent Handoffs

```python
weather_agent = Agent(name="WeatherAgent", tools=[get_weather])
main_agent = Agent(
    name="Assistant",
    handoffs=[weather_agent],
)

result = Runner.run_sync(main_agent, "What's the weather in Tokyo?")
```

### Uninstrument

To disable instrumentation:

```python
OpenAIAgentsInstrumentor().uninstrument()
```

## Span Attributes

### Agent Spans

| Attribute | Type | Description |
|-----------|------|-------------|
| `type` | string | `agent` |
| `agent_name` | string | Agent name |
| `handoffs` | string[] | Available handoff agents |
| `tools` | string[] | Available tools |
| `output_type` | string | Expected output type |

### Guardrail Spans

| Attribute | Type | Description |
|-----------|------|-------------|
| `type` | string | `guardrail` |
| `name` | string | Guardrail name |
| `triggered` | boolean | Whether guardrail triggered |

### Handoff Spans

| Attribute | Type | Description |
|-----------|------|-------------|
| `type` | string | `handoff` |
| `from_agent` | string | Source agent |
| `to_agent` | string | Target agent |

### Function Spans

| Attribute | Type | Description |
|-----------|------|-------------|
| `type` | string | `function` |
| `name` | string | Function name |
| `input` | string | Function input (JSON) |
| `output` | string | Function output |

### Enriched LLM Call Spans

| Attribute | Type | Description |
|-----------|------|-------------|
| `gen_ai.agent.name` | string | Agent that initiated the LLM call |

## License

Apache License 2.0

