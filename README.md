# LLM Tracekit

OpenTelemetry instrumentations for LLM providers including [OpenAI](https://openai.com/), [AWS Bedrock](https://aws.amazon.com/bedrock/), [Google Gemini](https://ai.google.dev/), [LiteLLM](https://www.litellm.ai/), and the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/).

## Exporting Traces to Coralogix

### Setup

Set the following environment variables:

```bash
export CX_TOKEN="your-coralogix-api-key"
export CX_ENDPOINT="ingress.coralogix.com"  # or your regional endpoint
```

### Initialize the Exporter

Import `setup_export_to_coralogix` from your chosen instrumentation package:

```python
from llm_tracekit.openai import OpenAIInstrumentor, setup_export_to_coralogix

setup_export_to_coralogix(
    service_name="my-ai-service",
    application_name="my-application",
    subsystem_name="my-subsystem",
    capture_content=True,  # Enable to capture prompts and completions
)
OpenAIInstrumentor().instrument()
```

### Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `CX_TOKEN` | Coralogix API key | Yes |
| `CX_ENDPOINT` | Coralogix ingress endpoint | Yes |
| `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` | Set to `true` to capture prompts/completions | No |

## Installing Instrumentations

To instrument **OpenAI**, install:

```bash
pip install llm-tracekit-openai
```

To instrument **AWS Bedrock**, install:

```bash
pip install llm-tracekit-bedrock
```

To instrument **Google Gemini**, install:

```bash
pip install llm-tracekit-gemini
```

To instrument **LiteLLM**, install:

```bash
pip install llm-tracekit-litellm
```

To instrument **OpenAI Agents SDK** (Python 3.10+), install:

```bash
pip install llm-tracekit-openai-agents
```

To use **Coralogix Guardrails**, install:

```bash
pip install cx-guardrails
```

## Usage Examples

### OpenAI

```python
from llm_tracekit.openai import OpenAIInstrumentor, setup_export_to_coralogix
from openai import OpenAI

setup_export_to_coralogix(
    service_name="openai-service",
    application_name="my-app",
    subsystem_name="chat",
    capture_content=True,
)
OpenAIInstrumentor().instrument()

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### AWS Bedrock

```python
from llm_tracekit.bedrock import BedrockInstrumentor, setup_export_to_coralogix
import boto3

setup_export_to_coralogix(
    service_name="bedrock-service",
    application_name="my-app",
    subsystem_name="chat",
    capture_content=True,
)
BedrockInstrumentor().instrument()

client = boto3.client("bedrock-runtime", region_name="us-east-1")
response = client.converse(
    modelId="anthropic.claude-3-sonnet-20240229-v1:0",
    messages=[{"role": "user", "content": [{"text": "Hello!"}]}]

## Package Structure

| Package | Description |
|---------|-------------|
| [`llm-tracekit-openai`](instrumentations/openai/) | OpenAI Chat Completions instrumentation |
| [`llm-tracekit-bedrock`](instrumentations/bedrock/) | AWS Bedrock instrumentation |
| [`llm-tracekit-gemini`](instrumentations/gemini/) | Google Gemini instrumentation |
| [`llm-tracekit-litellm`](instrumentations/litellm/) | LiteLLM instrumentation |
| [`llm-tracekit-openai-agents`](instrumentations/openai_agents/) | OpenAI Agents SDK instrumentation |
| [`cx-guardrails`](guardrails/) | Coralogix Guardrails SDK |

## Documentation

See individual package READMEs for detailed documentation:

- **OpenAI**: [instrumentations/openai/README.md](instrumentations/openai/README.md)
- **Bedrock**: [instrumentations/bedrock/README.md](instrumentations/bedrock/README.md)
- **Gemini**: [instrumentations/gemini/README.md](instrumentations/gemini/README.md)
- **LiteLLM**: [instrumentations/litellm/README.md](instrumentations/litellm/README.md)
- **OpenAI Agents**: [instrumentations/openai_agents/README.md](instrumentations/openai_agents/README.md)
- **Guardrails**: [guardrails/README.md](guardrails/README.md)

## License

Apache License 2.0
