# Guard API

The `guard()` method provides full control over message history, making it ideal for multi-turn conversations and complex guardrail scenarios.

## The `guard()` Method

The `guard()` API accepts a list of messages with conversation context:

```python
await guardrails.guard(
    messages=messages,
    guardrails=config,
    target=GuardrailsTarget.PROMPT,  # or GuardrailsTarget.RESPONSE
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `messages` | `list[Message \| dict]` | Conversation history as Message objects or dicts |
| `guardrails` | `list[GuardrailConfigType]` | List of guardrail policies to apply |
| `target` | `GuardrailsTarget` | What to guard: `PROMPT` or `RESPONSE` |

### Target Types

- `GuardrailsTarget.PROMPT` - Guards the latest user message in the conversation
- `GuardrailsTarget.RESPONSE` - Guards the latest assistant message (must be the last message)

## Basic Usage

Guard a user prompt with conversation context:

```python
import asyncio
from guardrails import Guardrails, PII, PromptInjection, GuardrailsTarget, GuardrailsTriggered

async def main():
    guardrails = Guardrails()
    config = [PII(), PromptInjection()]

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is machine learning?"},
        {"role": "assistant", "content": "Machine learning is a subset of AI..."},
        {"role": "user", "content": "Can you explain neural networks?"},
    ]

    async with guardrails.guarded_session():
        try:
            await guardrails.guard(
                messages=messages,
                guardrails=config,
                target=GuardrailsTarget.PROMPT,
            )
            print("✓ Prompt passed")
        except GuardrailsTriggered as e:
            print(f"✗ Blocked: {e}")

asyncio.run(main())
```

Expected output:

```
✓ Prompt passed
```

## Conversations with Tool Calls

When your LLM uses tools/functions, include tool messages in the conversation history. Tool call details and tool results should be in the `content` field:

```python
import asyncio
from guardrails import Guardrails, PII, PromptInjection, GuardrailsTarget, GuardrailsTriggered

async def main():
    guardrails = Guardrails()
    config = [PII(), PromptInjection()]

    # Conversation with tool usage
    messages = [
        {"role": "system", "content": "You are a helpful assistant with access to tools."},
        {"role": "user", "content": "What's the weather in San Francisco?"},
        {"role": "assistant", "content": '[tool_call: get_weather({"location": "San Francisco"})]'},
        {"role": "tool", "content": '{"temperature": 65, "condition": "sunny"}'},
        {"role": "assistant", "content": "The weather in San Francisco is sunny with a temperature of 65°F."},
        {"role": "user", "content": "Thanks! Now what about New York?"},
    ]

    async with guardrails.guarded_session():
        try:
            await guardrails.guard(
                messages=messages,
                guardrails=config,
                target=GuardrailsTarget.PROMPT,
            )
            print("✓ Prompt passed")
        except GuardrailsTriggered as e:
            print(f"✗ Blocked: {e}")

asyncio.run(main())
```

Expected output:

```
✓ Prompt passed
```

### Building Tool Call Conversations Incrementally

Here's a simple example of how to append tool calls and results to your messages array:

```python
messages = [
    {"role": "user", "content": "What's the weather in Paris?"},
]

# After the LLM decides to call a tool, append the tool call
messages.append({"role": "assistant", "content": '[tool_call: get_weather({"location": "Paris"})]'})

# After executing the tool, append the result
messages.append({"role": "tool", "content": '{"temperature": 18, "condition": "cloudy"}'})

# After the LLM generates its final response
messages.append({"role": "assistant", "content": "The weather in Paris is cloudy with a temperature of 18°C."})
```

## Using the `Message` Class

For type safety and better IDE support, use the `Message` class instead of plain dicts:

```python
from guardrails import Guardrails, Message, Role, PII, GuardrailsTarget

async def main():
    guardrails = Guardrails()

    messages = [
        Message(role=Role.SYSTEM, content="You are a helpful assistant with access to tools."),
        Message(role=Role.USER, content="What's the weather in San Francisco?"),
        Message(role=Role.ASSISTANT, content='[tool_call: get_weather({"location": "San Francisco"})]'),
        Message(role=Role.TOOL, content='{"temperature": 65, "condition": "sunny"}'),
        Message(role=Role.ASSISTANT, content="The weather in San Francisco is sunny with a temperature of 65°F."),
        Message(role=Role.USER, content="Thanks! Now what about New York?"),
    ]

    async with guardrails.guarded_session():
        await guardrails.guard(
            messages=messages,
            guardrails=[PII()],
            target=GuardrailsTarget.PROMPT,
        )
