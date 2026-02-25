# LLM Tracekit - Claude Agent SDK

OpenTelemetry instrumentation for [Claude Agent SDK (claude-agent-sdk)](https://github.com/anthropics/claude-agent-sdk-python), the official Python SDK for building AI agents with Claude Code.

- **Interfaces:** Both `query()` (one-off) and `ClaudeSDKClient` (multi-turn, tools) are instrumented.

### Query vs client

| | `query()` | `ClaudeSDKClient` |
|--|-----------|-------------------|
| **Use case** | One-off call; new session each time | Multi-turn conversation; same session, optional tools |
| **Span** | One span per `query(...)` call | One span per turn (each `query()` + `receive_response()` pair) |
| **Prompt source** | `prompt` and `options` passed to `query()` | Current turn: prompt from `client.query(prompt)` stored on the client, then read when `receive_response()` is called; options from `client.options` |
| **Response** | Stream wrapped by `QueryStreamWrapper`; completion/usage from streamed `AssistantMessage` + `ResultMessage` | Stream wrapped by `ClientReceiveResponseWrapper`; same completion/usage from stream |

Both paths use the same attribute builders (e.g. `build_prompt_attributes_for_turn`, `build_completion_attributes`); only where the prompt and options come from differs.

## Installation

```bash
pip install "llm-tracekit-claude-agent-sdk"
```

## Usage

### Setting up tracing

You can use the `setup_export_to_coralogix` function to set up tracing and export traces to Coralogix:

```python
from llm_tracekit.claude_agent_sdk import setup_export_to_coralogix

setup_export_to_coralogix(
    service_name="ai-service",
    application_name="ai-application",
    subsystem_name="ai-subsystem",
    capture_content=True,
)
```

Alternatively, set up tracing manually:

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

To instrument all usage of the Claude Agent SDK, call the `instrument` method:

```python
from llm_tracekit.claude_agent_sdk import ClaudeAgentSDKInstrumentor

ClaudeAgentSDKInstrumentor().instrument()
```

### Enabling message content

Message content (prompts, completions, tool arguments) is not captured by default. To capture it:

- Pass `capture_content=True` when calling `setup_export_to_coralogix`, or
- Set the environment variable `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` to `true`.

### Uninstrument

```python
ClaudeAgentSDKInstrumentor().uninstrument()
```

### Full example (standalone query)

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions
from llm_tracekit.claude_agent_sdk import ClaudeAgentSDKInstrumentor, setup_export_to_coralogix

setup_export_to_coralogix(service_name="ai-service", capture_content=True)
ClaudeAgentSDKInstrumentor().instrument()

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

### Full example (ClaudeSDKClient, multi-turn)

```python
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from llm_tracekit.claude_agent_sdk import ClaudeAgentSDKInstrumentor, setup_export_to_coralogix

setup_export_to_coralogix(service_name="ai-service", application_name="app", subsystem_name="client", capture_content=True)
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

## Supported span attributes

The instrumentation is **stateless**: every attribute is derived from the current request and response only (no in-memory conversation state). Below is the full list of attributes that may be set on spans.

### Base (always set)

| Attribute | Type | Description |
| --------- | ---- | ----------- |
| `gen_ai.system` | string | `"claude.agent_sdk"` |
| `gen_ai.operation.name` | string | `"chat"` |

### Request (from options / current turn)

| Attribute | Type | When present |
| --------- | ---- | ------------- |
| `gen_ai.request.model` | string | When `ClaudeAgentOptions.model` is set |
| `gen_ai.request.user` | string | When `ClaudeAgentOptions.user` is set |
| `gen_ai.prompt.<n>.role` | string | Per message: `system` (if options have system_prompt), then `user` for the current turn only |
| `gen_ai.prompt.<n>.content` | string | When content capture is enabled (`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` or `setup_export_to_coralogix(..., capture_content=True)`) |

**Note:** For `ClaudeSDKClient`, only the **current turn** is in the request (system + current user message). Full conversation history is not available from the SDK, so earlier turns are not included.

### Request tools (when tools are allowed)

| Attribute | Type | When present |
| --------- | ---- | ------------- |
| `gen_ai.request.tools.<n>.type` | string | `"function"` for each entry in `options.allowed_tools` |
| `gen_ai.request.tools.<n>.function.name` | string | Tool name from `allowed_tools` |
| `gen_ai.request.tools.<n>.function.description` | string | Empty string (SDK exposes names only in `allowed_tools`) |

### Completion (from streamed response)

| Attribute | Type | When present |
| --------- | ---- | ------------- |
| `gen_ai.completion.0.role` | string | `"assistant"` |
| `gen_ai.completion.0.finish_reason` | string | `"stop"`, `"tool_calls"`, or `"error"` |
| `gen_ai.completion.0.content` | string | When content capture is enabled |
| `gen_ai.completion.0.tool_calls.<i>.id` | string | When the model returns tool use |
| `gen_ai.completion.0.tool_calls.<i>.type` | string | `"function"` |
| `gen_ai.completion.0.tool_calls.<i>.function.name` | string | Tool name |
| `gen_ai.completion.0.tool_calls.<i>.function.arguments` | string | JSON string when content capture is enabled |

### Response and usage (from ResultMessage)

| Attribute | Type | When present |
| --------- | ---- | ------------- |
| `gen_ai.response.model` | string | When `ResultMessage.model` is present |
| `gen_ai.usage.input_tokens` | int | When `ResultMessage.usage` has `input_tokens` |
| `gen_ai.usage.output_tokens` | int | When `ResultMessage.usage` has `output_tokens` |

### Library-specific (from ResultMessage)

| Attribute | Type | When present |
| --------- | ---- | ------------- |
| `gen_ai.claude_agent_sdk.result.duration_ms` | int | ResultMessage duration (ms) |
| `gen_ai.claude_agent_sdk.result.duration_api_ms` | int | ResultMessage API duration (ms) |
| `gen_ai.claude_agent_sdk.result.num_turns` | int | ResultMessage num_turns |
| `gen_ai.claude_agent_sdk.result.total_cost_usd` | float | ResultMessage total cost (USD) |
| `gen_ai.claude_agent_sdk.result.session_id` | string | ResultMessage session_id |

Indices: `<n>` = message or tool index (0, 1, 2, …); `<i>` = tool call index within that message.

## Limitations

- **ClaudeSDKClient**: Instrumentation is stateless; all span data is taken from the current request only. Full conversation history lives in the CLI subprocess and is **not exposed to Python by the Claude Agent SDK**; each turn's span therefore has `gen_ai.prompt.*` for system (from options) and the current user message only. This is a known limitation on Anthropic's side.

- **Sync APIs**: The SDK is async-only; there is no sync instrumentation.
