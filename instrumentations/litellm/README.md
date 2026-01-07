# LLM Tracekit LiteLLM

OpenTelemetry instrumentation for [LiteLLM](https://www.litellm.ai/).

## Installation

```bash
pip install llm-tracekit-litellm
```


## Usage

```python
import litellm
from llm_tracekit.litellm import LiteLLMInstrumentor, setup_export_to_coralogix

# Configure tracing
setup_export_to_coralogix(
    service_name="ai-service",
    application_name="ai-application",
    subsystem_name="ai-subsystem",
    capture_content=True,
)

# Activate instrumentation
LiteLLMInstrumentor().instrument()

# Use LiteLLM as normal - works with any provider
response = litellm.completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}],
)

# Or use other providers
response = litellm.completion(
    model="claude-3-sonnet-20240229",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

### Async Support

```python
response = await litellm.acompletion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

### Streaming Support

```python
response = litellm.completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Count to 10"}],
    stream=True,
)
for chunk in response:
    print(chunk.choices[0].delta.content or "", end="")
```

### Tool Calls

Tool calls are automatically traced across all supported providers:

```python
response = litellm.completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "What's the weather?"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather",
            "parameters": {"type": "object", "properties": {}},
        },
    }],
)
```

### Uninstrument

To disable instrumentation:

```python
LiteLLMInstrumentor().uninstrument()
```

## Span Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `gen_ai.prompt.<n>.role` | string | Message role |
| `gen_ai.prompt.<n>.content` | string | Message content |
| `gen_ai.completion.<c>.role` | string | Response role |
| `gen_ai.completion.<c>.content` | string | Response content |
| `gen_ai.completion.<c>.finish_reason` | string | Completion finish reason |

## License

Apache License 2.0

