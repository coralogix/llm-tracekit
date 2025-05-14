# LLM Tracekit
This library contains modified versions of the [OpenTelemetry instrumentaions](https://github.com/open-telemetry/opentelemetry-python-contrib/) for [openai](https://openai.com/) and [bedrock](https://aws.amazon.com/bedrock/), designed to simplify LLM application development and production tracing and debugging.

## Installation
#### OpenAI
```bash
pip install llm-tracekit[openai]
```

#### Bedrock
```bash
pip install llm-tracekit[bedrock]
```

## Usage
This section describes how to setup up instrumentation for OpenAI or Bedrock. The examples will use the OpenAI instrumentation, but the usage is identical for both instrumentations, so you can simple replace `OpenAIInstrumentor` with `BedrockInstrumentor` if you are using Bedrock.

### Setting up tracing
You can use the `setup_export_to_coralogix` function to setup tracing and export traces to Coralogix
```python
from llm_tracekit import setup_export_to_coralogix

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
from llm_tracekit import OpenAIInstrumentor

OpenAIInstrumentor().instrument()
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
OpenAIInstrumentor().uninstrument()
```

### Full Example
```python
from llm_tracekit import OpenAIInstrumentor, setup_export_to_coralogix
from openai import OpenAI

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
OpenAIInstrumentor().instrument()

# Example OpenAI Usage
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "Write a short poem on open telemetry."},
    ],
)
```

### Changes from OpenTelemetry
* The `user` parameter in the OpenAI Chat Completions API is now recorded in the span as the `gen_ai.openai.request.user` attribute
* The `tools` parameter in the OpenAI Chat Completions API is now recorded in the span as the `gen_ai.openai.request.tools` attributes.
* User prompts and model responses are captured as span attributes instead of log events (see [Semantic Conventions](#semantic-conventions) below)

## Semantic Conventions
| Attribute | Type | Description | Examples
| --------- | ---- | ----------- | --------
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

### OpenAI specific attributes
| Attribute | Type | Description | Examples
| --------- | ---- | ----------- | --------
| `gen_ai.openai.request.user` | string | A unique identifier representing the end-user | `user@company.com`
| `gen_ai.openai.request.tools.<tool_number>.type` | string | Type of tool entry in tools list | `function`
| `gen_ai.openai.request.tools.<tool_number>.function.name` | string | The name of the function to use in tool calls | `get_current_weather`
| `gen_ai.openai.request.tools.<tool_number>.function.description` | string | Description of the function | `Get the current weather in a given location`
| `gen_ai.openai.request.tools.<tool_number>.function.parameters` | string | JSON describing the schema of the function parameters | `{"type": "object", "properties": {"location": {"type": "string", "description": "The city and state, e.g. San Francisco, CA"}, "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}}, "required": ["location"]}`

### Bedrock specific attributes
| Attribute | Type | Description | Examples
| --------- | ---- | ----------- | --------
| `gen_ai.bedrock.agent_alias.id` | string | The ID of the agent-alias in an `invoke_agent` call | `user@company.com`
| `gen_ai.bedrock.request.tools.<tool_number>.function.name` | string | The name of the function to use in tool calls | `get_current_weather`
| `gen_ai.bedrock.request.tools.<tool_number>.function.description` | string | Description of the function | `Get the current weather in a given location`
| `gen_ai.bedrock.request.tools.<tool_number>.function.parameters` | string | JSON describing the schema of the function parameters | `{"type": "object", "properties": {"location": {"type": "string", "description": "The city and state, e.g. San Francisco, CA"}, "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}}, "required": ["location"]}`
