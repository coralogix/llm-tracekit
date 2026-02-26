# LLM Tracekit - OpenAI Agents SDK
OpenTelemetry instrumentation for the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/), designed to simplify LLM application development and production tracing and debugging.

## Installation
```bash
pip install "llm-tracekit-openai-agents"
```


## Usage
This section describes how to set up instrumentation for the OpenAI Agents SDK.

### Setting up tracing
You can use the `setup_export_to_coralogix` function to setup tracing and export traces to Coralogix
```python
from llm_tracekit.openai_agents import setup_export_to_coralogix

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
from llm_tracekit.openai_agents import OpenAIAgentsInstrumentor

OpenAIAgentsInstrumentor().instrument()
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
OpenAIAgentsInstrumentor().uninstrument()
```

### Full Example
```python
from agents import Agent, Runner
from llm_tracekit.openai_agents import OpenAIAgentsInstrumentor, setup_export_to_coralogix

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
OpenAIAgentsInstrumentor().instrument()

# Example OpenAI Agents Usage
agent = Agent(name="Assistant", instructions="You are a helpful assistant.")
result = Runner.run_sync(agent, input="Write a short poem on open telemetry.")
print(result.final_output)
```

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

### OpenAI Agents SDK specific attributes

#### Agent spans
These spans represent the execution of a single agent. They act as parents for LLM calls, guardrails, and handoffs initiated by that agent.
| **Attribute** | **Type** | **Description**                                                      | **Example**      |
|---------------|----------|----------------------------------------------------------------------|------------------|
| `type`          | string   | The type of the span, identifying it as an agent execution.          | `agent`            |
| `agent_name`    | string   | The name of the agent being executed.                                | `Assistant`        |
| `handoffs`      | string[] | A list of other agents that this agent is capable of handing off to. | `["WeatherAgent"]` |
| `tools`         | string[] | A list of tools (functions) available to this agent.                 | `["get_current_weather"]`  |
| `output_type`   | string   | The expected data type of the agent's final output.                  | `MessageOutput`    |

#### Guardrail spans
These spans represent the execution of a guardrail check.
| **Attribute** | **Type** | **Description**                                                    | **Example**   |
|---------------|----------|--------------------------------------------------------------------|---------------|
| `type`          | string   | The type of the span, identifying it as a guardrail.               | `guardrail`     |
| `name`          | string   | The unique name of the guardrail being executed.                   | `MathGuardrail` |
| `triggered`     | boolean  | Indicates whether the guardrail condition was met (and triggered). | `false`         |

#### Handoff spans
These spans represent the moment an agent attempts to delegate a task to another agent.
> **Handling Multiple Handoffs:** If the LLM attempts to hand off to multiple agents in a single turn, the `to_agent` attribute will only contain the name of the *first* agent in the list. The span will also be marked with an error status to indicate this ambiguity.

| **Attribute** | **Type** | **Description**                                        | **Example**  |
|---------------|----------|--------------------------------------------------------|--------------|
| `type`          | string   | The type of the span, identifying it as a handoff.     | `handoff`      |
| `from_agent`    | string   | The name of the agent initiating the handoff.          | `Assistant`    |
| `to_agent`      | string   | The name of the agent intended to receive the handoff. | `WeatherAgent` |

#### Function spans
These spans represent the execution of a tool (a Python function).
| **Attribute** | **Type** | **Description**                                           | **Example**                                |
|---------------|----------|-----------------------------------------------------------|--------------------------------------------|
| `type`          | string   | The type of the span, identifying it as a function.       | `function`                                   |
| `name`          | string   | The name of the function that was called.                 | `get_current_weather`                                |
| `input`         | string   | The JSON string of arguments passed to the function.      | `{"city":"Tel Aviv"}`                        |
| `output`        | string   | The string representation of the function's return value. | `The weather in Tel Aviv is 30°C and sunny.` |

#### Enriched LLM call spans
These attributes are added to the existing span to link LLM calls back to the responsible agent.
| **Attribute**            | **Type** | **Description**                                     | **Example**                                                                         |
|--------------------------|----------|-----------------------------------------------------|-------------------------------------------------------------------------------------|
| `gen_ai.agent.name`        | string   | The name of the agent that initiated this LLM call. | `Assistant`, `WeatherAgent`                                                                           |
