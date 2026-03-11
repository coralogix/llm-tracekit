# Research: Rewrite Strands Agents Tests

## R-001: VCR Pattern for Bedrock Event-Stream Responses

**Decision**: Reuse the existing `handle_recording_boto_response` function from the current `conftest.py`.

**Rationale**: The current strands-agents conftest already handles the Bedrock-specific challenge of binary event-stream (`application/vnd.amazon.eventstream`) responses. During recording, event-stream bodies are base64-encoded for YAML storage; during playback, they are decoded back to binary. This is proven to work and is unique to Bedrock (openai-agents doesn't need this).

**Alternatives considered**:
- Writing a custom VCR serializer for binary data — unnecessary, base64 approach is simpler and already tested.
- Using `pytest-httpserver` instead of VCR — rejected because VCR is the project standard (constitution IV).

## R-002: Synchronous vs Async Test Functions

**Decision**: Use synchronous test functions (`def test_*`, not `async def test_*`).

**Rationale**: The Strands SDK `Agent` invocation is synchronous — you call `agent("prompt")` directly. Unlike OpenAI Agents SDK (which uses `await Runner.run()`) or Google ADK (which uses `async for _ in runner.run_async()`), Strands does not require an async event loop for basic agent invocation. The existing strands-agents tests are already synchronous and this is correct.

**Alternatives considered**:
- Using `pytest-asyncio` with async wrappers — unnecessary complexity since the SDK API is synchronous.

## R-003: Tool Definition Pattern for Strands

**Decision**: Use `@Agent.tool` decorator for defining test tools.

**Rationale**: The existing test code uses `@Agent.tool` which is the idiomatic Strands SDK approach. This differs from OpenAI Agents (`@function_tool`) and Google ADK (plain functions passed to `tools=[]`). The tool definition requires a docstring with `Args:` and `Returns:` sections for the SDK to generate tool schemas.

**Alternatives considered**:
- Using `strands.tool` decorator — `@Agent.tool` is the documented and tested approach in the existing code.
- Defining tools via `ToolConfig` objects — more verbose, less readable for test purposes.

## R-004: Model ID for Test Cassettes

**Decision**: Use `us.anthropic.claude-sonnet-4-20250514-v1:0` via `BedrockModel(model_id=MODEL_ID)`.

**Rationale**: User explicitly specified Claude Sonnet 4.6 on Bedrock. The cross-region model ID prefix `us.` ensures availability. The existing test code already uses this model ID and `BedrockModel` class.

**Alternatives considered**:
- `anthropic.claude-sonnet-4-20250514-v1:0` (without region prefix) — less reliable for cross-region inference.
- Other models — user explicitly specified this model.

## R-005: Span Name Prefixes for Assertion Helpers

**Decision**: Use span name prefixes matching the instrumentor's naming:
- Agent spans: `"invoke_agent"` (e.g., `invoke_agent Agent`)
- Cycle spans: `"cycle"` (e.g., `cycle 0`)
- Chat spans: `"chat"` (e.g., `chat us.anthropic.claude-sonnet-4-20250514-v1:0`)
- Tool spans: `"execute_tool"` (e.g., `execute_tool get_weather`)

**Rationale**: The `hook_provider.py` implementation uses these exact prefixes in `span_name = f"invoke_agent {agent_name}"`, `f"cycle {cycle_id}"`, `f"chat {model_id}"`, and `f"execute_tool {tool_name}"`. The existing `utils.py` helpers already use `startswith()` with these prefixes.

**Alternatives considered**: None — must match instrumentor implementation.

## R-006: Content Capture Toggle Mechanism

**Decision**: Two instrumentor fixtures:
- `instrument_with_content`: Sets `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=True` env var, creates instrumentor.
- `instrument_no_content`: Pops the env var, creates instrumentor.

**Rationale**: Matches the existing conftest pattern. The instrumentor reads `is_content_enabled()` at instrument time and also checks it per-event. The env var is the standard mechanism shared across all adapters.

**Alternatives considered**:
- Passing `capture_content` directly to instrumentor — the instrumentor reads from env var via `is_content_enabled()`, consistent with other adapters.
