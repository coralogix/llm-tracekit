# LLM Tracekit OpenAI

OpenTelemetry instrumentation for [OpenAI](https://openai.com/) Chat Completions API.

## Installation

```bash
pip install llm-tracekit-openai
```

Or via the meta-package:

```bash
pip install llm-tracekit[openai]
```

## Usage

```python
from llm_tracekit_core import setup_export_to_coralogix
from llm_tracekit_openai import OpenAIInstrumentor
from openai import OpenAI

# Configure tracing
setup_export_to_coralogix(
    service_name="ai-service",
    application_name="ai-application",
    subsystem_name="ai-subsystem",
    capture_content=True,
)

# Activate instrumentation
OpenAIInstrumentor().instrument()

# Use OpenAI as normal
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Write a short poem."}],
)
```

### Async Support

Works with both sync and async clients:

```python
from openai import AsyncOpenAI

client = AsyncOpenAI()
response = await client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

### Streaming Support

Streaming completions are fully supported:

```python
stream = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Count to 10"}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")
```

### Tool Calls

Function/tool calls are automatically traced:

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "What's the weather in Paris?"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
            },
        },
    }],
)
```

### Uninstrument

To disable instrumentation:

```python
OpenAIInstrumentor().uninstrument()
```

## Span Attributes

### Standard GenAI Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `gen_ai.prompt.<n>.role` | string | Message role (`system`, `user`, `assistant`, `tool`) |
| `gen_ai.prompt.<n>.content` | string | Message content |
| `gen_ai.completion.<c>.role` | string | Response role |
| `gen_ai.completion.<c>.content` | string | Response content |
| `gen_ai.completion.<c>.finish_reason` | string | Completion finish reason |

### OpenAI-specific Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `gen_ai.openai.request.user` | string | End-user identifier |
| `gen_ai.openai.request.tools.<n>.type` | string | Tool type |
| `gen_ai.openai.request.tools.<n>.function.name` | string | Function name |
| `gen_ai.openai.request.tools.<n>.function.description` | string | Function description |
| `gen_ai.openai.request.tools.<n>.function.parameters` | string | Function parameters schema |

## License

Apache License 2.0

