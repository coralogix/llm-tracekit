# LLM Tracekit - Microsoft Foundry
OpenTelemetry instrumentation for the [Azure AI Projects Python SDK](https://pypi.org/project/azure-ai-projects/) (Microsoft Foundry), designed to simplify LLM application development and production tracing and debugging.

## Installation
```bash
pip install "llm-tracekit-microsoft-foundry"
```

## Usage
This section describes how to set up instrumentation for the Microsoft Foundry SDK.

### Setting up tracing
You can use the `setup_export_to_coralogix` function to setup tracing and export traces to Coralogix
```python
from llm_tracekit.microsoft_foundry import setup_export_to_coralogix

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
from llm_tracekit.microsoft_foundry import MicrosoftFoundryInstrumentor

MicrosoftFoundryInstrumentor().instrument()
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
MicrosoftFoundryInstrumentor().uninstrument()
```

### Full Example
```python
import os
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from llm_tracekit.microsoft_foundry import MicrosoftFoundryInstrumentor, setup_export_to_coralogix

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
MicrosoftFoundryInstrumentor().instrument()

# Example Microsoft Foundry Usage
with AIProjectClient(
    endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
) as project_client:
    with project_client.get_openai_client() as openai_client:
        # Using Responses API
        response = openai_client.responses.create(
            model="gpt-4o-mini",
            input="Write a short poem on open telemetry.",
        )
        print(response.output_text)

        # Using Chat Completions API
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "Hello, world!"},
            ],
        )
        print(response.choices[0].message.content)
```

## Microsoft Foundry-Specific Attributes
In addition to standard GenAI semantic conventions, this instrumentation captures Foundry-specific context:

| Attribute | Type | Description | Examples |
|-----------|------|-------------|----------|
| `gen_ai.microsoft_foundry.agent.name` | string | Agent name from `extra_body.agent_reference` | `MyAgent` |
| `gen_ai.microsoft_foundry.agent.version` | string | Agent version if specified | `v1` |
| `gen_ai.microsoft_foundry.conversation_id` | string | Conversation ID if using conversations | `conv_123` |

## Semantic Conventions
| Attribute | Type | Description | Examples
| --------- | ---- | ----------- | --------
| `gen_ai.prompt.<message_number>.role` | string | Role of message author for user message <message_number> | `system`, `user`, `assistant`, `tool`
| `gen_ai.prompt.<message_number>.content` | string | Contents of user message <message_number> | `What's the weather in Paris?`
| `gen_ai.prompt.<message_number>.tool_calls.<tool_call_number>.id` | string | ID of tool call in user message <message_number> | `call_ABC123`
| `gen_ai.prompt.<message_number>.tool_calls.<tool_call_number>.type` | string | Type of tool call in user message <message_number> | `function`
| `gen_ai.prompt.<message_number>.tool_calls.<tool_call_number>.function.name` | string | The name of the function used in tool call within user message <message_number> | `get_current_weather`
| `gen_ai.prompt.<message_number>.tool_calls.<tool_call_number>.function.arguments` | string | Arguments passed to the function used in tool call within user message <message_number> | `{"location": "Seattle, WA"}`
| `gen_ai.prompt.<message_number>.tool_call_id` | string | Tool call ID in user message <message_number> (for tool results) | `call_ABC123`
| `gen_ai.completion.<choice_number>.role` | string | Role of message author for choice <choice_number> in model response | `assistant`
| `gen_ai.completion.<choice_number>.finish_reason` | string | Finish reason for choice <choice_number> in model response | `stop`, `tool_calls`
| `gen_ai.completion.<choice_number>.content` | string | Contents of choice <choice_number> in model response | `The weather in Paris is rainy and overcast, with temperatures around 57°F`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number>.id` | string | ID of tool call in choice <choice_number> | `call_ABC123`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number>.type` | string | Type of tool call in choice <choice_number> | `function`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number>.function.name` | string | The name of the function used in tool call within choice <choice_number> | `get_current_weather`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number>.function.arguments` | string | Arguments passed to the function used in tool call within choice <choice_number> | `{"location": "Seattle, WA"}`
| `gen_ai.request.tools.<tool_number>.type` | string | Type of tool entry in tools list | `function`
| `gen_ai.request.tools.<tool_number>.function.name` | string | The name of the function to use in tool calls | `get_current_weather`
| `gen_ai.request.tools.<tool_number>.function.description` | string | Description of the function | `Get the current weather in a given location`
| `gen_ai.request.tools.<tool_number>.function.parameters` | string | JSON describing the schema of the function parameters | `{"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]}`
| `gen_ai.request.user` | string | A unique identifier representing the end-user | `user@company.com`
