# Coralogix Guardrails SDK

Python SDK for interacting with the Coralogix Guardrails API.

## Installation

```bash
pip install guardrails
```

Or via the meta-package:

```bash
pip install llm-tracekit[guardrails]
```

## Quick Start

```python
import asyncio
from guardrails import Guardrails, PII, PromptInjection, PIICategorie, GuardrailsTriggered

guardrails = Guardrails(
    api_key="your-api-key",
    cx_endpoint="https://your-domain.coralogix.com",
)

async def main():
    async with guardrails.guarded_session():
        try:
            # Guard user input
            await guardrails.guard_prompt(
                prompt="User input here",
                guardrails_config=[PII(), PromptInjection()],
            )
            
            response = "..."  # Your LLM call here
            
            # Guard LLM output
            await guardrails.guard_response(
                response=response,
                guardrails_config=[PII(), PromptInjection()],
            )
        except GuardrailsTriggered as e:
            for v in e.triggered:
                print(f"Blocked: {v.guardrail_type}, score={v.score}")

asyncio.run(main())
```

> **Note**: This SDK is async-only. See [`examples/basic_example.py`](examples/basic_example.py) for a complete example.

### Environment Variables

```bash
export CX_GUARDRAILS_TOKEN="your-api-key"
export CX_ENDPOINT="https://your-domain.coralogix.com"
export CX_APPLICATION_NAME="my-app"      # Optional, default: "Unknown"
export CX_SUBSYSTEM_NAME="my-subsystem"  # Optional, default: "Unknown"
```

## Guard API

Use `guard()` for full control over messages. Accepts `Message` objects or simple dicts:

```python
from guardrails.models.enums import GuardrailsTarget

# Using dicts
messages = [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"},
]

await guardrails.guard(messages, [PII()], GuardrailsTarget.response)
```

See [`examples/direct_guard_example.py`](examples/direct_guard_example.py) for more details.

## Guardrail Types

### PII Detection

Detects personally identifiable information:

```python
from guardrails import PII, PIICategorie

PII()  # All categories
PII(categories=[PIICategorie.email_address, PIICategorie.phone_number], threshold=0.8)
```

**Categories:** `email_address`, `phone_number`, `credit_card`, `iban_code`, `us_ssn`

### Prompt Injection Detection

Detects attempts to manipulate LLM behavior:

```python
from guardrails import PromptInjection

PromptInjection()  # Default threshold 0.7
PromptInjection(threshold=0.8)  # Stricter
```

## Error Handling

```python
from guardrails import (
    GuardrailsTriggered,
    GuardrailsAPITimeoutError,
    GuardrailsAPIConnectionError,
    GuardrailsAPIResponseError,
)

try:
    await guardrails.guard_prompt(prompt="test", guardrails_config=[PII()])
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

## Failure Modes

| Pattern | Use When | Behavior |
|---------|----------|----------|
| **Fail-Closed** | Security-critical | Block on API failure |
| **Fail-Open** | High-availability | Allow on API failure |

Set `DISABLE_GUARDRAIL_TRIGGERED_EXCEPTIONS=true` for fail-open on violations.

## License

Apache License 2.0
