# LLM Tracekit

Open-source observability for your LLM application, based on OpenTelemetry.

LLM Tracekit is a set of OpenTelemetry instrumentations that gives you complete observability over your LLM application. Because it uses OpenTelemetry under the hood, it can be connected to your existing observability solutions - Coralogix, Datadog, Honeycomb, and others.

## 🚀 Getting Started

Install the instrumentation for your LLM provider:

```bash
pip install llm-tracekit-openai       # For OpenAI
pip install llm-tracekit-bedrock      # For AWS Bedrock
pip install llm-tracekit-gemini       # For Google Gemini
pip install llm-tracekit-litellm      # For LiteLLM
pip install llm-tracekit-langchain    # For LangChain
pip install llm-tracekit-openai_agents # For OpenAI Agents SDK
```

Then instrument your code:

```python
from llm_tracekit.openai import OpenAIInstrumentor, setup_export_to_coralogix

setup_export_to_coralogix(
    service_name="my-ai-service",
    capture_content=True,
)

OpenAIInstrumentor().instrument()

from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

## 🪗 What do we instrument?    

### LLM Providers

| Provider | Package | Instrumentor |
|----------|---------|--------------|
| [OpenAI](https://openai.com/) | `llm-tracekit-openai` | `OpenAIInstrumentor` |
| [AWS Bedrock](https://aws.amazon.com/bedrock/) | `llm-tracekit-bedrock` | `BedrockInstrumentor` |
| [Google Gemini](https://ai.google.dev/) | `llm-tracekit-gemini` | `GeminiInstrumentor` |

### Frameworks

| Framework | Package | Instrumentor |
|-----------|---------|--------------|
| [LiteLLM](https://github.com/BerriAI/litellm) | `llm-tracekit-litellm` | `LiteLLMInstrumentor` |
| [LangChain](https://www.langchain.com/) | `llm-tracekit-langchain` | `LangChainInstrumentor` |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) | `llm-tracekit-openai_agents` | `OpenAIAgentsInstrumentor` |


## 📖 Usage

### Setting up tracing

#### Export to Coralogix

```python
from llm_tracekit.openai import setup_export_to_coralogix

setup_export_to_coralogix(
    service_name="ai-service",
    application_name="ai-application",
    subsystem_name="ai-subsystem",
    capture_content=True,
)
```

## 🛡️ Guardrails

LLM Tracekit also includes **Coralogix Guardrails** - a client for protecting your LLM applications with content moderation, PII detection, prompt injection detection, and more.

See the [Guardrails documentation](./guardrails/README.md) for details.

## 📚 Documentation

For detailed documentation on each instrumentation, see the individual READMEs:

- [OpenAI](./instrumentations/openai/README.md)
- [AWS Bedrock](./instrumentations/bedrock/README.md)
- [Google Gemini](./instrumentations/gemini/README.md)
- [LiteLLM](./instrumentations/litellm/README.md)
- [LangChain](./instrumentations/langchain/README.md)
- [OpenAI Agents SDK](./instrumentations/openai_agents/README.md)

## 📜 License

Apache 2.0 - See [LICENSE](./LICENSE) for details.
