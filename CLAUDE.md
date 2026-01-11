# Task
LLM Tracekit is a tracing library for AI applications. Here's what it does:
It automatically tracks all your AI calls and exports that data so you can see it in a dashboard (specifically Coralogix).

Our goal is to:
- Add or improve OpenTelemetry instrumentations for LLM, GenAI, agent, and tool libraries
- Create new instrumentations for LLM / GenAI libraries following the semantic conventions below
- Fix incorrect, incomplete, or broken instrumentations
- Follow the [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) so observability backends can reliably understand and compare data, and the custom semantic conventions from below.
- Provide tests that validate the emitted telemetry

## Creating New Instrumentation

Follow this workflow when creating new instrumentation:

1. **Discover library interfaces** - Check and list all the interfaces the GenAI library offers, that calls the llm, including sync & async & streaming methods
   
2. **Get user approval** - After listing interfaces, ask the user for approval before implementing

3. **Create instrumentation files** - Place new instrumentations in `src/llm_tracekit/<library_name>/` with this structure:
   - `__init__.py` - Exports the instrumentor
   - `instrumentor.py` - Main instrumentor class extending `BaseInstrumentor`
   - `package.py` - Defines `_instruments` tuple with library version requirements
   - Create more files if needed
   
   **If the library already writes OpenTelemetry spans:**
   - Do NOT use `SpanProcessor.on_end()` - spans are immutable at that point
   - Use **patching approach**: Wrap the library's tracing function to add attributes while the span is still active
   - Example: For Google ADK, wrap `trace_call_llm` in `google.adk.telemetry` to add semantic convention attributes to the current span via `trace.get_current_span().set_attributes()`
   - See `src/llm_tracekit/google_adk/patch.py` for reference implementation

4. **Implement instrumentation** - For each interface, create a wrapper that:
   - Extracts request attributes before calling the original method
   - Handles streaming by wrapping the response iterator
   - Extracts response attributes after the call completes
   - Records metrics (duration, token usage)
   - Handles errors properly with `handle_span_exception()`

5. **Propose library-specific attributes** - If the library has unique data not covered by standard conventions, propose custom attributes with prefix `gen_ai.<library_name>.*` (e.g., `gen_ai.bedrock.agent_alias_id`)

6. **Create Examples** - Create usage scripts under `examples/<library>/` directory:
   - Ask for API Key to call the LLM, and set it inside the code
   - Name format: `<library>_<interface>.py` (e.g., `openai_chat_completions.py`) if there are multiple interface where will be multiple examples
   - Add docstring with usage instructions and required env vars
   - For each interface create a complex use case, with sub-agents, tools and multi-turn conversation
   - Cover different text input formats (strings, dicts, content arrays, multi-part), we DON'T support videos, pictures, and voice
   - Use `setup_tracing()` with `ConsoleSpanExporter` to validate spans, run the examples

7. **Debug examples with ConsoleSpanExporter** - Validate spans are correct (see Debugging section below) for every example. If not, update the instrumentation and run again.

8. **Check Semantic Convention** - For each mandatory and optional key in the semantic convention, verify whether it should exist in the span. IIf it should exist and is missing, fix the instrumentation and rerun everything

9. **Create tests** - Tests should validate:
   - Span names and attributes match the semantic conventions
   - Message content is captured correctly (with/without content capture enabled)
   - Tool calls are recorded properly
   - Streaming responses are handled
   - Error cases set appropriate error attributes
   - Metrics are recorded

10. **Run tests** - Use VCR cassettes for reproducible tests:
   ```bash
   # Run tests (uses existing cassettes)
   uv run pytest tests/<library>/ -v
   
   # Record new cassettes (requires API keys)
   uv run pytest tests/<library>/ --record-mode=once
   ```

# Semantic Convention
All instrumentations in this repo must follow these semantic conventions:
- OpenTelemetry GenAI semantic conventions (gen_ai.* attributes) from https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/


## Custom Attribute Keys

### Prompt Messages (input to model)

