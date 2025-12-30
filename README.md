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

```python
from llm_tracekit_core import setup_export_to_coralogix

setup_export_to_coralogix(
    service_name="my-ai-service",
    application_name="my-application",
    subsystem_name="my-subsystem",
    capture_content=True,  # Enable to capture prompts and completions
)
```

### Capturing Message Content

By default, prompts and completions are **not captured** to protect sensitive data. To enable:

```python
# Option 1: Via setup function
setup_export_to_coralogix(
    service_name="my-service",
    application_name="my-app",
    subsystem_name="my-subsystem",
    capture_content=True,
)

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
pip install llm-tracekit-guardrails
```

## Usage Examples

### OpenAI

```python
from llm_tracekit_openai import OpenAIInstrumentor, setup_export_to_coralogix
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
from llm_tracekit_bedrock import BedrockInstrumentor, setup_export_to_coralogix
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
)
```

### Google Gemini

```python
from llm_tracekit_gemini import GeminiInstrumentor, setup_export_to_coralogix
from google import genai

setup_export_to_coralogix(
    service_name="gemini-service",
    application_name="my-app",
    subsystem_name="chat",
    capture_content=True,
)
GeminiInstrumentor().instrument()

client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="Hello!"
)
```

### LiteLLM

```python
from llm_tracekit_litellm import LiteLLMInstrumentor, setup_export_to_coralogix
import litellm

setup_export_to_coralogix(
    service_name="litellm-service",
    application_name="my-app",
    subsystem_name="chat",
    capture_content=True,
)
LiteLLMInstrumentor().instrument()

response = litellm.completion(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### OpenAI Agents SDK

```python
from llm_tracekit_openai_agents import OpenAIAgentsInstrumentor, setup_export_to_coralogix
from agents import Agent, Runner

setup_export_to_coralogix(
    service_name="agents-service",
    application_name="my-app",
    subsystem_name="agents",
    capture_content=True,
)
OpenAIAgentsInstrumentor().instrument()

agent = Agent(name="Assistant", instructions="You are a helpful assistant.")
result = Runner.run_sync(agent, "Hello!")
```

## Package Structure

| Package | Description |
|---------|-------------|
| [`llm-tracekit-core`](core/) | Core utilities, span builders, and Coralogix export helpers |
| [`llm-tracekit-openai`](instrumentations/openai/) | OpenAI Chat Completions instrumentation |
| [`llm-tracekit-bedrock`](instrumentations/bedrock/) | AWS Bedrock instrumentation |
| [`llm-tracekit-gemini`](instrumentations/gemini/) | Google Gemini instrumentation |
| [`llm-tracekit-litellm`](instrumentations/litellm/) | LiteLLM instrumentation |
| [`llm-tracekit-openai-agents`](instrumentations/openai_agents/) | OpenAI Agents SDK instrumentation |
| [`llm-tracekit-guardrails`](guardrails/) | Coralogix Guardrails SDK |

## Documentation

See individual package READMEs for detailed documentation:

- **Core**: [core/README.md](core/README.md)
- **OpenAI**: [instrumentations/openai/README.md](instrumentations/openai/README.md)
- **Bedrock**: [instrumentations/bedrock/README.md](instrumentations/bedrock/README.md)
- **Gemini**: [instrumentations/gemini/README.md](instrumentations/gemini/README.md)
- **LiteLLM**: [instrumentations/litellm/README.md](instrumentations/litellm/README.md)
- **OpenAI Agents**: [instrumentations/openai_agents/README.md](instrumentations/openai_agents/README.md)
- **Guardrails**: [guardrails/README.md](guardrails/README.md)

## License

Apache License 2.0
