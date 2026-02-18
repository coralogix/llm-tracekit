# LLM Tracekit - LangGraph

OpenTelemetry instrumentation for [LangGraph](https://langchain-ai.github.io/langgraph/), designed to trace graph node executions and simplify debugging of stateful, multi-step LLM workflows.

This instrumentation creates **one span per graph node**. It does not create spans for individual LLM calls. To capture LLM spans (model name, token usage, tool calls, etc.) when a node invokes an LLM, use the **LangChain** (or provider-specific) instrumentor in addition to this one—see [Capturing LLM call spans](#capturing-llm-call-spans).

## Installation

```bash
pip install "llm-tracekit-langgraph"
```

## Usage

This section describes how to set up instrumentation for LangGraph.

### Setting up tracing

You can use the `setup_export_to_coralogix` function to setup tracing and export traces to Coralogix:

```python
from llm_tracekit.langgraph import setup_export_to_coralogix

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

To instrument all LangGraph runs that use LangChain's callback manager, call the `instrument` method:

```python
from llm_tracekit.langgraph import LangGraphInstrumentor

LangGraphInstrumentor().instrument()
```

### Capturing LLM call spans

This instrumentor only traces **graph nodes**. When a node calls an LLM (e.g. via LangChain's `ChatOpenAI`), that call is not turned into a span by the LangGraph instrumentor. To get full LLM observability—model name, token usage, request/response details, tool calls—you must use another instrumentor for the LLM layer:

- **LangChain**: use `llm-tracekit-langchain` and call `LangChainInstrumentor().instrument(...)` in addition to `LangGraphInstrumentor().instrument(...)`. Both can run together; LangChain will create child spans under the corresponding LangGraph node span.
- **Provider-specific** (e.g. OpenAI, Bedrock): you can use those instrumentors instead of or alongside LangChain, depending on your stack.

Install and activate the extra instrumentor(s) you need (e.g. `pip install "llm-tracekit-langchain"` and instrument both). The same tracer provider can be passed to all of them.

### Enabling message content

When `capture_content` is enabled, **LangGraph node spans** include `gen_ai.prompt.*` and `gen_ai.completion.*` from the node's input/output state (e.g. the `messages` field). Model name, token usage, and tool-call details appear on **LLM spans** created by the LangChain (or provider) instrumentor—see [Capturing LLM call spans](#capturing-llm-call-spans).

To enable content capture:

* Pass `capture_content=True` when calling `setup_export_to_coralogix`
* Set the environment variable `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` to `true`

### Uninstrument

To uninstrument, call the `uninstrument` method:

```python
LangGraphInstrumentor().uninstrument()
```

### Full Example

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from llm_tracekit.langgraph import LangGraphInstrumentor, setup_export_to_coralogix

# Optional: Configure sending spans to Coralogix
setup_export_to_coralogix(
    service_name="ai-service",
    capture_content=True,
)

# Activate instrumentation
LangGraphInstrumentor().instrument()

# Build a minimal graph
def node_a(state: dict) -> dict:
    return {"messages": state.get("messages", []) + ["A"]}

def node_b(state: dict) -> dict:
    return {"messages": state.get("messages", []) + ["B"]}

graph = StateGraph(dict)
graph.add_node("a", node_a)
graph.add_node("b", node_b)
graph.add_edge(START, "a")
graph.add_edge("a", "b")
graph.add_edge("b", END)

app = graph.compile(checkpointer=MemorySaver())
result = app.invoke({"messages": []}, config={"configurable": {"thread_id": "1"}})
```

## Semantic Conventions

### LangGraph node span attributes

| Attribute | Type | Description | Examples |
| --------- | ---- | ----------- | -------- |
| `gen_ai.operation.name` | string | Operation name | `langgraph.node` |
| `gen_ai.langgraph.node` | string | Name of the graph node | `ingest_messages`, `agent` |
| `gen_ai.langgraph.step` | integer | Step index in the run | `1`, `2` |
| `gen_ai.langgraph.triggers` | list | Triggers that started the node | `["start"]` |
| `gen_ai.langgraph.path` | string | Path of the node in the graph | `root.ingest_messages` |
| `gen_ai.langgraph.checkpoint_ns` | string | Checkpoint namespace | `namespace` |
| `gen_ai.thread.id` | string | Thread/conversation ID | `thread-42` |
| `gen_ai.task.id` | string | Task ID | `task-007` |
| `gen_ai.langgraph.status` | string | Node outcome | `success`, `error` |
| `gen_ai.tags` | list | Tags from the run | `["alpha"]` |
| `langgraph.metadata.<key>` | any | Custom metadata keys | User-defined |

### Prompt and completion attributes (when content capture is enabled)

When `capture_content` is enabled, node spans include message content from the node's **input state** (e.g. `messages` before the node runs) and **output state** (e.g. `messages` after the node runs). These are derived from the `messages` field in graph state; index is the message position in that list.

| Attribute | Type | Description | Examples |
| --------- | ---- | ----------- | -------- |
| `gen_ai.prompt.<index>.role` | string | Role of message at index in input state | `user`, `assistant`, `system` |
| `gen_ai.prompt.<index>.content` | string | Content of message at index in input state | `Hello, world` |
| `gen_ai.completion.<index>.role` | string | Role of message at index in output state | `assistant` |
| `gen_ai.completion.<index>.content` | string | Content of message at index in output state | `Hi there!` |

### Tool attributes (when tools are present on a node)

| Attribute | Type | Description |
| --------- | ---- | ----------- |
| `gen_ai.request.tools.<index>.type` | string | Tool type (e.g. `function`) |
| `gen_ai.request.tools.<index>.function.name` | string | Tool function name |
| `gen_ai.request.tools.<index>.function.description` | string | Tool description |
| `gen_ai.request.tools.<index>.function.parameters` | string | JSON schema of parameters |