**Important**: For multi-turn conversations or agent sessions, `gen_ai.prompt.*` should capture the **FULL conversation history** without the last response (which will be in the completion part), not just the latest message. Each message in the history gets an incrementing index (0, 1, 2, ...). See "Multi-Turn Conversation" example below.

**System Instruction**: If the library provides a system instruction/prompt (e.g., Google ADK's `instruction` field, OpenAI's `system` message), it should be captured as `gen_ai.prompt.0` with `role = "system"`. All other messages follow with incrementing indices.

| Attribute | Required | Type | Description | Examples |
| --------- | -------- | ---- | ----------- | -------- |
| `gen_ai.prompt.<n>.role` | ✓ | string | Role of message author | `system`, `user`, `assistant`, `tool` |
| `gen_ai.prompt.<n>.content` | content* | string | Message content | `What's the weather in Paris?` |
| `gen_ai.prompt.<n>.tool_call_id` | if role=tool | string | ID of the tool call this result is for | `call_abc123` |
| `gen_ai.prompt.<n>.tool_calls.<i>.id` | if has tool_calls | string | ID of tool call | `call_O8NOz8VlxosSASEsOY7LDUcP` |
| `gen_ai.prompt.<n>.tool_calls.<i>.type` | if has tool_calls | string | Type of tool call | `function` |
| `gen_ai.prompt.<n>.tool_calls.<i>.function.name` | if has tool_calls | string | Function name | `get_current_weather` |
| `gen_ai.prompt.<n>.tool_calls.<i>.function.arguments` | content* | string | Function arguments JSON | `{"location": "Seattle, WA"}` |

### Completion Choices (output from model)

**Important**: The assistant (LLM) response

| Attribute | Required | Type | Description | Examples |
| --------- | -------- | ---- | ----------- | -------- |
| `gen_ai.completion.0.role` | ✓ | string | Role of responder | `assistant` |
| `gen_ai.completion.0.finish_reason` | ✓ | string | Why generation stopped | `stop`, `tool_calls`, `error` |
| `gen_ai.completion.0.content` | content* | string | Response content | `The weather in Paris is 57°F` |
| `gen_ai.completion.0.tool_calls.<i>.id` | if has tool_calls | string | ID of tool call | `call_O8NOz8VlxosSASEsOY7LDUcP` |
| `gen_ai.completion.0.tool_calls.<i>.type` | if has tool_calls | string | Type of tool call | `function` |
| `gen_ai.completion.0.tool_calls.<i>.function.name` | if has tool_calls | string | Function name | `get_current_weather` |
| `gen_ai.completion.0.tool_calls.<i>.function.arguments` | content* | string | Function arguments JSON | `{"location": "Seattle, WA"}` |

### Custom tools definition keys (if tools available to the model)

| Attribute | Required | Type | Description | Examples |
| --------- | -------- | ---- | ----------- | -------- |
| `gen_ai.request.tools.<n>.type` | ✓ | string | Type of tool entry | `function` |
| `gen_ai.request.tools.<n>.function.name` | ✓ | string | Name of the function | `get_current_weather` |
| `gen_ai.request.tools.<n>.function.description` | ✓ | string | Description of the function | `Get the current weather in a given location` |
| `gen_ai.request.tools.<n>.function.parameters` | optional | string | JSON schema of parameters | `{"type": "object", "properties": {"location": {"type": "string", 
"description": "The city and state, e.g. San Francisco, CA"}, "unit": {"type": "string", "enum": 
["celsius", "fahrenheit"]}}, "required": ["location"]}` |

### Custom optional keys (capture when available in the library)
  | Attribute | Type | Description | Examples |
  | --------- | ---- | ----------- | -------- |
  | `gen_ai.request.user` | string | Unique identifier for the end-user | `user@company.com` |
  | `gen_ai.custom` | string | JSON of extra kwargs passed to the LLM call | `{"custom_param": "value"}` |

**Legend**:
- `<n>` = message/choice index (0, 1, 2, ...)
- `<i>` = tool call index within that message (0, 1, 2, ...)
- `content*` = Only captured when `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=True`
- Custom tools definition keys (tools available to the model)

