# Coralogix Guardrails SDK

Python SDK for interacting with the Coralogix Guardrails API.

## Installation

```bash
pip install coralogix-guardrails-sdk
```

## Usage

### Basic Example

```python
from guardrails_sdk import Guardrails, PII, PromptInjection, PIICategories, GuardrailTriggered

# Initialize the Guardrails client
guardrails = Guardrails(
    api_key="your-api-key",
    application_name="my-app",
    subsystem_name="my-subsystem",
    domain_url="https://your-domain.coralogix.com",
)

# Check input prompt
async with guardrails.interaction():
    prompt = "User input here"
    try:
        results = await guardrails.guard_prompt(
            prompt=prompt,
            guardrails_config=[PII(categories=[PIICategories.email]), PromptInjection()],
        )
        print(f"Guardrail results: {results}")
    except GuardrailTriggered as e:
        print(f"Guardrail triggered: {e}")
    response = ... # LLM call
    try:
        results = await guardrails.guard_response(
            guardrails_config=[PII(), PromptInjection()],
            response=response,
            prompt=prompt,
        )
        print(f"Guardrail results: {results}")
    except GuardrailTriggered as e:
        print(f"Guardrail triggered: {e}")
```

### Complete Example with LLM Integration

```python
from guardrails_sdk import Guardrails, PII, PromptInjection, PIICategories, GuardrailTriggered
from openai import OpenAI

# Initialize clients
guardrails = Guardrails(
    api_key="your-api-key",
    application_name="my-app",
    subsystem_name="my-subsystem",
    domain_url="https://your-domain.coralogix.com",
)
client = OpenAI()

# Process user input
async with guardrails.interaction():
    prompt = "User input here"
    
    # Guard the input prompt
    try:
        await guardrails.guard_prompt(
            prompt=prompt,
            guardrails_config=[PromptInjection()],
        )
    except GuardrailTriggered as e:
        print(f"Input blocked: {e}")
        return
    
    # Call LLM
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    response_content = response.choices[0].message.content
    
    # Guard the output response
    try:
        await guardrails.guard_response(
            guardrails_config=[
                PromptInjection(),
                PII(categories=[PIICategories.email, PIICategories.phone]),
            ],
            response=response_content,
            prompt=prompt,
        )
    except GuardrailTriggered as e:
        print(f"Output blocked: {e}")
        return
    
    print(f"Response: {response_content}")
```

### Configuration via Environment Variables

You can configure the Guardrails client using environment variables:

```bash
export GUARDRAILS_API_KEY="your-api-key"
export GUARDRAILS_APPLICATION_NAME="my-app"
export GUARDRAILS_SUBSYSTEM_NAME="my-subsystem"
export GUARDRAILS_DOMAIN_URL="https://your-domain.coralogix.com"
export GUARDRAILS_TIMEOUT="100"  # Optional, default is 100 seconds
```

Then initialize without parameters:

```python
guardrails = Guardrails()  # Reads from environment variables
```

## Guardrail Types

### PII Detection

Detect personally identifiable information:

```python
from guardrails_sdk import PII, PIICategories

# Detect all PII categories
pii_guardrail = PII()

# Detect specific categories
pii_guardrail = PII(
    categories=[PIICategories.email, PIICategories.phone, PIICategories.credit_card],
    threshold=0.8
)
```

Available PII categories:
- `PIICategories.email`
- `PIICategories.phone`
- `PIICategories.user_name`
- `PIICategories.address`
- `PIICategories.credit_card`
- `PIICategories.social_security_number`
- `PIICategories.passport`
- `PIICategories.driver_license`

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

## Error Handling

The SDK provides specific exception types for different error scenarios:

```python
from guardrails_sdk import (
    GuardrailsError,
    GuardrailsAPIConnectionError,
    GuardrailsAPITimeoutError,
    GuardrailsAPIResponseError,
    GuardrailTriggered,
)

try:
    results = await guardrails.guard_prompt(
        prompt="test",
        guardrails_config=[PromptInjection()],
    )
except GuardrailTriggered as e:
    # A guardrail detected a violation
    print(f"Guardrail type: {e.guardrail_type}")
    print(f"Name: {e.name}")
    print(f"Score: {e.score}")
    print(f"Explanation: {e.explanation}")
except GuardrailsAPITimeoutError as e:
    # Request timed out
    print(f"Timeout: {e}")
except GuardrailsAPIConnectionError as e:
    # Network/connection error
    print(f"Connection error: {e}")
except GuardrailsAPIResponseError as e:
    # Non-2xx HTTP response
    print(f"API error {e.status_code}: {e.body}")
except GuardrailsError as e:
    # Any other SDK error
    print(f"Error: {e}")
```

## License

Apache License 2.0
