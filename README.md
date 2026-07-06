# LLM Tracekit

[![Awesome Strands Agents](https://img.shields.io/badge/Awesome-Strands%20Agents-00FF77?style=flat-square&logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjkwIiBoZWlnaHQ9IjQ2MyIgdmlld0JveD0iMCAwIDI5MCA0NjMiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik05Ny4yOTAyIDUyLjc4ODRDODUuMDY3NCA0OS4xNjY3IDcyLjIyMzQgNTYuMTM4OSA2OC42MDE3IDY4LjM2MTZDNjQuOTgwMSA4MC41ODQzIDcxLjk1MjQgOTMuNDI4MyA4NC4xNzQ5IDk3LjA1MDFMMjM1LjExNyAxMzkuNzc1QzI0NS4yMjMgMTQyLjc2OSAyNDYuMzU3IDE1Ni42MjggMjM2Ljg3NCAxNjEuMjI2TDMyLjU0NiAyNjAuMjkxQy0xNC45NDM5IDI4My4zMTYgLTkuMTYxMDcgMzUyLjc0IDQxLjQ4MzUgMzY3LjU5MUwxODkuNTUxIDQxMS4wMDlMMTkwLjEyNSA0MTEuMTY5QzIwMi4xODMgNDE0LjM3NiAyMTQuNjY1IDQwNy4zOTYgMjE4LjE5NiAzOTUuMzU1QzIyMS43ODQgMzgzLjEyMiAyMTQuNzc0IDM3MC4yOTYgMjAyLjU0MSAzNjYuNzA5TDU0LjQ3MzggMzIzLjI5MUM0NC4zNDQ3IDMyMC4zMjEgNDMuMTg3OSAzMDYuNDM2IDUyLjY4NTcgMzAxLjgzMUwyNTcuMDE0IDIwMi43NjZDMzA0LjQzMiAxNzkuNzc2IDI5OC43NTggMTEwLjQ4MyAyNDguMjMzIDk1LjUxMkw5Ny4yOTAyIDUyLjc4ODRaIiBmaWxsPSIjRkZGRkZGIi8+CjxwYXRoIGQ9Ik0yNTkuMTQ3IDAuOTgxODEyQzI3MS4zODkgLTIuNTc0OTggMjg0LjE5NyA0LjQ2NTcxIDI4Ny43NTQgMTYuNzA3NEMyOTEuMzExIDI4Ljk0OTIgMjg0LjI3IDQxLjc1NyAyNzIuMDI4IDQ1LjMxMzhMNzEuMTcyNyAxMDMuNjcxQzQwLjcxNDIgMTEyLjUyMSAzNy4xOTc2IDE1NC4yNjIgNjUuNzQ1OSAxNjguMDgzTDI0MS4zNDMgMjUzLjA5M0MzMDcuODcyIDI4NS4zMDIgMjk5Ljc5NCAzODIuNTQ2IDIyOC44NjIgNDAzLjMzNkwzMC40MDQxIDQ2MS41MDJDMTguMTcwNyA0NjUuMDg4IDUuMzQ3MDggNDU4LjA3OCAxLjc2MTUzIDQ0NS44NDRDLTEuODIzOSA0MzMuNjExIDUuMTg2MzcgNDIwLjc4NyAxNy40MTk3IDQxNy4yMDJMMjE1Ljg3OCAzNTkuMDM1QzI0Ni4yNzcgMzUwLjEyNSAyNDkuNzM5IDMwOC40NDkgMjIxLjIyNiAyOTQuNjQ1TDQ1LjYyOTcgMjA5LjYzNUMtMjAuOTgzNCAxNzcuMzg2IC0xMi43NzcyIDc5Ljk4OTMgNTguMjkyOCA1OS4zNDAyTDI1OS4xNDcgMC45ODE4MTJaIiBmaWxsPSIjRkZGRkZGIi8+Cjwvc3ZnPgo=&logoColor=white)](https://github.com/cagataycali/awesome-strands-agents)

Open-source observability for your LLM application, based on OpenTelemetry.

LLM Tracekit is a set of OpenTelemetry instrumentations that gives you complete observability over your LLM application. Because it uses OpenTelemetry under the hood, it can be connected to your existing observability solutions - Coralogix, Datadog, Honeycomb, and others.

## 🚀 Getting Started

Install the instrumentation for your LLM provider:

```bash
pip install llm-tracekit-openai             # For OpenAI
pip install llm-tracekit-bedrock            # For AWS Bedrock
pip install llm-tracekit-gemini             # For Google Gemini
pip install llm-tracekit-google-adk         # For Google ADK
pip install llm-tracekit-litellm            # For LiteLLM
pip install llm-tracekit-langchain          # For LangChain
pip install llm-tracekit-langgraph          # For LangGraph
pip install llm-tracekit-openai-agents      # For OpenAI Agents SDK
pip install llm-tracekit-strands            # For Strands Agents
pip install llm-tracekit-anthropic          # For Anthropic (Claude API)
pip install llm-tracekit-microsoft-foundry  # For Microsoft Foundry
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
| [Anthropic](https://www.anthropic.com/) | `llm-tracekit-anthropic` | `AnthropicInstrumentor` |
| [Microsoft Foundry](https://ai.azure.com/) | `llm-tracekit-microsoft-foundry` | `MicrosoftFoundryInstrumentor` |

### Frameworks

| Framework | Package | Instrumentor |
|-----------|---------|--------------|
| [Google ADK](https://github.com/google/adk-python) | `llm-tracekit-google-adk` | `GoogleADKInstrumentor` |
| [LiteLLM](https://github.com/BerriAI/litellm) | `llm-tracekit-litellm` | `LiteLLMInstrumentor` |
| [LangChain](https://www.langchain.com/) | `llm-tracekit-langchain` | `LangChainInstrumentor` |
| [LangGraph](https://langchain-ai.github.io/langgraph/) | `llm-tracekit-langgraph` | `LangGraphInstrumentor` |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) | `llm-tracekit-openai-agents` | `OpenAIAgentsInstrumentor` |
| [Strands Agents](https://github.com/strands-agents/sdk-python) | `llm-tracekit-strands` | `StrandsInstrumentor` |


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
- [Google ADK](./instrumentations/google-adk/README.md)
- [LiteLLM](./instrumentations/litellm/README.md)
- [LangChain](./instrumentations/langchain/README.md)
- [LangGraph](./instrumentations/langgraph/README.md)
- [OpenAI Agents SDK](./instrumentations/openai-agents/README.md)
- [Strands Agents](./instrumentations/strands/README.md)
- [Anthropic](./instrumentations/anthropic/README.md)
- [Microsoft Foundry](./instrumentations/microsoft-foundry/README.md)

## 📜 License

Apache 2.0 - See [LICENSE](./LICENSE) for details.
