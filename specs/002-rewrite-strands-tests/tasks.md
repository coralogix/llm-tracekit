# Tasks: Rewrite Strands Agents Tests

**Input**: Design documents from `specs/002-rewrite-strands-tests/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Tests**: This feature IS the test rewrite. All tasks produce test code.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Clean up old test files and prepare the test directory structure

- [ ] T001 Delete old test files: `instrumentations/strands-agents/tests/test_agent_tracing.py`, `instrumentations/strands-agents/tests/test_content_capture.py`, `instrumentations/strands-agents/tests/test_uninstrumentation.py`
- [ ] T002 Verify `instrumentations/strands-agents/tests/__init__.py` exists (already present, keep as-is)

---

## Phase 2: Foundational (Test Infrastructure)

**Purpose**: Rewrite `conftest.py` and `utils.py` — MUST be complete before any test functions can work

**⚠️ CRITICAL**: No test function work can begin until this phase is complete

- [ ] T003 [P] Rewrite `instrumentations/strands-agents/tests/conftest.py` — follow the openai-agents conftest pattern with these components:
  - OTel fixtures: `span_exporter` (InMemorySpanExporter), `metric_reader` (InMemoryMetricReader), `tracer_provider` (TracerProvider with SimpleSpanProcessor), `meter_provider` (MeterProvider with metric_reader)
  - VCR YAML serializer: `LiteralBlockScalar` class, `literal_block_scalar_presenter`, `process_string_value`, `convert_body_to_literal`, `PrettyPrintJSONBody` class with serialize/deserialize, `fixture_vcr` module-scoped autouse fixture
  - Bedrock VCR handler: `handle_recording_boto_response` for base64 event-stream encoding/decoding (reuse from existing conftest)
  - AWS env vars: `aws_env_vars` autouse fixture setting dummy `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_DEFAULT_REGION`
  - VCR config: `vcr_config` module-scoped fixture filtering `X-Amz-Security-Token` and `Authorization` headers, with `decode_compressed_response` and `before_record_response` for Bedrock
  - Instrumentor fixtures: `instrument_with_content` (sets `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=True`, creates StrandsInstrumentor, instruments with tracer/meter provider, yields, uninstruments) and `instrument_no_content` (pops env var, same lifecycle)
  - Graceful skip: `try/except ImportError` around `StrandsInstrumentor` import with `pytest.skip` for missing SDK

- [ ] T004 [P] Rewrite `instrumentations/strands-agents/tests/utils.py` — keep existing span filtering and assertion helpers:
  - Span filters: `get_spans_by_name_prefix(exporter, prefix)`, `get_agent_spans(exporter)` (prefix `"invoke_agent"`), `get_cycle_spans(exporter)` (prefix `"cycle"`), `get_chat_spans(exporter)` (prefix `"chat"`), `get_tool_spans(exporter)` (prefix `"execute_tool"`)
  - Attribute assertions: `assert_agent_span_attributes(span, agent_name, model)`, `assert_chat_span_attributes(span, request_model, input_tokens, output_tokens)`, `assert_tool_span_attributes(span, tool_name)`
  - Content assertions: `assert_messages_in_span(span, expected_messages, expect_content)`, `assert_choices_in_span(span, expected_choices, expect_content)`

**Checkpoint**: Test infrastructure ready — individual test functions can now be written

---

## Phase 3: User Story 1 — Consistent Test Pattern (Priority: P1) + User Story 2 — Simple Completion (Priority: P1) 🎯 MVP

**Goal**: Verify a basic Strands agent invocation produces correct span hierarchy and attributes with real SDK + VCR. This is the MVP — if this passes, the core test pattern is validated.

**Independent Test**: Run `pytest tests/test_strands_agents.py::test_simple_completion -v` and verify agent span, cycle span, chat span hierarchy and attributes.

### Implementation

- [ ] T005 [US1][US2] Write `test_simple_completion` in `instrumentations/strands-agents/tests/test_strands_agents.py`:
  - Define `MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"` module constant
  - Define `_make_agent(system_prompt, tools)` helper using `BedrockModel(model_id=MODEL_ID)` and `Agent(model=model, system_prompt=system_prompt, tools=tools or [])`
  - Mark with `@pytest.mark.vcr()`
  - Accept fixtures: `span_exporter`, `metric_reader`, `instrument_with_content`
  - Create agent via `_make_agent()`, invoke with `agent("Say 'This is a test.' and nothing else.")`
  - Assert: exactly 1 agent span via `get_agent_spans`, call `assert_agent_span_attributes` with agent name and MODEL_ID
  - Assert: at least 1 cycle span via `get_cycle_spans`
  - Assert: exactly 1 chat span via `get_chat_spans`, call `assert_chat_span_attributes` with MODEL_ID
  - Assert: 0 tool spans via `get_tool_spans`
  - Assert span hierarchy: cycle parent is agent span, chat parent is cycle span (via `.parent.span_id`)
  - Assert SpanKind: agent is INTERNAL, chat is CLIENT
  - Assert content on chat span: `gen_ai.completion.0.role == "assistant"`, `gen_ai.completion.0.content` exists
  - Assert metrics: `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` present in `metric_reader.get_metrics_data()`
