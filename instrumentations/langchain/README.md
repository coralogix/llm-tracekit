# LLM Tracekit LangChain

OpenTelemetry instrumentation for [LangChain](https://www.langchain.com/).

## Installation

```bash
pip install llm-tracekit-langchain
```

Or via the meta-package:

```bash
pip install llm-tracekit[langchain]
```

## Usage

```python
from llm_tracekit_core import setup_export_to_coralogix
from llm_tracekit_langchain import LangChainInstrumentor
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# Configure tracing
setup_export_to_coralogix(
    service_name="ai-service",
    application_name="ai-application",
    subsystem_name="ai-subsystem",
    capture_content=True,
)

# Activate instrumentation
LangChainInstrumentor().instrument()

# Use LangChain as normal
llm = ChatOpenAI(model="gpt-4o-mini")
response = llm.invoke([HumanMessage(content="Write a short poem.")])
```

### Supported Providers

The instrumentation automatically traces calls through LangChain to these providers:

- **OpenAI** via `langchain-openai`
- **AWS Bedrock** via `langchain-aws`

### Multi-turn Conversations

```python
from langchain_core.messages import HumanMessage, SystemMessage

conversation = [
    SystemMessage(content="You're a helpful assistant."),
    HumanMessage(content="Hello!"),
]

response = llm.invoke(conversation)
conversation.append(response)
conversation.append(HumanMessage(content="Tell me more"))

final_response = llm.invoke(conversation)
```

### Streaming Support

Streaming completions are fully supported:

```python
stream = llm.stream([HumanMessage(content="Count to 10")])
for chunk in stream:
    print(chunk.content, end="")
```

### Tool Calls

Function/tool calls are automatically traced:

```python
from langchain_core.tools import tool

@tool
def get_weather(location: str) -> str:
    """Get weather for a location."""
    return f"Weather in {location}: Sunny, 72°F"

tool_llm = llm.bind_tools([get_weather])
response = tool_llm.invoke([HumanMessage(content="What's the weather in Paris?")])
```

### Uninstrument

To disable instrumentation:

```python
LangChainInstrumentor().uninstrument()
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

### Request Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `gen_ai.request.model` | string | Requested model name |
| `gen_ai.request.temperature` | float | Temperature setting |
| `gen_ai.request.top_p` | float | Top-p (nucleus sampling) |
| `gen_ai.request.max_tokens` | int | Max tokens limit |

### Response Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `gen_ai.response.model` | string | Model used for response |
| `gen_ai.response.id` | string | Response ID |
| `gen_ai.usage.input_tokens` | int | Input token count |
| `gen_ai.usage.output_tokens` | int | Output token count |

## License

Apache License 2.0

