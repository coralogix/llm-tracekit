# Data Model: Rewrite Strands Agents Tests

This feature is a test rewrite — it does not introduce new data entities. The data model documents the existing span hierarchy and attributes that the tests validate.

## Span Hierarchy

```
invoke_agent {agent_name}          (SpanKind.INTERNAL)
├── cycle {cycle_id}               (SpanKind.INTERNAL)
│   ├── chat {model_id}            (SpanKind.CLIENT)
│   └── execute_tool {tool_name}   (SpanKind.INTERNAL)
├── cycle {cycle_id}               (SpanKind.INTERNAL)
│   └── chat {model_id}            (SpanKind.CLIENT)
└── ...
```

## Span Attributes

### Agent Span (`invoke_agent`)

| Attribute | Type | Required | Value |
|-----------|------|----------|-------|
| `gen_ai.system` | string | Yes | `"strands"` |
| `gen_ai.operation_name` | string | Yes | `"invoke_agent"` |
| `gen_ai.agent.name` | string | Yes | Agent name |
| `gen_ai.request.model` | string | Yes | Model ID |
| `gen_ai.usage.input_tokens` | int | After completion | Aggregated across cycles |
| `gen_ai.usage.output_tokens` | int | After completion | Aggregated across cycles |

### Chat Span (`chat`)

| Attribute | Type | Required | Value |
|-----------|------|----------|-------|
| `gen_ai.system` | string | Yes | `"strands"` |
| `gen_ai.operation_name` | string | Yes | `"chat"` |
| `gen_ai.request.model` | string | Yes | Model ID |
| `gen_ai.response.model` | string | After response | Model ID from response |
| `gen_ai.response.finish_reasons` | tuple | After response | e.g., `("end_turn",)` |
| `gen_ai.usage.input_tokens` | int | After response | Per-call tokens |
| `gen_ai.usage.output_tokens` | int | After response | Per-call tokens |
| `gen_ai.prompt.{i}.role` | string | Content capture | Message role |
| `gen_ai.prompt.{i}.content` | string | Content capture | Message text |
| `gen_ai.completion.{i}.role` | string | Content capture | `"assistant"` |
| `gen_ai.completion.{i}.content` | string | Content capture | Response text |
| `gen_ai.completion.{i}.finish_reason` | string | Content capture | Finish reason |
| `gen_ai.completion.{i}.tool_calls.{j}.function.name` | string | Tool call | Tool name |

### Tool Span (`execute_tool`)

| Attribute | Type | Required | Value |
|-----------|------|----------|-------|
| `gen_ai.system` | string | Yes | `"strands"` |
| `gen_ai.operation_name` | string | Yes | `"execute_tool"` |
| `name` | string | Yes | Tool function name |
| `type` | string | Yes | `"function"` or `"mcp"` |
| `gen_ai.tool.status` | string | After execution | `"success"` or `"error"` |
| `input` | string | Content capture | JSON tool input |
| `output` | string | Content capture | JSON tool output |

## VCR Cassette Structure

Each cassette is a YAML file with the following structure:

```yaml
interactions:
- request:
    body: {string: "..."}
    headers: {filtered}
    method: POST
    uri: https://bedrock-runtime.us-east-1.amazonaws.com/...
  response:
    body: {string: "base64-encoded-event-stream"}
    headers:
      Content-Type: [application/vnd.amazon.eventstream]
      x-vcr-base64: ["yes"]
    status: {code: 200, message: OK}
version: 1
```

## Metrics

| Metric Name | Type | Attributes |
|-------------|------|------------|
| `gen_ai.client.operation.duration` | Histogram | `gen_ai.operation_name`, `gen_ai.system` |
| `gen_ai.client.token.usage` | Histogram | `gen_ai.operation_name`, `gen_ai.system`, `gen_ai.token.type` |