- [ ] T006 [US1][US2] Record VCR cassette for `test_simple_completion` by running the test with live AWS credentials (creates `instrumentations/strands-agents/tests/cassettes/test_simple_completion.yaml`)

**Checkpoint**: MVP validated — basic test pattern works with real SDK and VCR cassettes

---

## Phase 4: User Story 3 — Tool Usage Tracing (Priority: P1)

**Goal**: Verify tool calls produce correct tool spans with attributes and multi-cycle chat spans

**Independent Test**: Run `pytest tests/test_strands_agents.py::test_agent_with_tool -v`

### Implementation

- [ ] T007 [US3] Write `test_agent_with_tool` in `instrumentations/strands-agents/tests/test_strands_agents.py`:
  - Define `get_weather` tool using `@Agent.tool` decorator with docstring (Args/Returns sections)
  - Create agent with `_make_agent(system_prompt="Use the get_weather tool when asked about weather.", tools=[get_weather])`
  - Invoke with `agent("What's the weather in Tel Aviv?")`
  - Assert: 1 agent span, at least 1 tool span, at least 2 chat spans (tool_use + final)
  - Assert tool span: `assert_tool_span_attributes(tool_spans[0], tool_name="get_weather")`, SpanKind.INTERNAL, `gen_ai.tool.status == "success"`, `input` and `output` attributes exist
  - Assert first chat completion has `gen_ai.completion.0.tool_calls.0.function.name == "get_weather"`
  - Assert last chat has `gen_ai.completion.0.role == "assistant"` and `gen_ai.completion.0.content` exists
- [ ] T008 [US3] Record VCR cassette for `test_agent_with_tool` (creates `instrumentations/strands-agents/tests/cassettes/test_agent_with_tool.yaml`)

**Checkpoint**: Tool usage tracing verified

---

## Phase 5: User Story 4 — Content Capture Toggle (Priority: P2)

**Goal**: Verify content attributes are absent when capture is disabled

**Independent Test**: Run `pytest tests/test_strands_agents.py::test_agent_no_content_capture tests/test_strands_agents.py::test_agent_with_tool_no_content -v`

### Implementation

- [ ] T009 [P] [US4] Write `test_agent_no_content_capture` in `instrumentations/strands-agents/tests/test_strands_agents.py`:
  - Mark with `@pytest.mark.vcr()`
  - Accept fixtures: `span_exporter`, `instrument_no_content`
  - Create agent via `_make_agent()`, invoke with `agent("Say 'Hello world.'")`
  - Assert: 1 chat span exists
  - Assert content absent: `gen_ai.prompt.0.content` NOT in attributes, `gen_ai.completion.0.content` NOT in attributes
  - Assert structural present: `assert_chat_span_attributes` passes with MODEL_ID
