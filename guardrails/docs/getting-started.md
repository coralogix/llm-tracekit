# Getting Started

This guide will walk you through the process of integrating Coralogix Guardrails with your LLM application to protect against prompt injection attacks, PII leakage, and other security threats. By following these steps, you'll be able to start securing your AI applications in just a few minutes.

## Requirements

To integrate your application with Coralogix Guardrails, ensure you have the following:

- Python 3.10 or higher
- A Coralogix account with an API key
- Access to the Coralogix Guardrails API

## Install the SDK

Install the Guardrails library using `pip`.

```bash
pip install guardrails
```

Or via the meta-package:

```bash
pip install llm-tracekit[guardrails]
```

## Set up environment variables

Configure the necessary environment variables.

```bash
# Coralogix credentials
export CX_GUARDRAILS_TOKEN="your-coralogix-api-key"
export CX_ENDPOINT="https://your-domain.coralogix.com"

# Optional: Application metadata for observability
export CX_APPLICATION_NAME="my-app"
export CX_SUBSYSTEM_NAME="my-subsystem"

# OpenAI API key (for the example)
export OPENAI_API_KEY="your-openai-api-key"
```

## Step 1: Test Your Connection

Before enabling production policies, verify that the Guardrails API is reachable:

```python
import asyncio
from guardrails import Guardrails

async def main():
    guardrails = Guardrails()
    response = await guardrails.test_connection()
    print("✓ Guardrails API is reachable!")
    print(f"Response: {response}")

asyncio.run(main())
```

Expected output:

```
✓ Guardrails API is reachable!
Response: results=[GuardrailResult(type='test_policy', detected=False, ...)]
```

## Step 2: Set Up Observability Export

It is highly advisable to send guardrail data to Coralogix for monitoring and analysis. Configure the export to Coralogix AI Center:

```python
from llm_tracekit import setup_export_to_coralogix

setup_export_to_coralogix(
    service_name="my-service",
    application_name="my-app",
    subsystem_name="my-subsystem",
)
```

