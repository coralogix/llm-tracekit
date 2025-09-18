# Coralogix Guardrails SDK

This library provides an SDK for configuring and applying Guardrails for your application. This SDK provids content safety and validation, real-time detection of PII exposure, prompt injection attacks, and custom policies.


## Installation

```bash
pip install cx-guardrails-sdk
```

## Quick Start

### Python Client Usage

#### Imports
```python
import asyncio
from guardrails import Guardrails, PII, PromptInjection, CustomGuardrail, PIICategories, PromptInjectionCategories
```

#### Initialize the guardrails client
```python
guardrails = Guardrails(
    api_key="your-api-key",
    application_name="my-application",
    subsystem_name="my-subsystem"
    domain_url="http://127.0.0.1:8000"
)
```

#### Configure guardrails
```python
guardrail_config = [
    PII(
        name="pii-check", 
        categories=["email", "phone", "address"]
    ),
    PromptInjection(
        name="injection-check", 
        categories=["illegal_topics", "code_execution", "say_command"]
    ),
    CustomGuardrail(
        name="custom-check", 
        criteria="Ensure content is appropriate for all audiences"
    )
]
```



#### Run Guardrails
```python
message = "Please send payment to john.doe@example.com or call 555-123-4567"

results = await guardrails.run(message, guardrail_config)
```

### The server provides the following endpoints:

- `POST /guardrails/run` - Main guardrails analysis endpoint
- `GET /guardrails/health` - Health check endpoint (Used for testing)


### HTTP API Usage

```bash
curl -X POST "https://api.guardrails.ai/v1/guardrails/run" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "Please call me at 555-123-4567",
       "api_key": "your-api-key",
       "application_name": "my-application",
       "subsystem_name": "my-subsystem",
       "domain_url": "http://127.0.0.1:8000"
       "guardrails_config": [
         {
           "name": "pii-check",
           "type": "pii",
           "categories": ["phone"],
         }
       ]
     }'
```

## Guardrail Types

### PII (Personally Identifiable Information)

Detects and flags various types of personal information:

```python
from guardrails import PII, PIICategories

# Use predefined categories
pii_guardrail = PII(
    name="pii-detection",
    categories=PIICategories.values(),  # All available categories
)

# Or specify custom categories
pii_guardrail = PII(
    name="basic-pii",
    categories=["email", "phone", "credit_card"],
)
```

**Available PII Categories:**
- `email` - Email addresses
- `phone` - Phone numbers
- `name` - Personal names
- `address` - Physical addresses
- `credit_card` - Credit card numbers
- `social_security_number` - SSN/Social security numbers
- `passport` - Passport numbers
- `driver_license` - Driver's license numbers


### Prompt Injection Protection

Detects various prompt injection attacks:

```python
from guardrails import PromptInjection, PromptInjectionCategories

# Use all protection categories
injection_guardrail = PromptInjection(
    name="injection-protection",
    categories=PromptInjectionCategories.values(),  # All available categories
)

# Or specify specific threats
injection_guardrail = PromptInjection(
    name="targeted-protection",
    categories=["code_execution", "illegal_topics", "instructions_leakage"],
)
```

**Available Prompt Injection Categories:**
- `change_personality` - Attempts to change AI personality
- `forget_instructions` - Attempts to override system instructions
- `illegal_topics` - Requests for illegal content
- `say_command` - Commands to repeat or say specific things
- `instructions_leakage` - Attempts to extract system prompts
- `code_execution` - Requests to execute code
- `contains_emojis` - Suspicious emoji usage patterns
- `contains_encoding` - Encoded or obfuscated content
- `prompt_repetition` - Repetitive prompt patterns
- `contains_gibberish` - Nonsensical input patterns

### Custom Guardrails

Define your own validation criteria:

```python
from guardrails import CustomGuardrail

custom_guardrail = CustomGuardrail(
    name="brand-safety",
    criteria="Ensure content aligns with company brand guidelines and values",
    threshold=0.75
)

# Another example
content_policy = CustomGuardrail(
    name="content-policy",
    criteria="Check if content violates community guidelines or terms of service",
    threshold=0.9
)
```

## Configuration

### Guardrails Client

```python
from guardrails import Guardrails

guardrails = Guardrails(
    api_key="your-api-key",              # Required: Your API key
    application_name="my-app",           # Required: Application identifier
    subsystem_name="content-filter",     # Required: Subsystem identifier
    domain_url="http://127.0.0.1:8000"   # Required: Domain
)
```

### Environment Variables

You can also configure using environment variables:

```bash
export API_KEY="your-api-key"
export APPLICATION_NAME="my-app"
export SUBSYSTEM_NAME="content-filter"
export DOMAIN_URL="http://127.0.0.1:8000"
```

## Response Format

The guardrails analysis returns a list of results:

```python
class GuardrailsResult:
    name: str          # Name of the guardrail
    detected: bool     # Whether the guardrail was triggered
    score: float       # Confidence score (0.0 - 1.0)
    explanation: str   # Human-readable explanation for why the guardrail was triggered
    threshold: float   # Threshold used for detection
```

Example response:
```python
[
    GuardrailsResult(
        name="pii-check",
        detected=True,
        score=0.95,
        explanation="Found email address: john.doe@example.com",
        threshold=0.7
    ),
    GuardrailsResult(
        name="injection-check",
        detected=False,
        score=0.1,
        explanation="No prompt injection patterns detected",
        threshold=0.6
    )
]
```


## Testing
### Running the Development Server

```bash
# Clone the repository
git clone https://github.com/coralogix/llm-tracekit
cd llm-tracekit/src/guardrails

# Install in development mode
pip install -e .

# Start the development server
PYTHONPATH=./src uvicorn src.guardrails.tests.main:app --host 127.0.0.1 --port 8000 --reload
```

### HTTP API Usage

```bash
curl -X POST "http://localhost:8000/guardrails/run" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "Please call me at 555-123-4567",
       "api_key": "your-api-key",
       "application_name": "test-app",
       "subsystem_name": "content-check",
       "domain_url": "http://127.0.0.1:8000"
       "guardrails_config": [
         {
           "name": "pii-check",
           "type": "pii",
           "categories": ["phone"],
         }
       ]
     }'
```

### Run the tests



-----------
-----------

## API Reference

### Classes

- **`Guardrails`**: Main client class for interacting with the guardrails service
- **`PII`**: PII detection guardrail configuration
- **`PromptInjection`**: Prompt injection protection configuration  
- **`CustomGuardrail`**: Custom validation criteria configuration
- **`GuardrailsResult`**: Individual guardrail analysis result
- **`GuardrailsResponse`**: Complete analysis response

### Constants

- **`GR_THRESHOLD`**: Default threshold value (0.7)
- **`PIICategories`**: List of all available PII detection categories
- **`PromptInjectionCategories`**: List of all prompt injection protection categories
- ❕Both Categories class have `values()` method, used for getting the string values of the enums.
