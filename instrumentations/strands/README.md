# llm-tracekit-strands

OpenTelemetry instrumentation for [Strands Agents SDK](https://github.com/strands-agents/sdk-python).

## Overview

Strands Agents SDK already includes built-in OpenTelemetry tracing. This instrumentation enriches those existing spans with additional GenAI semantic convention attributes for:

- **Prompt messages** (`gen_ai.prompt.*`) - Full conversation history with roles, content, and tool calls
- **Completion choices** (`gen_ai.completion.*`) - Model responses with finish reasons and tool calls
- **Tool definitions** (`gen_ai.request.tools.*`) - Available tools with names, descriptions, and parameters
- **User identification** (`gen_ai.request.user`) - User ID from model configuration

## Installation

```bash
pip install llm-tracekit-strands
```

## Usage

```python
from llm_tracekit.strands import StrandsInstrumentor

# Enable instrumentation (call before creating agents)
StrandsInstrumentor().instrument()

# Use Strands normally
from strands import Agent

agent = Agent()
response = agent("Hello, how are you?")
```

## Configuration

### Content Capture

By default, message content is not captured. To enable content capture:

```python
import os
os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

from llm_tracekit.strands import StrandsInstrumentor
StrandsInstrumentor().instrument()
```

Or programmatically:

```python
from llm_tracekit.core import enable_capture_content
from llm_tracekit.strands import StrandsInstrumentor

enable_capture_content()
StrandsInstrumentor().instrument()
```

### Strands Telemetry Setup

Strands has its own telemetry configuration. You can use either Strands' built-in setup or configure OpenTelemetry directly:

```python
# Option 1: Use Strands' built-in telemetry
from strands.telemetry import StrandsTelemetry

StrandsTelemetry().setup_console_exporter()

# Option 2: Configure OpenTelemetry directly
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
```

## Attributes Added

### Prompt Messages (input to model)

| Attribute | Description |
|-----------|-------------|
| `gen_ai.prompt.<n>.role` | Role of message author (user, assistant, system, tool) |
| `gen_ai.prompt.<n>.content` | Message content (when content capture enabled) |
| `gen_ai.prompt.<n>.tool_call_id` | ID of tool call this result is for (role=tool) |
| `gen_ai.prompt.<n>.tool_calls.<i>.id` | Tool call ID |
| `gen_ai.prompt.<n>.tool_calls.<i>.type` | Tool call type (function) |
| `gen_ai.prompt.<n>.tool_calls.<i>.function.name` | Function name |
| `gen_ai.prompt.<n>.tool_calls.<i>.function.arguments` | Function arguments JSON |

### Completion Choices (output from model)

| Attribute | Description |
|-----------|-------------|
| `gen_ai.completion.0.role` | Role of responder (assistant) |
| `gen_ai.completion.0.finish_reason` | Why generation stopped (stop, tool_calls, length) |
| `gen_ai.completion.0.content` | Response content (when content capture enabled) |
| `gen_ai.completion.0.tool_calls.<i>.*` | Tool calls requested by model |

### Tool Definitions (when content capture enabled)

| Attribute | Description |
|-----------|-------------|
| `gen_ai.request.tools.<n>.type` | Tool type (function) |
| `gen_ai.request.tools.<n>.function.name` | Function name |
| `gen_ai.request.tools.<n>.function.description` | Function description |
| `gen_ai.request.tools.<n>.function.parameters` | JSON schema of parameters |

### User Identification

| Attribute | Description |
|-----------|-------------|
| `gen_ai.request.user` | User identifier from model configuration |

To capture user identification, pass the `user` parameter in your model's `params` configuration:

```python
from strands.models.openai import OpenAIModel

model = OpenAIModel(
    model_id="gpt-4o",
    params={"user": "user@example.com"}
)

agent = Agent(model=model)
```

This works with any Strands model that supports the `user` parameter (OpenAI, Anthropic, etc.).

## License

Apache-2.0
