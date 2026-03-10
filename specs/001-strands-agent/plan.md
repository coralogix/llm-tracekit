# Implementation Plan: Strands Agents Instrumentation

**Branch**: `001-strands-agent` | **Date**: 2026-03-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-strands-agent/spec.md`

## Summary

Add a new `llm-tracekit-strands` instrumentation package that provides OpenTelemetry tracing for the Strands Agents SDK. The adapter uses the Strands hooks system (HookProvider pattern) to capture agent lifecycle events and map them to OTel spans with GenAI semantic attributes, consistent with existing adapters.

## Technical Context

**Language/Version**: Python 3.10–3.13
**Primary Dependencies**: strands-agents, llm-tracekit-core, opentelemetry-instrumentation
**Testing**: pytest, pytest-asyncio, pytest-vcr, assertpy
**Project Type**: Library (instrumentation package within uv workspace)
**Constraints**: Must not add overhead >5% to agent execution; must coexist with Strands' built-in tracing

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. OpenTelemetry Standards | ✅ Pass | Uses GenAI semantic attributes from core |
| II. Workspace Modularity | ✅ Pass | New independent package in `instrumentations/strands/` |
| III. Instrumentation Consistency | ✅ Pass | Follows BaseInstrumentor pattern; HookProvider replaces wrapt (analogous to TracingProcessor in OpenAI Agents) |
| IV. Test-Driven with VCR | ✅ Pass | Tests will use pytest-vcr with cassettes, InMemorySpanExporter |
| V. Type Safety & Linting | ✅ Pass | Type hints, ruff, mypy |
| VI. Semantic Versioning | ✅ Pass | v1.0.0 initial release |

## Project Structure

### Documentation (this feature)

```text
specs/001-strands-agent/
├── spec.md
├── plan.md              # This file
├── research.md          # Integration approach decisions
├── data-model.md        # Span entities and attribute tables
├── quickstart.md        # Usage examples
├── contracts/
│   └── public-api.md    # Public API contract
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
instrumentations/strands/
├── src/llm_tracekit/strands/
│   ├── __init__.py           # Public exports
│   ├── instrumentor.py       # StrandsInstrumentor (BaseInstrumentor)
│   ├── hook_provider.py      # StrandsHookProvider (maps hooks → spans)
│   └── package.py            # _instruments tuple
├── tests/
│   ├── conftest.py           # Fixtures (span exporter, metric reader, instrumentor)
│   ├── utils.py              # Assert helpers
│   ├── test_agent_tracing.py # US1: basic agent tracing
│   ├── test_content_capture.py  # US2: content capture
│   ├── test_uninstrument.py  # US4: uninstrumentation
│   └── cassettes/            # VCR cassettes
├── pyproject.toml
├── pyrightconfig.json
├── README.md
└── LICENSE
```

**Structure Decision**: Follows the same layout as `instrumentations/openai-agents/`. Uses `hook_provider.py` instead of `tracing_processor.py` since Strands uses hooks rather than a tracing processor API. The remaining structure is identical.

## Integration Design

### Hook-to-Span Mapping

The `StrandsHookProvider` implements the Strands `HookProvider` protocol and registers callbacks for agent lifecycle events. Each callback creates or ends an OTel span.

```text
BeforeInvocationEvent  → start agent span ("invoke_agent {agent_name}")
  cycle transition     → start cycle span ("cycle {cycle_id}")
  BeforeModelCallEvent → start model span ("chat {model}")
  AfterModelCallEvent  → end model span (record tokens, content)
  BeforeToolCallEvent  → start tool span ("execute_tool {tool_name}")
  AfterToolCallEvent   → end tool span
  cycle end            → end cycle span
AfterInvocationEvent   → end agent span (record aggregated metrics)
```

Cycle spans are managed by tracking cycle transitions within the model/tool callbacks (a new cycle starts when BeforeModelCallEvent fires with a new cycle ID).

### Instrumentation Flow

1. `StrandsInstrumentor._instrument()` creates a `StrandsHookProvider` with the tracer.
2. It patches `Agent.__init__` via wrapt to inject the hook provider into every new agent instance (`agent.hooks.add_hook_provider(provider)`).
3. `_uninstrument()` removes the patch and disables the hook provider.

This mirrors how OpenAI Agents uses `add_trace_processor()` — the hook provider is registered once and receives events from all agent instances.

## Complexity Tracking

No constitution violations. The hook-based approach avoids unnecessary complexity.

## Design Artifacts

| Artifact | Path | Status |
|----------|------|--------|
| Research | [research.md](research.md) | ✅ Complete |
| Data Model | [data-model.md](data-model.md) | ✅ Complete |
| Public API | [contracts/public-api.md](contracts/public-api.md) | ✅ Complete |
| Quickstart | [quickstart.md](quickstart.md) | ✅ Complete |