This enables OpenTelemetry tracing for all guardrail evaluations, allowing you to view traces in Coralogix AI Center. For more details on AI Observability setup, see the [AI Observability Getting Started Guide](https://coralogix.com/docs/user-guides/ai-observability/getting-started/).

## Step 3: Guard a Single Prompt

Check a user prompt for security issues:

```python
import asyncio
from guardrails import Guardrails, PII, PromptInjection

async def main():
    guardrails = Guardrails()
    
    result = await guardrails.guard_prompt(
        prompt="What is the capital of France?",
        guardrails=[PII(), PromptInjection()],
    )
    print(f"✓ Prompt passed: {result}")

asyncio.run(main())
```

Expected output:

```
✓ Prompt passed: results=[GuardrailResult(type='pii', detected=False, ...), GuardrailResult(type='prompt_injection', detected=False, ...)]
```

## Step 4: Guard a Prompt with Observability

For production use, wrap your guardrail calls in a `guarded_session()` context manager. This creates a parent span that groups all guardrail evaluations together for OpenTelemetry tracing, making it easy to correlate traces and view the complete request flow in Coralogix.

```python
import asyncio
from openai import AsyncOpenAI
from guardrails import Guardrails, PII, PromptInjection, GuardrailsTriggered

async def main():
    guardrails = Guardrails()
    openai_client = AsyncOpenAI()
    
    user_message = "What is AI observability? Explain in one sentence."
    config = [PII(), PromptInjection()]

    # Use guarded_session to group all spans under one parent for tracing
    async with guardrails.guarded_session():
        # Guard the user input
        try:
            await guardrails.guard_prompt(prompt=user_message, guardrails=config)
            print("✓ User input passed")
        except GuardrailsTriggered as e:
            return print(f"✗ Blocked: {e}")

        # Call OpenAI
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message},
            ],
        )
        print(f"\n📝 AI RESPONSE:\n{response.choices[0].message.content}")

asyncio.run(main())
```

Expected output:

```
✓ User input passed

📝 AI RESPONSE:
AI observability refers to the tools and practices used to monitor, analyze, and understand the behavior and performance of AI models and systems in real-time.
```

## Step 5: Full Guarded Conversation

Guard both user input and LLM response in a complete flow:

```python
import asyncio
from openai import AsyncOpenAI
from guardrails import Guardrails, PII, PromptInjection, GuardrailsTriggered

async def main():
    guardrails = Guardrails()
    openai_client = AsyncOpenAI()
    
    user_message = "What is AI observability? Explain in one sentence."
    config = [PII(), PromptInjection()]

    async with guardrails.guarded_session():
        # Guard the user input
        try:
            await guardrails.guard_prompt(prompt=user_message, guardrails=config)
            print("✓ User input passed")
        except GuardrailsTriggered as e:
            return print(f"✗ Blocked: {e}")

        # Call OpenAI
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message},
            ],
        )
        llm_response = response.choices[0].message.content

        # Guard the LLM response
        try:
            await guardrails.guard_response(
                response=llm_response,
                prompt=user_message,
                guardrails=config,
            )
            print("✓ LLM response passed")
        except GuardrailsTriggered as e:
            return print(f"✗ Response blocked: {e}")

        print(f"\n📝 AI RESPONSE:\n{llm_response}")

asyncio.run(main())
```

Expected output:

```
✓ User input passed
✓ LLM response passed

📝 AI RESPONSE:
AI observability refers to the tools and practices used to monitor, analyze, and understand the behavior and performance of AI models and systems in real-time.
```

## Run the application

Execute your Python script:

```bash
python guardrails_demo.py
```

Expected output:

```
✓ User input passed
✓ LLM response passed

📝 AI RESPONSE:
AI observability refers to the tools and practices used to monitor, analyze, and understand the behavior and performance of AI models and systems in real-time.
```

## View your data in Coralogix

1. Log into your Coralogix account.
2. Go to **AI Center > Application Catalog** to see your application.
3. Click on your application to view its detailed information.
4. Navigate to the Guardrails section to see the trace data for your guardrail evaluations.

## Available Guardrail Types

### PII Detection

Detects personally identifiable information in prompts and responses:

```python
from guardrails import PII, PIICategory

# Detect all PII categories
PII()

# Detect specific categories with custom threshold
PII(
    categories=[PIICategory.EMAIL_ADDRESS, PIICategory.PHONE_NUMBER],
    threshold=0.8
)
```

**Available categories:** `EMAIL_ADDRESS`, `PHONE_NUMBER`, `CREDIT_CARD`, `US_SSN`

### Prompt Injection Detection

Detects attempts to manipulate LLM behavior through malicious prompts:

```python
from guardrails import PromptInjection

# Default threshold (0.7)
PromptInjection()

# Stricter detection
PromptInjection(threshold=0.8)
```

## Handling Guardrail Violations

When a guardrail detects a violation, it raises a `GuardrailsTriggered` exception. This allows you to block unsafe content and respond appropriately:

```python
from guardrails import Guardrails, PII, GuardrailsTriggered

try:
    await guardrails.guard_prompt(prompt="Contact me at john.doe@example.com", guardrails=[PII()])
except GuardrailsTriggered as e:
    # Guardrail detected a violation
    print(f"Blocked: {len(e.triggered)} violation(s) detected")
    for violation in e.triggered:
        print(f"  - {violation.guardrail_type}: {violation.message}")
```

Expected output:

```
Blocked: 1 violation(s) detected
  - pii: PII detected in content
```

## Next Steps

- Explore the [examples](../examples/) directory for more integration patterns
- Learn about the [Direct Guard API](./guard-api.md) for full control over message history
- Set up monitoring dashboards in Coralogix AI Center

