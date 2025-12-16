# Coralogix Guardrails SDK

Python SDK for interacting with the Coralogix Guardrails API.

## Installation

```bash
pip install coralogix-guardrails-sdk
```

## Usage

### Basic Example

```python
from guardrails_sdk import Guardrails, PII, PromptInjection

# Initialize the Guardrails client
guardrails = Guardrails(
    api_key="your-api-key",
    application_name="my-app",
    subsystem_name="my-subsystem",
    domain_url="https://your-domain.coralogix.com",
)

# Check input prompt
results = await guardrails.run_input(
    prompt="User input here",
    guardrails_config=[PII(categories=["email", "phone"]), PromptInjection()],
)

# Check output response
results = await guardrails.run_output(
    prompt="User input",
    response="Model response",
    guardrails_config=[PII(), PromptInjection()],
)

# Clean up
await guardrails.aclose()
```

### Using Context Manager

```python
async with Guardrails(
    api_key="your-api-key",
    application_name="my-app",
    subsystem_name="my-subsystem",
    domain_url="https://your-domain.coralogix.com",
) as guardrails:
    results = await guardrails.run_input(
        prompt="User input",
        guardrails_config=[PII(), PromptInjection()],
    )
```

### Configuration via Environment Variables

You can configure the Guardrails client using environment variables:

```bash
export GUARDRAILS_API_KEY="your-api-key"
export GUARDRAILS_APPLICATION_NAME="my-app"
export GUARDRAILS_SUBSYSTEM_NAME="my-subsystem"
export GUARDRAILS_DOMAIN_URL="https://your-domain.coralogix.com"
```

Then initialize without parameters:

```python
guardrails = Guardrails()  # Reads from environment variables
```

## Guardrail Types

### PII Detection

Detect personally identifiable information:

```python
from guardrails_sdk import PII

# Detect all PII categories
pii_guardrail = PII()

# Detect specific categories
pii_guardrail = PII(
    categories=["email", "phone", "credit_card"],
    threshold=0.8
)
```

### Prompt Injection Detection

Detect prompt injection attacks:

```python
from guardrails_sdk import PromptInjection

prompt_injection_guardrail = PromptInjection(threshold=0.7)
```

### Custom Guardrails

Define custom guardrails:

```python
from guardrails_sdk import CustomGuardrail

custom_guardrail = CustomGuardrail(
    name="toxicity",
    criteria="Check if content is toxic",
    threshold=0.8
)
```

## License

Apache License 2.0

