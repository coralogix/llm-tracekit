# LLM Tracekit - Claude Agent SDK
OpenTelemetry instrumentation for [Claude Agent SDK (claude-agent-sdk)](https://github.com/anthropics/claude-agent-sdk-python), the official Python SDK for building AI agents with Claude Code.

## Installation
```bash
pip install "llm-tracekit-claude-agent-sdk"
```


## Usage
This section describes how to set up instrumentation for the Claude Agent SDK.

### Setting up tracing
You can use the `setup_export_to_coralogix` function to setup tracing and export traces to Coralogix
```python
from llm_tracekit.core import setup_export_to_coralogix

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
To instrument all usage of the Claude Agent SDK, call the `instrument` method
```python
from llm_tracekit.claude_agent_sdk import ClaudeAgentSDKInstrumentor

instrumentor = ClaudeAgentSDKInstrumentor()
instrumentor.instrument()
```

Both `query()` (one-off calls) and `ClaudeSDKClient` (multi-turn sessions) are instrumented automatically.

### Enabling message content
Message content such as the contents of the prompt, completion, and tool arguments are not captured by default.
To capture message content as span attributes, do one of the following:
* Pass `capture_content=True` when calling `setup_export_to_coralogix`
* Set the environment variable `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` to `true`

Most Coralogix AI evaluations will not work without message contents, so it is highly recommended to enable capturing.

### Uninstrument
To uninstrument, call the `uninstrument` method:
```python
instrumentor.uninstrument()
```

### Full Example (standalone query)
```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions
from llm_tracekit.core import setup_export_to_coralogix
from llm_tracekit.claude_agent_sdk import ClaudeAgentSDKInstrumentor

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
ClaudeAgentSDKInstrumentor().instrument()

# Example usage
async def main():
    async for message in query(
        prompt="What is the capital of France?",
        options=ClaudeAgentOptions(system_prompt="You are a helpful assistant."),
    ):
        if type(message).__name__ == "AssistantMessage":
            for block in message.content:
                if type(block).__name__ == "TextBlock":
                    print(block.text)

asyncio.run(main())
```

### Full Example (ClaudeSDKClient, multi-turn)
```python
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from llm_tracekit.core import setup_export_to_coralogix
from llm_tracekit.claude_agent_sdk import ClaudeAgentSDKInstrumentor

setup_export_to_coralogix(
    service_name="ai-service",
    application_name="ai-application",
    subsystem_name="ai-subsystem",
    capture_content=True,
)

ClaudeAgentSDKInstrumentor().instrument()

async def main():
    async with ClaudeSDKClient(ClaudeAgentOptions()) as client:
        await client.query("Hello!")
        async for msg in client.receive_response():
            if type(msg).__name__ == "AssistantMessage":
                for block in msg.content:
                    if type(block).__name__ == "TextBlock":
                        print(block.text)
        await client.query("What did I just say?")
        async for msg in client.receive_response():
            if type(msg).__name__ == "AssistantMessage":
                for block in msg.content:
                    if type(block).__name__ == "TextBlock":
                        print(block.text)

asyncio.run(main())
```

## Semantic Conventions
| Attribute | Type | Description | Examples
| --------- | ---- | ----------- | --------
| `gen_ai.system` | string | Identifies the instrumented SDK | `claude.agent_sdk`
| `gen_ai.operation.name` | string | The type of GenAI operation | `chat`
| `gen_ai.request.model` | string | Model name requested via options | `claude-3-5-sonnet-20241022`
| `gen_ai.request.user` | string | End-user identifier from options | `user@example.com`
| `gen_ai.request.tools.<n>.type` | string | Type of each allowed tool | `function`
| `gen_ai.request.tools.<n>.function.name` | string | Name of each allowed tool | `bash`
| `gen_ai.prompt.<message_number>.role` | string | Role of message author for prompt message `<message_number>` | `system`, `user`
| `gen_ai.prompt.<message_number>.content` | string | Contents of prompt message `<message_number>` | `What is the capital of France?`
| `gen_ai.completion.<choice_number>.role` | string | Role of message author for choice `<choice_number>` in model response | `assistant`
| `gen_ai.completion.<choice_number>.finish_reason` | string | Finish reason for choice `<choice_number>` in model response | `stop`, `tool_calls`, `error`
| `gen_ai.completion.<choice_number>.content` | string | Contents of choice `<choice_number>` in model response | `The capital of France is Paris.`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number>.id` | string | ID of tool call in choice `<choice_number>` | `toolu_01A09q90qw90lq917835lq9`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number>.type` | string | Type of tool call in choice `<choice_number>` | `function`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number>.function.name` | string | Name of the function used in tool call in choice `<choice_number>` | `bash`
| `gen_ai.completion.<choice_number>.tool_calls.<tool_call_number>.function.arguments` | string | Arguments of the function used in tool call in choice `<choice_number>` | `{"command": "ls -la"}`
| `gen_ai.usage.input_tokens` | int | Number of input tokens consumed | `42`
| `gen_ai.usage.output_tokens` | int | Number of output tokens generated | `128`

### Claude Agent SDK specific attributes
| Attribute | Type | Description | Examples
| --------- | ---- | ----------- | --------
| `gen_ai.claude_agent_sdk.result.duration_ms` | int | Total wall-clock duration of the agent run (ms) | `4200`
| `gen_ai.claude_agent_sdk.result.duration_api_ms` | int | Time spent in API calls during the agent run (ms) | `3800`
| `gen_ai.claude_agent_sdk.result.num_turns` | int | Number of agentic turns taken | `3`
| `gen_ai.claude_agent_sdk.result.total_cost_usd` | float | Estimated cost of the run in USD | `0.0042`
| `gen_ai.claude_agent_sdk.result.session_id` | string | Session ID assigned by the SDK subprocess | `sess_01Abc...`

## Metrics

The instrumentation records the following OpenTelemetry metrics:

| Metric | Type | Description |
| ------ | ---- | ----------- |
| `gen_ai.client.operation.duration` | Histogram | Duration of the operation in seconds |
| `gen_ai.client.token.usage` | Histogram | Token usage per request, with `gen_ai.token.type` attribute (`input` or `completion`) |

## Limitations
- **Conversation history**: Each span captures only the current turn (system prompt + current user message). The full conversation history lives inside the CLI subprocess and is not exposed to Python by the SDK.
- **`gen_ai.response.model`**: Not set — the SDK's `ResultMessage` does not expose the model name used inside the subprocess.
- **Tool schemas**: `gen_ai.request.tools.<n>.function.description` is always an empty string and `.function.parameters` is never set, because `ClaudeAgentOptions.allowed_tools` contains only tool names without schema definitions.
- **`gen_ai.request.user` on Windows**: The instrumentation correctly extracts the `user` field, but the SDK passes it to `subprocess.Popen(user=...)`, which is unsupported on Windows. Using this option on Windows raises a `ValueError` from the SDK itself. This works correctly on Linux/macOS.
- **Sync APIs**: The SDK is async-only; there is no sync instrumentation.
