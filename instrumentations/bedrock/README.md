# LLM Tracekit Bedrock

OpenTelemetry instrumentation for [AWS Bedrock](https://aws.amazon.com/bedrock/) APIs including Converse, InvokeModel, and InvokeAgent.

## Installation

```bash
pip install llm-tracekit-bedrock
```

## Usage

```python
import boto3
from llm_tracekit.bedrock import BedrockInstrumentor, setup_export_to_coralogix

# Configure tracing
setup_export_to_coralogix(
    service_name="ai-service",
    application_name="ai-application",
    subsystem_name="ai-subsystem",
    capture_content=True,
)

# Activate instrumentation
BedrockInstrumentor().instrument()

# Use Bedrock as normal
client = boto3.client("bedrock-runtime")
response = client.converse(
    modelId="anthropic.claude-3-sonnet-20240229-v1:0",
    messages=[{"role": "user", "content": [{"text": "Hello!"}]}],
)
```

### Supported APIs

- **Converse**: `bedrock-runtime.converse()` and `converse_stream()`
- **InvokeModel**: `bedrock-runtime.invoke_model()` and `invoke_model_with_response_stream()`
- **InvokeAgent**: `bedrock-agent-runtime.invoke_agent()`

### Uninstrument

To disable instrumentation:

```python
BedrockInstrumentor().uninstrument()
```

## Span Attributes

### Standard GenAI Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `gen_ai.prompt.<n>.role` | string | Message role |
| `gen_ai.prompt.<n>.content` | string | Message content |
| `gen_ai.completion.<c>.role` | string | Response role |
| `gen_ai.completion.<c>.content` | string | Response content |
| `gen_ai.completion.<c>.finish_reason` | string | Completion finish reason |

### Bedrock-specific Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `gen_ai.bedrock.agent_alias.id` | string | Agent alias ID for `invoke_agent` |
| `gen_ai.bedrock.request.tools.<n>.function.name` | string | Function name |
| `gen_ai.bedrock.request.tools.<n>.function.description` | string | Function description |
| `gen_ai.bedrock.request.tools.<n>.function.parameters` | string | Function parameters schema |

## License

Apache License 2.0

