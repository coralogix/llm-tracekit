# LLM Tracekit - Strands Agents SDK
OpenTelemetry instrumentation for the [Strands Agents SDK](https://strandsagents.com/), designed to simplify LLM agent application development and production tracing and debugging.

## Installation
```bash
pip install "llm-tracekit-strands"
```

## Important: Disable Strands Built-in Telemetry

Strands Agents SDK includes built-in OpenTelemetry tracing. **Do not** initialize the native telemetry when using this adapter, as it will produce duplicate traces that are incompatible with Coralogix's AI Center rendering.

```python
# Do NOT use the following when using llm-tracekit-strands:
# from strands.telemetry import StrandsTelemetry
# StrandsTelemetry.init()
```

## Usage
This section describes how to set up instrumentation for the Strands Agents SDK.

### Setting up tracing
You can use the `setup_export_to_coralogix` function to setup tracing and export traces to Coralogix
```python
from llm_tracekit.strands import setup_export_to_coralogix

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
To instrument all Strands agents, call the `instrument` method
```python
from llm_tracekit.strands import StrandsInstrumentor

StrandsInstrumentor().instrument()
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
StrandsInstrumentor().uninstrument()
```

### Full Example
```python
from strands import Agent
from llm_tracekit.strands import StrandsInstrumentor, setup_export_to_coralogix

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
StrandsInstrumentor().instrument()

# Example Strands Agent Usage
agent = Agent(
    model="anthropic.claude-sonnet-4-20250514",
    system_prompt="You are a helpful assistant.",
)
result = agent("Write a short poem on open telemetry.")
print(result)
```

## Span Hierarchy

The adapter produces a 4-level span hierarchy following OTel GenAI semantic conventions:

```
invoke_agent {agent_name}          (INTERNAL)
  └── cycle {cycle_id}             (INTERNAL)
      ├── chat {model}             (CLIENT)
      └── execute_tool {tool_name} (INTERNAL)
```

## Semantic Conventions
| Attribute | Type | Description | Examples
| --------- | ---- | ----------- | --------
| `gen_ai.prompt.<message_number>.role` | string | Role of message author for user message <message_number> | `system`, `user`, `assistant`, `tool`
| `gen_ai.prompt.<message_number>.content` | string | Contents of user message <message_number> | `What's the weather in Paris?`
| `gen_ai.prompt.<message_number>.tool_calls.<tool_call_number>.id` | string | ID of tool call in user message <message_number> | `tu-abc123`
| `gen_ai.prompt.<message_number>.tool_calls.<tool_call_number>.type` | string | Type of tool call in user message <message_number> | `function`
| `gen_ai.prompt.<message_number>.tool_calls.<tool_call_number>.function.name` | string | The name of the function used in tool call within user message <message_number> | `get_current_weather`
| `gen_ai.prompt.<message_number>.tool_calls.<tool_call_number>.function.arguments` | string | Arguments passed to the function used in tool call within user message <message_number> | `{"location": "Seattle, WA"}`
| `gen_ai.prompt.<message_number>.tool_call_id` | string | Tool call ID in user message <message_number> | `tu-abc123`
| `gen_ai.completion.<choice_number>.role` | string | Role of message author for choice <choice_number> in model response | `assistant`
| `gen_ai.completion.<choice_number>.finish_reason` | string | Finish reason for choice <choice_number> in model response | `end_turn`, `tool_use`
| `gen_ai.completion.<choice_number>.content` | string | Contents of choice <choice_number> in model response | `The weather in Paris is rainy and overcast`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number>.id` | string | ID of tool call in choice <choice_number> | `tu-abc123`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number>.type` | string | Type of tool call in choice <choice_number> | `function`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number>.function.name` | string | The name of the function used in tool call within choice <choice_number> | `get_current_weather`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number>.function.arguments` | string | Arguments passed to the function used in tool call within choice <choice_number> | `{"location": "Seattle, WA"}`

### Strands-specific attributes

#### Agent spans (`invoke_agent`)
| **Attribute** | **Type** | **Description** | **Example** |
|---|---|---|---|
| `gen_ai.system` | string | The GenAI system identifier | `strands` |
| `gen_ai.operation.name` | string | The operation name | `invoke_agent` |
| `gen_ai.agent.name` | string | Name of the agent | `WeatherAgent` |
| `gen_ai.request.model` | string | The model used by the agent | `anthropic.claude-sonnet-4-20250514` |
| `gen_ai.agent.tools` | string | JSON list of available tool names | `["get_weather", "calculator"]` |
| `gen_ai.usage.input_tokens` | int | Aggregated input tokens across all model calls | `300` |
| `gen_ai.usage.output_tokens` | int | Aggregated output tokens across all model calls | `150` |

#### Cycle spans (`cycle`)
| **Attribute** | **Type** | **Description** | **Example** |
|---|---|---|---|
| `strands.agent.cycle.id` | string | The cycle identifier | `cycle-1` |
| `event_loop.parent_cycle_id` | string | Parent cycle ID for recursive cycles | `cycle-0` |

#### Model invocation spans (`chat`)
| **Attribute** | **Type** | **Description** | **Example** |
|---|---|---|---|
| `gen_ai.system` | string | The GenAI system identifier | `strands` |
| `gen_ai.operation.name` | string | The operation name | `chat` |
| `gen_ai.request.model` | string | Model requested | `anthropic.claude-sonnet-4-20250514` |
| `gen_ai.response.model` | string | Model that responded | `anthropic.claude-sonnet-4-20250514` |
| `gen_ai.usage.input_tokens` | int | Input tokens for this call | `100` |
| `gen_ai.usage.output_tokens` | int | Output tokens for this call | `50` |
| `gen_ai.usage.cache_read_input_tokens` | int | Cached input tokens read | `200` |
| `gen_ai.usage.cache_write_input_tokens` | int | Cached input tokens written | `50` |
| `gen_ai.response.finish_reasons` | string[] | Model stop reasons | `("end_turn",)` |

#### Tool spans (`execute_tool`)
| **Attribute** | **Type** | **Description** | **Example** |
|---|---|---|---|
| `gen_ai.system` | string | The GenAI system identifier | `strands` |
| `gen_ai.operation.name` | string | The operation name | `execute_tool` |
| `name` | string | Name of the tool | `get_weather` |
| `type` | string | Type of the tool | `function` |
| `gen_ai.tool.call.id` | string | Tool call ID from model request | `tu-abc123` |
| `gen_ai.tool.status` | string | Execution status | `success`, `error` |
| `input` | string | JSON string of tool arguments (content capture only) | `{"city":"Paris"}` |
| `output` | string | String of tool return value (content capture only) | `22°C, sunny` |

### Metrics

| **Metric** | **Type** | **Description** |
|---|---|---|
| `gen_ai.client.operation.duration` | Histogram | Duration of model invocations in seconds |
| `gen_ai.client.token.usage` | Histogram | Token usage per model invocation |