- [ ] T010 [P] [US4] Write `test_agent_with_tool_no_content` in `instrumentations/strands-agents/tests/test_strands_agents.py`:
  - Define `calculator` tool using `@Agent.tool`
  - Create agent with calculator tool, invoke with `agent("What is 2 + 2?")`
  - Assert: at least 1 tool span
  - Assert tool content absent: `input` NOT in attributes, `output` NOT in attributes
- [ ] T011 [US4] Record VCR cassettes for `test_agent_no_content_capture` and `test_agent_with_tool_no_content` (creates 2 cassette files)

**Checkpoint**: Content capture toggle verified for both chat and tool spans

---

## Phase 6: User Story 5 — Tool Error + User Story 6 — Multi-Cycle (Priority: P2)

**Goal**: Verify error handling on tool spans and multi-cycle span hierarchy

**Independent Test**: Run `pytest tests/test_strands_agents.py::test_agent_tool_error tests/test_strands_agents.py::test_agent_multi_cycle -v`

### Implementation

- [ ] T012 [P] [US5] Write `test_agent_tool_error` in `instrumentations/strands-agents/tests/test_strands_agents.py`:
  - Define `failing_tool` using `@Agent.tool` that raises `ValueError("Tool failed as intended for testing")`
  - Create agent with failing_tool, invoke with `agent("Do something.")`
  - Assert: at least 1 tool span
  - Assert tool span: `gen_ai.tool.status == "error"`
- [ ] T013 [P] [US6] Write `test_agent_multi_cycle` in `instrumentations/strands-agents/tests/test_strands_agents.py`:
  - Define `get_capital` tool using `@Agent.tool`
  - Create agent with get_capital tool, invoke with `agent("What is the capital of France?")`
  - Assert: 1 agent span, at least 2 cycle spans
  - Assert all cycle spans are children of agent span
  - Assert agent span has `gen_ai.usage.input_tokens > 0` and `gen_ai.usage.output_tokens > 0`
- [ ] T014 [US5][US6] Record VCR cassettes for `test_agent_tool_error` and `test_agent_multi_cycle` (creates 2 cassette files)

**Checkpoint**: Error handling and multi-cycle tracing verified

---

## Phase 7: User Story 8 — Metrics (Priority: P2)

**Goal**: Verify metrics are emitted (combined with test_simple_completion assertions)

**Independent Test**: Metrics are already asserted in `test_simple_completion` (T005). No separate test function needed — the metrics verification is embedded in the simple completion test.

### Implementation

- [ ] T015 [US8] Verify `test_simple_completion` (T005) includes metric assertions for `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` — no additional test function needed, just confirm coverage

**Checkpoint**: Metrics verification confirmed

---

## Phase 8: User Story 7 — Uninstrumentation (Priority: P3)

**Goal**: Verify no spans are emitted after uninstrument()

**Independent Test**: Run `pytest tests/test_strands_agents.py::test_uninstrument_no_spans -v`

### Implementation

- [ ] T016 [US7] Write `test_uninstrument_no_spans` in `instrumentations/strands-agents/tests/test_strands_agents.py`:
  - Accept fixtures: `span_exporter`, `tracer_provider`, `meter_provider` (manage instrumentor manually)
  - Import `StrandsInstrumentor` and `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`
  - Set env var to `"True"`, create instrumentor, call `instrument(tracer_provider, meter_provider)`
  - Create agent, invoke — assert spans are produced (len > 0)
  - Call `uninstrument()`, clear exporter
  - Create new agent, invoke — assert no new agent spans (`invoke_agent` prefix)
  - Clean up env var
- [ ] T017 [US7] Record VCR cassette for `test_uninstrument_no_spans` (creates `instrumentations/strands-agents/tests/cassettes/test_uninstrument_no_spans.yaml` — will contain 2 Bedrock interactions)

