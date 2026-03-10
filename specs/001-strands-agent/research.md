# Research: Strands Agents Instrumentation

**Branch**: `001-strands-agent` | **Date**: 2026-03-09

## 1. Integration Approach

### Decision: Hook-based instrumentation via HookProvider

### Rationale

The Strands Agents SDK offers two instrumentation surfaces:

1. **Built-in OpenTelemetry tracing** (`strands.telemetry.tracer`) — the SDK already creates its own spans internally (agent, cycle, model invoke). However, these use Strands' own attribute naming and span structure, not the GenAI semantic conventions used by llm-tracekit.

2. **Hooks system** (`strands.hooks`) — a typed, composable callback system with events for every lifecycle phase: `BeforeInvocationEvent`, `AfterInvocationEvent`, `BeforeModelCallEvent`, `AfterModelCallEvent`, `BeforeToolCallEvent`, `AfterToolCallEvent`, `MessageAddedEvent`, `AgentInitializedEvent`.

The hooks system is the right integration point because:
- It provides granular access to agent, model, and tool lifecycle events.
- It allows creating spans with GenAI semantic attributes consistent with other llm-tracekit adapters.
- It doesn't require monkey-patching internals.
- It matches the `TracingProcessor` pattern used by the OpenAI Agents adapter (register a processor/hook provider → receive lifecycle events → map to OTel spans).

### Alternatives Considered

| Alternative | Why Rejected |
|------------|--------------|
| **Enrich existing Strands spans** (like Google ADK) | Strands spans use non-standard attribute names; enriching them would create inconsistent attribute sets. Also, the Strands tracer may not be initialized if the user configures their own tracer provider. |
| **Wrap/patch Strands internals** (like OpenAI/Bedrock) | Unnecessary complexity given the hooks API exists. Hooks are the supported extension point; patching internals would be fragile across SDK versions. |
| **Disable Strands built-in tracing and replace entirely** | Would lose any Strands-specific spans that users may want. Better to coexist — the user can disable Strands' own telemetry if they prefer llm-tracekit's spans exclusively. |

## 2. Span Hierarchy Design

### Decision: Agent → Cycle → Model/Tool (3-level hierarchy)

### Rationale

The Strands Agents SDK's event loop is explicitly cycle-based (`event_loop_cycle()`), making cycles a natural span boundary. This maps to:

```
invoke_agent {agent_name}           (root, per invocation, INTERNAL)
  └── cycle {cycle_id}               (per reasoning cycle, INTERNAL)
        ├── chat {model}              (per model call, CLIENT)
        └── execute_tool {tool_name}  (per tool execution, INTERNAL)
```

- `invoke_agent {agent_name}` — follows OTel GenAI semconv (`gen_ai.operation.name = "invoke_agent"`)
- `cycle {cycle_id}` — Strands-specific (no standard exists for reasoning cycles)
- `chat {model}` — standard GenAI span, consistent with all other adapters
- `execute_tool {tool_name}` — follows OTel GenAI semconv (`gen_ai.operation.name = "execute_tool"`)

### Alternatives Considered

| Alternative | Why Rejected |
|------------|--------------|
| Flat hierarchy (agent only) | Loses the cycle-level granularity that is unique to Strands and valuable for debugging multi-step reasoning. |
| 2-level (agent → model/tool) | Possible but loses cycle boundaries. Cycles are a first-class concept in Strands and map cleanly to the hooks API. |

## 3. Coexistence with Strands Built-in Tracing

### Decision: Independent — do not disable or modify Strands' own tracing

### Rationale

The adapter creates its own spans via the hooks system without interfering with Strands' internal `tracer.py` spans. However, running both simultaneously produces duplicate traces — Strands' native spans use non-standard attribute formats (span events instead of per-index attributes) that are incompatible with Coralogix's AI Center rendering. Users should **not** initialize `StrandsTelemetry` when using llm-tracekit to avoid duplicate traces and confusion. The quickstart and README must clearly instruct users to skip `StrandsTelemetry.init()` / `StrandsTelemetry.setup()`.

## 4. Content Capture Attributes

### Decision: Use the per-index format (`gen_ai.prompt.{n}.content`, `gen_ai.completion.{n}.content`)

### Rationale

All existing llm-tracekit adapters use the per-index format defined in `_extended_gen_ai_attributes.py`. The newer `gen_ai.input.messages` / `gen_ai.output.messages` format is not used anywhere in the codebase. For consistency, the Strands adapter should use the same format and reuse the `generate_message_attributes` and `generate_choice_attributes` functions from core.

## 5. Package Name and Dependencies

### Decision: `llm-tracekit-strands-agents`, depending on `strands-agents` and `llm-tracekit-core`

### Rationale

Follows the naming pattern: `llm-tracekit-{provider}`. The `strands-agents` package is the PyPI name for the Strands Agents SDK. Entry point: `strands_agents = "llm_tracekit.strands_agents:StrandsInstrumentor"`.
