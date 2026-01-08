# Coralogix Guardrails

Python SDK for protecting your LLM applications with content moderation, PII detection, and prompt injection detection.

## Installation

```bash
pip install cx-guardrails
```

## 🚀 Getting Started

| Method | Use Case | Input |
|--------|----------|-------|
| `guard_prompt()` | Guard user input before LLM call | `prompt` |
| `guard_response()` | Guard LLM output after generation | `response`, `prompt` (optional) |
| `guard()` | Full control over message history | List of messages |

## 🛡️ Available Guardrails

| Guardrail | Description | Usage |
|-----------|-------------|-------|
| **PII Detection** | Detects personally identifiable information | `PII()` |
| **Prompt Injection** | Detects attempts to manipulate LLM behavior | `PromptInjection()` |


```python
import asyncio
from cx_guardrails import Guardrails, PII, PromptInjection, GuardrailsTriggered, setup_export_to_coralogix

setup_export_to_coralogix(service_name="my-service")

guardrails = Guardrails()

async def main():
    async with guardrails.guarded_session():
        try:
            await guardrails.guard_prompt(
                guardrails=[PII(), PromptInjection()],
                prompt="User input here",
            )
            
            response = "..."  # Your LLM call here
            
            await guardrails.guard_response(
                guardrails=[PII(), PromptInjection()],
                response=response,
            )
        except GuardrailsTriggered as e:
            for v in e.triggered:
                print(f"Blocked: {v.guardrail_type}, score={v.score}")

asyncio.run(main())
```


### PII Detection

```python
from cx_guardrails import PII, PIICategory

PII()  # All categories, Default threshold 0.7
PII(categories=[PIICategory.EMAIL_ADDRESS, PIICategory.PHONE_NUMBER], threshold=0.8)
```

**Categories:** `email_address`, `phone_number`, `credit_card`, `iban_code`, `us_ssn`

### Prompt Injection Detection

```python
from cx_guardrails import PromptInjection

PromptInjection()  # Default threshold 0.7
PromptInjection(threshold=0.8)
```

## 📖 Using `guard()` for full control

```python
from cx_guardrails import GuardrailsTarget

messages = [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"},
]

await guardrails.guard([PII()], messages, GuardrailsTarget.RESPONSE)
```

### With tool calls

```python
messages = [
    {"role": "user", "content": "What's the weather in Paris?"},
    {
        "role": "assistant",
        "content": {"tool_calls": [
            {
                "id": "call_123",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": '{"location": "Paris"}'
                }
            }
        ],
        
    }},
    {
        "role": "tool",
        "tool_call_id": "call_123",
        "content": "The weather in Paris is 22°C and sunny."
    },
    {"role": "assistant", "content": "The weather in Paris is 22°C and sunny."},
]

await guardrails.guard([PII()], messages, GuardrailsTarget.RESPONSE)
```

## ⚙️ Configuration

### Environment Variables

```bash
export CX_GUARDRAILS_TOKEN="your-api-key"
export CX_ENDPOINT="https://your-domain.coralogix.com"
export CX_APPLICATION_NAME="my-app"      # Optional
export CX_SUBSYSTEM_NAME="my-subsystem"  # Optional
```

### Client Configuration

```python
guardrails = Guardrails(
    api_key="your-api-key",
    cx_endpoint="https://your-domain.coralogix.com",
    timeout=2,  # Timeout in seconds (default: 10)
)
```

## 🚨 Error Handling

```python
from cx_guardrails import (
    GuardrailsTriggered,
    GuardrailsAPITimeoutError,
    GuardrailsAPIConnectionError,
    GuardrailsAPIResponseError,
)

try:
    await guardrails.guard_prompt(guardrails=[PII()], prompt="test")
except GuardrailsTriggered as e:
    for v in e.triggered:
        print(f"{v.guardrail_type}: {v.score}")
except GuardrailsAPITimeoutError:
    pass  # Request timed out
except GuardrailsAPIConnectionError:
    pass  # Network error
except GuardrailsAPIResponseError as e:
    print(f"HTTP {e.status_code}")
```

## 📚 Examples

See the [examples](./examples/) directory for complete working examples:

- [Basic usage](./examples/basic.py)
- [Guard API](./examples/guard.py)
- [OpenAI integration](./examples/openai_chat.py)
- [Bedrock integration](./examples/bedrock.py)
- [Gemini integration](./examples/gemini.py)
- [LangChain integration](./examples/langchain.py)
- [LiteLLM integration](./examples/litellm_chat.py)
- [OpenAI Agents integration](./examples/openai_agents.py)

## 📜 License

Apache 2.0 - See [LICENSE](./LICENSE.md) for details.
