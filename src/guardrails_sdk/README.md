# Coralogix Guardrails SDK

Python SDK for interacting with the Coralogix Guardrails API.

## Installation

```bash
pip install coralogix-guardrails-sdk
```

## Quick Start

```python
import asyncio
from guardrails_sdk import Guardrails, GuardrailsConfig, PII, PromptInjection, PIICategories, GuardrailTriggered

guardrails = Guardrails(
    api_key="your-api-key",
    cx_endpoint="https://your-domain.coralogix.com",
    application_name="my-app",
    subsystem_name="my-subsystem",
)

async def main():
    async with guardrails.guarded_session():
        try:
            # Guard input
            await guardrails.guard_prompt(
                prompt="User input here",
                guardrails_config=GuardrailsConfig(
                    pii=PII(categories=[PIICategories.email]),
                    prompt_injection=PromptInjection()
                ),
            )
            
            response = "..."  # Your LLM call here
            
            # Guard output
            await guardrails.guard_response(
                guardrails_config=GuardrailsConfig(
                    pii=PII(categories=[PIICategories.email]),
                    prompt_injection=PromptInjection()
                ),
                response=response,
                prompt="User input here",
            )
        except GuardrailTriggered as e:
            print(f"Blocked: {e.guardrail_type}, score={e.score}, categories={e.detected_categories}")

asyncio.run(main())
```

> **Note**: This SDK is async-only. All calls must be awaited. Use `asyncio.run()` from synchronous code.

### Environment Variables

```bash
export CX_GUARDRAILS_TOKEN="your-api-key"
export CX_ENDPOINT="https://your-domain.coralogix.com"
export CX_APPLICATION_NAME="my-app"      # Optional, default: "Unknown"
export CX_SUBSYSTEM_NAME="my-subsystem"  # Optional, default: "Unknown"
```

```python
guardrails = Guardrails()  # Reads from environment variables
```

## The `guarded_session()` Context Manager

**Required** for all guardrail calls. It:
1. Manages the HTTP client lifecycle (connection reuse)
2. Creates an OpenTelemetry span for tracing correlation

**Important**: Don't nest guarded_sessions. Don't reuse across unrelated requests. One guarded_session = one user-LLM exchange.

## Response Schema

`guard_prompt()` and `guard_response()` return `List[GuardrailsResult]`—one per guardrail. If any violation is detected (score ≥ threshold), `GuardrailTriggered` is raised instead.

| Field | Type | Description |
|-------|------|-------------|
| `detection_type` | `GuardrailType` | `pii` or `prompt_injection` |
| `detected` | `bool` | Whether violation was detected |
| `score` | `float` | Confidence score (0.0–1.0) |
| `threshold` | `float` | Detection threshold (default: 0.7) |
| `explanation` | `str \| None` | Human-readable explanation |
| `detected_categories` | `Any \| None` | For PII: detected categories (e.g., `["email"]`) |

## Guardrail Types

### PII Detection

Detects personally identifiable information in text. Use on prompts to prevent users from accidentally sharing sensitive data, or on responses to ensure your LLM doesn't leak PII.

```python
from guardrails_sdk import PII, PIICategories

# Detect all PII categories (default)
PII()

# Detect specific categories with custom threshold
PII(categories=[PIICategories.email, PIICategories.phone], threshold=0.8)
```

**Available categories:**
- `PIICategories.email` – Email addresses
- `PIICategories.phone` – Phone numbers
- `PIICategories.user_name` – Personal names
- `PIICategories.address` – Physical addresses
- `PIICategories.credit_card` – Credit card numbers
- `PIICategories.social_security_number` – SSNs
- `PIICategories.passport` – Passport numbers
- `PIICategories.driver_license` – Driver's license numbers

### Prompt Injection Detection

Detects attempts to manipulate LLM behavior through malicious prompts. Catches techniques like jailbreaking, instruction override, and role-playing attacks.

```python
from guardrails_sdk import PromptInjection

# Default threshold (0.7)
PromptInjection()

# Custom threshold for stricter detection
PromptInjection(threshold=0.8)
```

Use on user inputs to block malicious prompts before they reach your LLM.

### GuardrailsConfig

The `GuardrailsConfig` class is used to configure which guardrails to apply. You can specify any combination of PII detection, prompt injection detection, and custom guardrails.

```python
from guardrails_sdk import GuardrailsConfig, PII, PromptInjection, PIICategories

# Use only PII detection
config = GuardrailsConfig(pii=PII(categories=[PIICategories.email]))

# Use only prompt injection detection
config = GuardrailsConfig(prompt_injection=PromptInjection())

# Use both PII and prompt injection detection
config = GuardrailsConfig(
    pii=PII(categories=[PIICategories.email]),
    prompt_injection=PromptInjection()
)


## Error Handling

```python
from guardrails_sdk import (
    GuardrailsError, GuardrailsAPIConnectionError,
    GuardrailsAPITimeoutError, GuardrailsAPIResponseError, GuardrailTriggered,
)

try:
    await guardrails.guard_prompt(
        prompt="test",
        guardrails_config=GuardrailsConfig(prompt_injection=PromptInjection())
    )
except GuardrailTriggered as e:
    print(f"Type: {e.guardrail_type}")      # "pii", "prompt_injection"
    print(f"Score: {e.score}")               # 0.95
    print(f"Explanation: {e.explanation}")   # Human-readable
    print(f"Categories: {e.detected_categories}")  # ["email", "phone"] for PII
    print(str(e))  # "Guardrail triggered: pii | score=0.950 | ..."
except GuardrailsAPITimeoutError:
    ...  # Request timed out
except GuardrailsAPIConnectionError:
    ...  # Network error
except GuardrailsAPIResponseError as e:
    print(f"HTTP {e.status_code}: {e.body}")
```

## Failure Mode Patterns

Choose how to handle API failures:

### Fail-Closed (High-Security)

```python
async def guard_fail_closed(guardrails, prompt, config: GuardrailsConfig):
    try:
        async with guardrails.guarded_session():
            await guardrails.guard_prompt(prompt=prompt, guardrails_config=config)
            return True, None
    except GuardrailTriggered as e:
        return False, f"Blocked: {e}"
    except (GuardrailsAPITimeoutError, GuardrailsAPIConnectionError, GuardrailsAPIResponseError):
        return False, "Guardrails unavailable—blocking request"
```

### Fail-Open (High-Availability)

```python
async def guard_fail_open(guardrails, prompt, config: GuardrailsConfig):
    try:
        async with guardrails.guarded_session():
            await guardrails.guard_prompt(prompt=prompt, guardrails_config=config)
            return True, None
    except GuardrailTriggered as e:
        return False, f"Blocked: {e}"
    except (GuardrailsAPITimeoutError, GuardrailsAPIConnectionError, GuardrailsAPIResponseError) as e:
        logging.warning(f"Guardrails unavailable, failing open: {e}")
        return True, None  # Allow through
```

| Pattern | Use When | Trade-off |
|---------|----------|-----------|
| **Fail-Closed** | Security-critical, compliance | May block users during outages |
| **Fail-Open** | High-availability requirements | May allow violations during outages |

> **Tip**: For retry logic, use [tenacity](https://github.com/jd/tenacity) with `retry_if_exception_type((GuardrailsAPITimeoutError, GuardrailsAPIConnectionError))`.

## License

Apache License 2.0
