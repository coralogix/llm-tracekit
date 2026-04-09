# LLM Tracekit - LangGraph

OpenTelemetry instrumentation for [LangGraph](https://langchain-ai.github.io/langgraph/), focused on **span structure** and **node attributes** for graph runs. Use it together with LangChain, OpenAI, or other LLM instrumentors for full observability.

## Span structure (3 levels)

1. **Global span** — One per graph invocation. Starts when execution leaves START and ends when it reaches END. Span name: `"LangGraph"`.
2. **Node spans** — One per graph node execution, as **children** of the global span. Span name: `"LangGraph Node <node_name>"`. Each node span has two attributes: **node name** (`gen_ai.langgraph.node`) and **step number** (`gen_ai.langgraph.step`, when provided by LangGraph). The node span is the **current span** while the node runs, so any LLM calls inside the node are traced by other instrumentors as **children of that node span**. **Tool nodes** (nodes that only run tools and do not call an LLM) get a node span too; they have no LLM child spans.
3. **LLM spans** — Created by other instrumentors (LangChain, OpenAI, Gemini, etc.) when a node calls an LLM. They appear as children of the corresponding node span.

Resulting trace: **LangGraph** → **LangGraph Node …** → **chat/completion** (from LangChain/OpenAI/etc.) where the node runs an LLM; tool-only nodes appear as **LangGraph Node &lt;name&gt;** with no child.

## Installation

```bash
pip install "llm-tracekit-langgraph"
```

## Usage

### Setting up tracing

You can use the `setup_export_to_coralogix` function to setup tracing and export traces to Coralogix:

```python
from llm_tracekit.langgraph import setup_export_to_coralogix

setup_export_to_coralogix(
    service_name="ai-service",
    application_name="ai-application",
    subsystem_name="ai-subsystem",
)
```

Alternatively, set up tracing manually with your preferred `TracerProvider` and exporter.

### Activation

To instrument all LangGraph runs that use LangChain's callback manager:

```python
from llm_tracekit.langgraph import LangGraphInstrumentor

LangGraphInstrumentor().instrument()
```

### Capturing LLM call spans

This instrumentor only creates the **graph-level** and **node-level** spans above. It does **not** create spans for LLM calls. To get LLM spans (model, token usage, tool calls, etc.) as **children of the node span** that runs the LLM:

- Use **LangChain**: `llm-tracekit-langchain` and `LangChainInstrumentor().instrument(...)` in addition to `LangGraphInstrumentor().instrument(...)`. Both can run together; LangChain will create child spans under the current (node) span.
- Or use **provider-specific** instrumentors (OpenAI, Bedrock, etc.) instead of or alongside LangChain.

Install and activate the extra instrumentor(s) you need. The same tracer provider can be passed to all of them. LLM spans will appear under the correct node span because the node span is set as the current span while the node runs.

### Uninstrument

```python
LangGraphInstrumentor().uninstrument()
```

### Full example

Minimal graph (no LLM):

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from llm_tracekit.langgraph import LangGraphInstrumentor, setup_export_to_coralogix

setup_export_to_coralogix(service_name="ai-service")

LangGraphInstrumentor().instrument()

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
## Manual handler

You can also add the handler explicitly when invoking a graph (e.g. for testing or when not using the instrumentor):

```python
from llm_tracekit.langgraph.callback import LangGraphCallbackHandler

tracer = tracer_provider.get_tracer(__name__)
handler = LangGraphCallbackHandler(tracer=tracer)
result = app.invoke(initial_state, config={"callbacks": [handler], "configurable": {"thread_id": "1"}})
```

## Semantic Conventions

### Node span attributes
| Attribute | Type | Description | Examples |
| --------- | ---- | ----------- | -------- |
| `gen_ai.langgraph.node` | string | The name of the LangGraph node being executed | `agent`, `tools` |
| `gen_ai.langgraph.step` | int | Step counter for this node execution within the graph run | `1`, `2` |
| `gen_ai.request.user` | string | A unique identifier representing the end-user (from `config={"metadata": {"user": "..."}}` or `config={"configurable": {"user": "..."}}`) | `user@company.com` |

### Passing user identity

Pass the user identifier in either the `metadata` dict or the `configurable` dict of the LangGraph config:

```python
# Option 1: via metadata (preferred)
result = app.invoke(
    {"messages": [HumanMessage(content="Hello")]},
    config={
        "configurable": {"thread_id": "1"},
        "metadata": {"user": "user@company.com"},
    },
)

# Option 2: via configurable (also supported)
result = app.invoke(
    {"messages": [HumanMessage(content="Hello")]},
    config={
        "configurable": {"thread_id": "1", "user": "user@company.com"},
    },
)
```
