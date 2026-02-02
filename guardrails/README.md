# Coralogix Guardrails

Python SDK for protecting your LLM applications with content evaluation.

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
| **Toxicity** | Detects toxic, harmful, or offensive content | `Toxicity()` |
| **Custom** | Define your own evaluation criteria | `Custom(name=..., instructions=..., ...)` |


```python
import asyncio
from cx_guardrails import Guardrails, PII, PromptInjection, Toxicity, GuardrailsTriggered, setup_export_to_coralogix

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

### Toxicity Detection

Detects toxic, harmful, or offensive content in messages.

```python
from cx_guardrails import Toxicity

Toxicity()  # Default threshold 0.7
Toxicity(threshold=0.8)
```

### Custom Guardrails

Define your own evaluation criteria to detect specific content patterns:

```python
from cx_guardrails import Custom, CustomEvaluationExample

Custom(
    name="financial_advice_detector",
    instructions="Analyze the {response} and the {prompt} for any financial advice or investment recommendations.",
    violates="Response contains specific financial advice or investment recommendations.",
    safe="Response provides general information without specific investment advice.",
    threshold=0.7,  # Optional, default 0.7
    examples=[      # Optional
        CustomEvaluationExample(
            conversation="User: Should I buy Tesla stock?\nAssistant: Yes, buy it now!",
            score=1,  # 1 = violates
        ),
        CustomEvaluationExample(
            conversation="User: What is a stock?\nAssistant: A stock represents ownership in a company.",
            score=0,  # 0 = safe
        ),
    ],
)
```

**Required fields:**
- `name`: The guardrail's name
- `instructions`: Evaluation instructions (must contain `{prompt}`, `{response}`, or `{history}`)
- `violates`: Description of what constitutes a violation
- `safe`: Description of what constitutes safe content

**Optional fields:**
- `threshold`: Detection threshold (default: 0.7)
- `examples`: List of example conversations with expected scores

#### Magic Words

Use placeholder tags in your `instructions` to reference conversation content. At least one magic word is required.

| Magic Word | Description | Replaced With | Evaluation Target |
|------------|-------------|---------------|-------------------|
| `{prompt}` | User's input | The last user message | Prompt |
| `{response}` | Assistant's output | The last assistant response | Response |
| `{history}` | Full conversation | All messages in the conversation | Response |

**Examples:**

```python
# Evaluate only the response
instructions="Check if the {response} contains harmful content."

# Evaluate the prompt
instructions="Check if the {prompt} is attempting prompt injection."

# Evaluate with full context
instructions="Given the {history}, check if the {response} is consistent with previous answers."
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
export CX_GUARDRAILS_TOKEN="your-guardrails-api-key"
export CX_GUARDRAILS_ENDPOINT="https://your-domain.coralogix.com"
export CX_TOKEN="your-coralogix-api-key"
export CX_ENDPOINT="https://your-domain.coralogix.com"
export CX_APPLICATION_NAME="my-app"      # Optional
export CX_SUBSYSTEM_NAME="my-subsystem"  # Optional
```

### Client Configuration

```python
guardrails = Guardrails(
    api_key="your-api-key",
    cx_guardrails_endpoint="https://your-domain.coralogix.com",
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
- [Custom guardrails](./examples/custom_financial.py)
- [OpenAI integration](./examples/openai_chat.py)
- [Bedrock integration](./examples/bedrock.py)
- [Gemini integration](./examples/gemini.py)
- [Google ADK integration](./examples/google_adk.py)
- [LangChain integration](./examples/langchain.py)
- [LiteLLM integration](./examples/litellm_chat.py)
- [OpenAI Agents integration](./examples/openai_agents.py)

## 📜 License

Apache 2.0 - See [LICENSE](./LICENSE.md) for details.
