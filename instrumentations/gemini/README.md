# LLM Tracekit - Gemini
OpenTelemetry instrumentation for [Google Gemini](https://ai.google.dev/), designed to simplify LLM application development and production tracing and debugging.

## Supported Operations
- **Text Generation**: `client.models.generate_content()` and `generate_content_stream()` (sync and async)
- **Embeddings**: `client.models.embed_content()` (sync and async)

## Installation
```bash
pip install "llm-tracekit-gemini"
```


## Usage
This section describes how to set up instrumentation for Google Gemini.

### Setting up tracing
You can use the `setup_export_to_coralogix` function to setup tracing and export traces to Coralogix
```python
from llm_tracekit.gemini import setup_export_to_coralogix

setup_export_to_coralogix(
    service_name="ai-service",
    application_name="ai-application",
    subsystem_name="ai-subsystem",
    capture_content=True,
)
```

Alternatively, you can set up tracing manually:
```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

tracer_provider = TracerProvider(
    resource=Resource.create({SERVICE_NAME: "ai-service"}),
)
exporter = OTLPSpanExporter()
span_processor = SimpleSpanProcessor(exporter)
tracer_provider.add_span_processor(span_processor)
trace.set_tracer_provider(tracer_provider)
```

### Activation
To instrument all clients, call the `instrument` method
```python
from llm_tracekit.gemini import GeminiInstrumentor

GeminiInstrumentor().instrument()
```

### Enabling message content
Message content such as the contents of the prompt, completion, function arguments and return values are not captured by default.
To capture message content as span attributes, do one of the following:
* Pass `capture_content=True` when calling `setup_export_to_coralogix`
* Set the environment variable `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` to `true`

Most Coralogix AI evaluations will not work without message contents, so it is highly recommended to enable capturing.

### Uninstrument
To uninstrument clients, call the `uninstrument` method:
```python
GeminiInstrumentor().uninstrument()
```

### Full Example - Text Generation
```python
from google import genai
from llm_tracekit.gemini import GeminiInstrumentor, setup_export_to_coralogix

# Optional: Configure sending spans to Coralogix
# Reads Coralogix connection details from the following environment variables:
# - CX_TOKEN
# - CX_ENDPOINT
setup_export_to_coralogix(
    service_name="ai-service",
    application_name="ai-application",
    subsystem_name="ai-subsystem",
    capture_content=True,
)

# Activate instrumentation
GeminiInstrumentor().instrument()

# Example Gemini Usage
client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=[{"role": "user", "parts": [{"text": "Write a short poem on open telemetry."}]}],
)
```

### Full Example - Embeddings
```python
from google import genai
from google.genai import types
from llm_tracekit.gemini import GeminiInstrumentor, setup_export_to_coralogix

setup_export_to_coralogix(
    service_name="ai-service",
    application_name="ai-application",
    subsystem_name="ai-subsystem",
    capture_content=True,
)

GeminiInstrumentor().instrument()

client = genai.Client()

# Single content embedding
response = client.models.embed_content(
    model="gemini-embedding-001",
    contents="What is machine learning?",
)
print(f"Embedding dimensions: {len(response.embeddings[0].values)}")

# Batch embedding
response = client.models.embed_content(
    model="gemini-embedding-001",
    contents=["First text", "Second text", "Third text"],
)
print(f"Number of embeddings: {len(response.embeddings)}")

# With dimensionality reduction
response = client.models.embed_content(
    model="gemini-embedding-001",
    contents="What is quantum computing?",
    config=types.EmbedContentConfig(output_dimensionality=256),
)
print(f"Reduced dimensions: {len(response.embeddings[0].values)}")
```

## Semantic Conventions

### Text Generation Attributes
| Attribute | Type | Description | Examples
| --------- | ---- | ----------- | --------
| `gen_ai.operation.name` | string | The operation being performed | `chat`
| `gen_ai.system` | string | The AI system being used | `gemini`
| `gen_ai.request.model` | string | The model requested | `gemini-2.0-flash`
| `gen_ai.response.model` | string | The model that responded | `gemini-2.0-flash`
| `gen_ai.usage.input_tokens` | int | Number of input tokens | `25`
| `gen_ai.usage.output_tokens` | int | Number of output tokens | `150`
| `gen_ai.prompt.<message_number>.role` | string | Role of message author for user message <message_number> | `system`, `user`, `assistant`, `tool`
| `gen_ai.prompt.<message_number>.content` | string | Contents of user message <message_number> | `What's the weather in Paris?`
| `gen_ai.prompt.<message_number>.tool_calls.<tool_call_number>.id` | string | ID of tool call in user message <message_number> | `call_O8NOz8VlxosSASEsOY7LDUcP`
| `gen_ai.prompt.<message_number>.tool_calls.<tool_call_number>.type` | string | Type of tool call in user message <message_number> | `function`
| `gen_ai.prompt.<message_number>.tool_calls.<tool_call_number>.function.name` | string | The name of the function used in tool call within user message  <message_number> | `get_current_weather`
| `gen_ai.prompt.<message_number>.tool_calls.<tool_call_number>.function.arguments` | string | Arguments passed to the function used in tool call within user message <message_number> | `{"location": "Seattle, WA"}`
| `gen_ai.prompt.<message_number>.tool_call_id` | string | Tool call ID in user message <message_number> | `call_mszuSIzqtI65i1wAUOE8w5H4`
| `gen_ai.completion.<choice_number>.role` | string | Role of message author for choice <choice_number>  in model response | `assistant`
| `gen_ai.completion.<choice_number>.finish_reason` | string | Finish reason for choice <choice_number>  in model response | `stop`, `tool_calls`, `error`
| `gen_ai.completion.<choice_number>.content` | string | Contents of choice <choice_number>  in model response | `The weather in Paris is rainy and overcast, with temperatures around 57°F`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number >.id` | string | ID of tool call in choice <choice_number>  | `call_O8NOz8VlxosSASEsOY7LDUcP`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number >.type` | string | Type of tool call in choice <choice_number>  | `function`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number >.function.name` | string | The name of the function used in tool call  within choice <choice_number> | `get_current_weather`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number >.function.arguments` | string | Arguments passed to the function used in tool call within choice <choice_number> | `{"location": "Seattle, WA"}`
| `gen_ai.request.tools.<tool_number>.type` | string | Type of tool definition advertised to the model | `function`
| `gen_ai.request.tools.<tool_number>.function.name` | string | Name of the tool/function exposed to the model | `get_current_weather`
| `gen_ai.request.tools.<tool_number>.function.description` | string | Description of the tool/function | `Get the current weather in a given location`
| `gen_ai.request.tools.<tool_number>.function.parameters` | string | JSON schema describing the tool/function parameters passed with the request | `{"type": "object", "properties": {"city": {"type": "string"}}}`

### Embeddings Attributes
| Attribute | Type | Description | Examples
| --------- | ---- | ----------- | --------
| `gen_ai.operation.name` | string | The operation being performed | `embeddings`
| `gen_ai.system` | string | The AI system being used | `gemini`
| `gen_ai.request.model` | string | The embedding model requested | `gemini-embedding-001`
| `gen_ai.response.model` | string | The embedding model that responded | `gemini-embedding-001`
| `gen_ai.usage.input_tokens` | int | Number of input tokens | `10`
| `gen_ai.prompt.<n>.role` | string | Role for input content (always `user` for embeddings) | `user`
| `gen_ai.prompt.<n>.content` | string | The text content being embedded | `What is machine learning?`
| `gen_ai.embeddings.dimension.count` | int | Requested output dimensionality | `256`
| `gen_ai.embeddings.<n>.vector` | array | The embedding vector values (when content capture enabled) | `[0.1, 0.2, ...]`
