# Implementation Plan: Rewrite Strands Agents Tests

**Branch**: `001-strands-agent` | **Date**: 2026-03-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/002-rewrite-strands-tests/spec.md`

## Summary

Rewrite the strands-agents test suite to use real Strands SDK calls with VCR-recorded Bedrock responses, matching the patterns established by the openai-agents and google-adk adapters. This consolidates three old test files into a single `test_strands_agents.py` with a cleaned-up `conftest.py` and `utils.py`.

## Technical Context

**Language/Version**: Python 3.10–3.13  
**Primary Dependencies**: strands-agents (SDK), llm-tracekit-core, opentelemetry-sdk, pytest, pytest-vcr, pyyaml  
**Storage**: N/A (VCR cassettes stored as YAML files in tests/cassettes/)  
**Testing**: pytest with pytest-vcr, InMemorySpanExporter, InMemoryMetricReader  
**Target Platform**: CI (GitHub Actions) and local development  
**Project Type**: Test suite (within library workspace)  
**Performance Goals**: All tests complete in under 30 seconds using cassette replay  
**Constraints**: Tests must be synchronous (Strands SDK agent API is synchronous); must work offline with pre-recorded cassettes  
**Scale/Scope**: 8 test functions in 1 test file, 1 conftest, 1 utils, 1 __init__.py

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. OpenTelemetry Standards | PASS | Tests consume spans with standard GenAI attributes, no new attribute definitions |
| II. Workspace Modularity | PASS | All changes scoped to `instrumentations/strands-agents/tests/` |
| III. Instrumentation Consistency | PASS | No instrumentor code changes |
| IV. Test-Driven with VCR | PASS | This change directly implements this principle |
| V. Type Safety & Linting | PASS | Test files excluded from mypy; ruff compliance required |
| VI. Semantic Versioning | PASS | No version changes for test-only modifications |
| Security | PASS | FR-010 requires filtering AWS credentials from cassettes |

No gate violations. No complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/002-rewrite-strands-tests/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (files to modify)

```text
instrumentations/strands-agents/tests/
├── __init__.py                  # Already exists (keep)
├── conftest.py                  # REWRITE — align with openai-agents pattern
├── test_strands_agents.py       # REWRITE — consolidate all tests, use VCR
├── utils.py                     # REWRITE — keep span helpers, add assertion helpers
└── cassettes/                   # NEW — VCR cassettes recorded from Bedrock
    ├── test_simple_completion.yaml
    ├── test_agent_with_tool.yaml
    ├── test_agent_no_content_capture.yaml
    ├── test_agent_with_tool_no_content.yaml
    ├── test_agent_multi_cycle.yaml
    ├── test_agent_tool_error.yaml
    └── test_uninstrument_no_spans.yaml
```

### Files to delete

```text
instrumentations/strands-agents/tests/
├── test_agent_tracing.py        # DELETE — consolidated into test_strands_agents.py
├── test_content_capture.py      # DELETE — consolidated into test_strands_agents.py
└── test_uninstrumentation.py    # DELETE — consolidated into test_strands_agents.py
```

**Structure Decision**: Single test file with VCR cassettes, matching openai-agents and google-adk layout. Span helpers in utils.py, test infrastructure in conftest.py.

## Design Decisions

### DD-001: conftest.py Structure

Follow the openai-agents conftest pattern exactly, with Bedrock-specific adaptations:

1. **OTel fixtures** (same as openai-agents): `span_exporter`, `metric_reader`, `tracer_provider`, `meter_provider`
2. **VCR serializer** (same as openai-agents): `PrettyPrintJSONBody` with `LiteralBlockScalar` for YAML readability
3. **VCR response handler** (Bedrock-specific): `handle_recording_boto_response` for base64 event-stream encoding/decoding (already exists in current conftest)
4. **AWS env vars** (Bedrock-specific): Auto-set dummy `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_DEFAULT_REGION` when not present
5. **VCR config** (Bedrock-specific): Filter `Authorization`, `X-Amz-Security-Token` headers
6. **Instrumentor fixtures**: `instrument_with_content` and `instrument_no_content` — each creates/tears down `StrandsInstrumentor` with appropriate content capture env var

### DD-002: Test Function Mapping

| Test Function | Covers | VCR Cassette |
|---------------|--------|-------------|
| `test_simple_completion` | Simple agent, span hierarchy, content, SpanKind, metrics | Yes |
| `test_agent_with_tool` | Tool call, tool span attributes, multi-chat spans | Yes |
| `test_agent_no_content_capture` | Content disabled for chat spans | Yes |
| `test_agent_with_tool_no_content` | Content disabled for tool spans | Yes |
| `test_agent_multi_cycle` | Multiple cycle spans, token aggregation | Yes |
| `test_agent_tool_error` | Failing tool, error status | Yes |
| `test_uninstrument_no_spans` | Uninstrumentation lifecycle | Yes (2 cassettes via recording) |

### DD-003: Assertion Strategy

Tests assert **structural properties** only — never exact model output text:
- Span names start with expected prefixes (`invoke_agent`, `cycle`, `chat`, `execute_tool`)
- Span hierarchy via parent/child span IDs
- Attribute keys exist with correct types/values for structural attrs
- Content attributes present/absent based on capture toggle
- SpanKind correctness (INTERNAL for agent/cycle/tool, CLIENT for chat)
- Metric names exist in metric reader output

### DD-004: utils.py Design

Keep the existing span filtering helpers (`get_agent_spans`, `get_cycle_spans`, `get_chat_spans`, `get_tool_spans`, `get_spans_by_name_prefix`) and assertion helpers (`assert_agent_span_attributes`, `assert_chat_span_attributes`, `assert_tool_span_attributes`). These already match the needed pattern. The existing `assert_messages_in_span` and `assert_choices_in_span` are also retained for content capture tests.

## Post-Design Constitution Re-check

| Principle | Status | Notes |
|-----------|--------|-------|
| IV. Test-Driven with VCR | PASS | Design uses pytest-vcr cassettes, InMemory exporters, Arrange-Act-Assert |
| Security | PASS | DD-001 specifies credential filtering in VCR config |
| II. Workspace Modularity | PASS | All changes within `instrumentations/strands-agents/tests/` |

All gates pass post-design.
