# Coralogix Guardrails SDK

Python SDK for interacting with the Coralogix Guardrails API.

## Installation

```bash
pip install cx-guardrails
```

## API Overview

| Method | Use Case | Input |
|--------|----------|-------|
| `guard_prompt()` | Guard user input before LLM call | `prompt` |
| `guard_response()` | Guard LLM output after generation | `response`, `prompt` (optional) |
| `guard()` | Full control over message history | List of messages |

## Quick Start

```python
import asyncio
from cx_guardrails import Guardrails, PII, PromptInjection, PIICategory, GuardrailsTriggered, setup_export_to_coralogix

setup_export_to_coralogix(service_name="my-service")

guardrails = Guardrails(
    api_key="your-api-key",
    cx_endpoint="https://your-domain.coralogix.com",
)

async def main():
    async with guardrails.guarded_session():
        try:
            # Guard user input
            await guardrails.guard_prompt(
                guardrails=[PII(), PromptInjection()],
                prompt="User input here",
            )
            
            response = "..."  # Your LLM call here
            
            # Guard LLM output
            await guardrails.guard_response(
                guardrails=[PII(), PromptInjection()],
                response=response,
            )
        except GuardrailsTriggered as e:
            for v in e.triggered:
                print(f"Blocked: {v.guardrail_type}, score={v.score}")

asyncio.run(main())
```

> **Note**: This SDK is async-only. See [`examples/basic.py`](examples/basic.py) for a complete example.

### Environment Variables

```bash
export CX_GUARDRAILS_TOKEN="your-api-key"
export CX_ENDPOINT="https://your-domain.coralogix.com"
export CX_APPLICATION_NAME="my-app"      # Optional, default: "Unknown"
export CX_SUBSYSTEM_NAME="my-subsystem"  # Optional, default: "Unknown"
```

### Timeout Configuration

The default timeout is 10 seconds. Configure it via the `timeout` parameter, in seconds:

```python
guardrails = Guardrails(
    api_key="your-api-key",
    cx_endpoint="https://your-domain.coralogix.com",
    timeout=2,  # 2 seconds
)
```

## Guard API

Use `guard()` for full control over messages. Accepts `Message` objects or simple dicts:

```python
from cx_guardrails import GuardrailsTarget

# Using dicts
messages = [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"},
]

await guardrails.guard([PII()], messages, GuardrailsTarget.RESPONSE)
```

See [`examples/guard.py`](examples/guard.py) for more details.

## Guardrail Types

### PII Detection

Detects personally identifiable information:

```python
from cx_guardrails import PII, PIICategory

PII()  # All categories
PII(categories=[PIICategory.EMAIL_ADDRESS, PIICategory.PHONE_NUMBER], threshold=0.8)
```

**Categories:** `email_address`, `phone_number`, `credit_card`, `iban_code`, `us_ssn`

### Prompt Injection Detection

Detects attempts to manipulate LLM behavior:

```python
from cx_guardrails import PromptInjection

PromptInjection()  # Default threshold 0.7
PromptInjection(threshold=0.8)  # Stricter
```





## Error Handling

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

## Failure Modes

| Pattern | Use When | Behavior |
|---------|----------|----------|
| **Fail-Closed** | Security-critical | Block on API failure |
| **Fail-Open** | High-availability | Allow on API failure |

Set `DISABLE_GUARDRAILS_TRIGGERED_EXCEPTION=true` for fail-open on violations.

## License

Apache License 2.0