**Note**: All required fields must be captured if the library provides them. Some libraries (like Google ADK with Python functions) may only have `name` and `description` available.

### Library-Specific Attributes

When a library has unique data not covered by standard conventions, propose custom attributes using the prefix `gen_ai.<library_name>.*`. Examples:
- `gen_ai.bedrock.agent_alias_id` - Bedrock agent alias identifier
- `gen_ai.openai.request.seed` - OpenAI request seed parameter
- `gen_ai.openai.response.service_tier` - OpenAI response service tier

Always propose these to the user before implementing, explaining what data they capture and why it's valuable for observability.


## Understanding Prompt vs Completion

Each LLM call creates ONE span with:
- **`gen_ai.prompt.*`** = Input messages sent TO the model (the **full** conversation history)
- **`gen_ai.completion.*`** = Output choices FROM the model (the response)

**Important Rules**:
1. `completion` refers to response choices (like OpenAI's `n` parameter), NOT conversation turns. Usually there's only `completion.0`.
2. **For multi-turn conversations, `gen_ai.prompt.*` MUST include the FULL conversation history**, not just the latest message. Each subsequent message is indexed incrementally (0, 1, 2, ...).
3. For agent/session-based libraries (like Google ADK, LangChain agents), access the session history to capture all previous messages.

### Example: Multi-Turn Conversation (3 turns, 3 spans)

This example shows a math tutor conversation where the user asks follow-up questions.

**Turn 1 Span: First question**
```
gen_ai.prompt.0.role = "user"
gen_ai.prompt.0.content = "What is 5 + 3?"
gen_ai.prompt.1.role = "assistant"
gen_ai.prompt.1.content = "The answer is 8."
gen_ai.completion.0.role = "assistant"
gen_ai.completion.0.content = "The answer is 8."
```
Note: After the response, the span includes BOTH the user message AND the assistant response in `prompt.*` (captured from session history).

**Turn 2 Span: Follow-up question (full history preserved)**
```
gen_ai.prompt.0.role = "user"
gen_ai.prompt.0.content = "What is 5 + 3?"
gen_ai.prompt.1.role = "assistant"
gen_ai.prompt.1.content = "The answer is 8."
gen_ai.prompt.2.role = "user"
gen_ai.prompt.2.content = "Now multiply that by 2"
gen_ai.prompt.3.role = "assistant"
gen_ai.prompt.3.content = "8 × 2 = 16"
gen_ai.completion.0.role = "assistant"
gen_ai.completion.0.content = "8 × 2 = 16"
```
Note: The span now has 4 prompt messages (indices 0-3) showing the complete conversation.

**Turn 3 Span: Recall question (complete 6-message history)**
```
gen_ai.prompt.0.role = "user"
gen_ai.prompt.0.content = "What is 5 + 3?"
gen_ai.prompt.1.role = "assistant"
gen_ai.prompt.1.content = "The answer is 8."
gen_ai.prompt.2.role = "user"
gen_ai.prompt.2.content = "Now multiply that by 2"
gen_ai.prompt.3.role = "assistant"
gen_ai.prompt.3.content = "8 × 2 = 16"
gen_ai.prompt.4.role = "user"
gen_ai.prompt.4.content = "What was my first question?"
gen_ai.prompt.5.role = "assistant"
gen_ai.prompt.5.content = "Your first question was 'What is 5 + 3?'"
gen_ai.completion.0.role = "assistant"
gen_ai.completion.0.content = "Your first question was 'What is 5 + 3?'"
```
Note: The model correctly recalls the first question because the full history was provided.

### Example: Tool Call Flow (2 separate spans)

**Span 1: User asks question → Model requests tool call**
```
gen_ai.prompt.0.role = "user"
gen_ai.prompt.0.content = "What's the weather in Tokyo?"
gen_ai.completion.0.role = "assistant"
gen_ai.completion.0.tool_calls.0.function.name = "get_weather"
gen_ai.completion.0.tool_calls.0.function.arguments = '{"city": "Tokyo"}'
```

**Span 2: Tool result provided → Model gives final answer**
```
gen_ai.prompt.0.role = "user"
gen_ai.prompt.0.content = "What's the weather in Tokyo?"
gen_ai.prompt.1.role = "assistant"
gen_ai.prompt.1.tool_calls.0.function.name = "get_weather"
gen_ai.prompt.2.role = "tool"
gen_ai.prompt.2.content = "Sunny and 25°C"
gen_ai.prompt.2.tool_call_id = "call_abc123"
gen_ai.completion.0.role = "assistant"
gen_ai.completion.0.content = "The weather in Tokyo is sunny and 25°C."
```

### Implementation Notes for Multi-Turn

When implementing instrumentation for libraries with session/conversation management:

1. **Access session history** - If the library maintains session state (like Google ADK's `InMemorySessionService`), access the session's events/history to get all previous messages.

2. **Capture after response** - The full conversation history (including the latest response) should be captured AFTER the LLM call completes, in the `_finalize` or response processing step.

3. **Map roles correctly** - Map library-specific roles to standard roles:
   - `model` → `assistant`
   - `function` → `tool`
   
4. **Include tool interactions** - If the conversation includes tool calls and responses, they should be captured as separate prompt messages with appropriate roles.

## Debugging with Console Span Exporter
For debugging OpenTelemetry spans and hierarchy issues, use the console exporter:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

tracer_provider = TracerProvider(
    resource=Resource.create({SERVICE_NAME: "debug-service"})
)
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)
```

This outputs all spans to console in JSON format, showing:
- Trace IDs and Span IDs
- Parent-child relationships between spans
- All attributes (verify they match semantic conventions)
- Timing information


## Testing

### Test Structure
Tests should be placed in `tests/<library_name>/` with this structure:
- `conftest.py` - Fixtures for instrumentor setup, client creation, VCR config
- `test_*.py` - Test files for each interface
- `cassettes/` - VCR recordings of API calls
- `utils.py` - Helper functions for assertions

### Key Fixtures
- `instrument_with_content` - Enables content capture (`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=True`)
- `instrument_no_content` - Disables content capture (captures structure but not text)
- `span_exporter` - `InMemorySpanExporter` for asserting on spans
- `metric_reader` - `InMemoryMetricReader` for asserting on metrics

### VCR Cassettes
Tests use VCR to record and replay API calls. VCR automatically records if the cassette file doesn't exist:

```bash
# Run tests (uses existing cassettes, records new ones if missing)
uv run pytest tests/<library>/ -v

# Delete cassettes to re-record them
rm -rf tests/<library>/cassettes/*.yaml
uv run pytest tests/<library>/ -v  # Will record fresh cassettes
```

**Important**: Always filter sensitive data in cassettes using `vcr_config` fixture:
```python
@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": [
            ("authorization", "Bearer test_api_key"),
        ],
    }
```


# Cursor Commands and Rules

This directory contains commands and rules for working with the llm-tracekit codebase.

## Commands

Commands are chat commands that can be triggered with `/` prefix:

- **`commands/start-ticket.md`** - Start work on a Linear ticket
  - Usage: `/start-ticket <TICKET_ID>`
  - Sets status, assigns ticket, creates branch, loads context

- **`commands/code-checks.md`** - Run code quality checks before committing
  - Usage: `/code-checks`
  - Runs linting, tests (UT → Integration → E2E), and commits

- **`commands/create-pr.md`** - Create a pull request
  - Usage: `/create-pr` or `/pr`
  - Generates PR with proper title format and description

- **`commands/self-improve.md`** - Analyze and improve Cursor rules and commands
  - Usage: `/self-improve`
  - Proactively identifies patterns and improvement opportunities

## Rules

Rules are agent instructions that apply intelligently or can be @-mentioned:

### Always Active
- **`rules/code-checks/`** - Requires code checks before declaring work complete

### On-Demand
- **`rules/ticket-listing/`** - How to list and filter Linear tickets

## Usage

- Type `/` in chat to see available commands
- Rules are applied automatically when relevant, or @-mention them manually
- Commands accept parameters after the command name