```

### Available Roles

| Role | Description |
|------|-------------|
| `Role.SYSTEM` | System instructions |
| `Role.USER` | User messages |
| `Role.ASSISTANT` | LLM responses |
| `Role.TOOL` | Tool/function call results |

## Full Guarded Conversation Example

Here's a complete example using the `guard()` API with OpenAI and the `Message` class:

```python
import asyncio
from openai import AsyncOpenAI
from guardrails import Guardrails, Message, Role, PII, PromptInjection, GuardrailsTarget, GuardrailsTriggered

async def main():
    guardrails = Guardrails()
    openai_client = AsyncOpenAI()
    
    config = [PII(), PromptInjection()]
    messages = [
        Message(role=Role.SYSTEM, content="You are a helpful assistant."),
        Message(role=Role.USER, content="What is AI observability? Explain in one sentence."),
    ]

    async with guardrails.guarded_session():
        # Guard the user input
        try:
            await guardrails.guard(
                messages=messages,
                guardrails=config,
                target=GuardrailsTarget.PROMPT,
            )
            print("✓ User input passed")
        except GuardrailsTriggered as e:
            return print(f"✗ Blocked: {e}")

        # Call OpenAI - convert Message objects to dicts for OpenAI API
        openai_messages = [{"role": m.role.value, "content": m.content} for m in messages]
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=openai_messages,
        )
        llm_response = response.choices[0].message.content

        # Append assistant response to maintain conversation history
        messages.append(Message(role=Role.ASSISTANT, content=llm_response))

        # Guard the LLM response with full conversation context
        try:
            await guardrails.guard(
                messages=messages,
                guardrails=config,
                target=GuardrailsTarget.RESPONSE,
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

## Error Handling

The `guard()` method can raise several exceptions. Here's how to handle them:

```python
from guardrails import (
    Guardrails,
    PII,
    GuardrailsTarget,
    GuardrailsTriggered,
    GuardrailsAPITimeoutError,
    GuardrailsAPIConnectionError,
    GuardrailsAPIResponseError,
)

async def guarded_request(messages: list, config: list):
    guardrails = Guardrails()
    
    async with guardrails.guarded_session():
        try:
            await guardrails.guard(
                messages=messages,
                guardrails=config,
                target=GuardrailsTarget.PROMPT,
            )
            return {"status": "passed"}
            
        except GuardrailsTriggered as e:
            # One or more guardrails detected a violation
            violations = [
                {
                    "type": v.guardrail_type,
                    "name": v.name,
                }
                for v in e.triggered
            ]
            return {"status": "blocked", "violations": violations}
            
        except GuardrailsAPITimeoutError:
            # Request timed out - decide: fail-open or fail-closed?
            # Fail-closed (block the request):
            return {"status": "error", "reason": "timeout", "action": "blocked"}
            # Or fail-open (allow the request):
            # return {"status": "warning", "reason": "timeout", "action": "allowed"}
            
        except GuardrailsAPIConnectionError as e:
            # Network error - implement retry logic or fallback
            return {"status": "error", "reason": "connection_error", "message": str(e)}
            
        except GuardrailsAPIResponseError as e:
            # API returned an error response
            return {
                "status": "error",
                "reason": "api_error",
                "status_code": e.status_code,
                "body": e.body,
            }
```

### Error Types

| Exception | When It's Raised | Recommended Action |
|-----------|------------------|-------------------|
| `GuardrailsTriggered` | A guardrail detected a violation | Block the request, log the violation |
| `GuardrailsAPITimeoutError` | Request exceeded timeout | Retry or implement fail-open/fail-closed |
| `GuardrailsAPIConnectionError` | Network connectivity issues | Retry with backoff, alert on-call |
| `GuardrailsAPIResponseError` | API returned non-2xx status | Log error, check API status |

### Fail-Open vs Fail-Closed

Choose based on your requirements:

| Pattern | Use When | Behavior on Error |
|---------|----------|-------------------|
| **Fail-Closed** | Security-critical applications | Block requests when guardrails unavailable |
| **Fail-Open** | High-availability requirements | Allow requests when guardrails unavailable |

To enable fail-open mode globally (suppresses `GuardrailsTriggered` exceptions):

```bash
export DISABLE_GUARDRAILS_TRIGGERED_EXCEPTION=true
```

## Best Practices

1. **Reuse the messages list** - Share the same messages list between guardrails and your LLM provider to ensure consistency.

2. **Guard both directions** - Guard user prompts before sending to the LLM, and guard responses before returning to the user.

3. **Use `guarded_session()`** - Always wrap guardrail calls in a session for proper tracing and resource management.

4. **Handle all error types** - Implement proper error handling for all exception types to ensure resilient applications.

5. **Log violations** - Track and monitor guardrail violations for security auditing and model improvement.

