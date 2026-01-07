# LLM Tracekit Gemini

OpenTelemetry instrumentation for [Google Gemini](https://ai.google.dev/) API.

## Installation

```bash
pip install llm-tracekit-gemini
```


## Usage

```python
import google.generativeai as genai
from llm_tracekit.gemini import GeminiInstrumentor, setup_export_to_coralogix

# Configure tracing
setup_export_to_coralogix(
    service_name="ai-service",
    application_name="ai-application",
    subsystem_name="ai-subsystem",
    capture_content=True,
)

# Activate instrumentation
GeminiInstrumentor().instrument()

# Use Gemini as normal
genai.configure(api_key="your-api-key")
model = genai.GenerativeModel("gemini-pro")
response = model.generate_content("Hello!")
```

### Async Support

```python
response = await model.generate_content_async("Hello!")
```

### Streaming Support

```python
response = model.generate_content("Count to 10", stream=True)
for chunk in response:
    print(chunk.text, end="")
```

### Tool Calls

Function calling is automatically traced:

```python
def get_weather(location: str) -> str:
    return f"Weather in {location}: Sunny"

model = genai.GenerativeModel(
    "gemini-pro",
    tools=[get_weather],
)
response = model.generate_content("What's the weather in Paris?")
```

### Uninstrument

To disable instrumentation:

```python
GeminiInstrumentor().uninstrument()
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