**Checkpoint**: Uninstrumentation lifecycle verified

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [ ] T018 Run `ruff check instrumentations/strands-agents/tests/` and fix any linting issues
- [ ] T019 Run `ruff format instrumentations/strands-agents/tests/` to ensure formatting compliance
- [ ] T020 Run full test suite `cd instrumentations/strands-agents && uv run pytest tests/ -v` and verify all 8 tests pass with cassettes
- [ ] T021 Verify no old test files remain: confirm `test_agent_tracing.py`, `test_content_capture.py`, `test_uninstrumentation.py` are deleted

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all test functions
- **Phase 3 (US1+US2 MVP)**: Depends on Phase 2 — write first test + cassette
- **Phase 4 (US3)**: Depends on Phase 2 — can run in parallel with Phase 3
- **Phase 5 (US4)**: Depends on Phase 2 — can run in parallel with Phase 3/4
- **Phase 6 (US5+US6)**: Depends on Phase 2 — can run in parallel with Phase 3/4/5
- **Phase 7 (US8)**: Depends on Phase 3 (metrics are asserted in test_simple_completion)
- **Phase 8 (US7)**: Depends on Phase 2 — can run in parallel with other phases
- **Polish (Phase 9)**: Depends on all test phases complete

### User Story Dependencies

- **US1+US2 (P1)**: After Foundational — no dependencies on other stories
- **US3 (P1)**: After Foundational — no dependencies on other stories
- **US4 (P2)**: After Foundational — no dependencies on other stories
- **US5 (P2)**: After Foundational — no dependencies on other stories
- **US6 (P2)**: After Foundational — no dependencies on other stories
- **US7 (P3)**: After Foundational — no dependencies on other stories
- **US8 (P2)**: After US1+US2 (metrics verified there) — no separate implementation needed

### Parallel Opportunities

- T003 and T004 (conftest + utils) can run in parallel — different files
- T009 and T010 (no-content tests) can run in parallel — same file but independent functions
- T012 and T013 (tool error + multi-cycle) can run in parallel — same file but independent functions
- All test phases (3–8) can run in parallel after Phase 2 completes (they all write to the same test file but are independent functions)

---

## Parallel Example: Phase 2

```bash
# Launch foundational tasks in parallel (different files):
Task T003: "Rewrite conftest.py"
Task T004: "Rewrite utils.py"
```

## Parallel Example: Phases 3–8

```bash
# After Phase 2, all test functions can be written in parallel:
Task T005: "test_simple_completion"     # US1+US2
Task T007: "test_agent_with_tool"       # US3
Task T009: "test_agent_no_content_capture"  # US4
Task T010: "test_agent_with_tool_no_content"  # US4
Task T012: "test_agent_tool_error"      # US5
Task T013: "test_agent_multi_cycle"     # US6
Task T016: "test_uninstrument_no_spans" # US7
```

---

## Implementation Strategy

### MVP First (US1+US2 Only)

1. Complete Phase 1: Delete old files
2. Complete Phase 2: Rewrite conftest.py + utils.py
3. Complete Phase 3: Write test_simple_completion + record cassette
4. **STOP and VALIDATE**: Run `pytest tests/test_strands_agents.py::test_simple_completion -v`
5. If passing: core VCR + real SDK pattern is validated

### Incremental Delivery

1. Phase 1 + 2 → Infrastructure ready
2. Add test_simple_completion → Validate MVP
3. Add test_agent_with_tool → Tool tracing validated
4. Add no-content tests → Content toggle validated
5. Add error + multi-cycle tests → Edge cases validated
6. Add uninstrument test → Lifecycle validated
7. Phase 9 → Lint, format, full suite pass

---

## Notes

- All tests are synchronous (no `async def`, no `pytest.mark.asyncio`)
- Cassettes MUST be recorded with real AWS credentials before tests can replay offline
- Assertions check structural span properties, never exact model output text
- The `_make_agent` helper centralizes agent creation to avoid duplication
- Each test function gets its own VCR cassette named after the function
- Commit after each phase to maintain rollback capability
