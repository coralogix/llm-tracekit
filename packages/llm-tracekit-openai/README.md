# llm-tracekit-openai

OpenAI instrumentation for LLM tracing.

## Installation

```bash
pip install llm-tracekit-openai
```

## Usage

```python
from openai import OpenAI
from llm_tracekit_openai import OpenAIInstrumentor

OpenAIInstrumentor().instrument()

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

## License

Apache-2.0
