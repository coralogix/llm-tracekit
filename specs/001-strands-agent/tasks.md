# Tasks: Strands Agent Instrumentation Adapter

**Input**: Design documents from `/specs/001-strands-agent/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/public-api.md, quickstart.md

**Tests**: Included — the spec references pytest, pytest-vcr, and InMemorySpanExporter. Test tasks follow TDD (write tests first, verify they fail, then implement).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Package root**: `instrumentations/strands/`
- **Source**: `instrumentations/strands/src/llm_tracekit/strands/`
- **Tests**: `instrumentations/strands/tests/`

---

## Phase 1: Setup

**Purpose**: Scaffold the `llm-tracekit-strands` package within the uv workspace

- [ ] T001 Create package directory structure per plan.md: `instrumentations/strands/src/llm_tracekit/strands/`, `instrumentations/strands/tests/`, `instrumentations/strands/tests/cassettes/`
- [ ] T002 Create `instrumentations/strands/pyproject.toml` with dependencies (`strands-agents>=1.0.0`, `llm-tracekit-core>=1.0.0`, `opentelemetry-instrumentation>=0.53b1`), entry point (`strands = "llm_tracekit.strands:StrandsInstrumentor"`), and dev dependencies (`pytest`, `pytest-asyncio`, `pytest-vcr`, `assertpy`)
- [ ] T003 [P] Create `instrumentations/strands/pyrightconfig.json` matching the OpenAI Agents adapter config
- [ ] T004 [P] Create `instrumentations/strands/LICENSE` (Apache 2.0, matching other adapters)
- [ ] T005 Register the package in the workspace root `pyproject.toml` under `tool.uv.workspace.members`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core module stubs that all user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Create `instrumentations/strands/src/llm_tracekit/strands/package.py` with `_instruments` tuple containing `("strands-agents", ">=1.0.0")`
- [ ] T007 Create `instrumentations/strands/src/llm_tracekit/strands/instrumentor.py` with `StrandsInstrumentor(BaseInstrumentor)` skeleton — implement `instrumentation_dependencies()` returning `_instruments`, and stub `_instrument()` / `_uninstrument()` methods
- [ ] T008 Create `instrumentations/strands/src/llm_tracekit/strands/hook_provider.py` with `StrandsHookProvider` class skeleton implementing the Strands `HookProvider` protocol — stub all hook callbacks (`before_invocation`, `after_invocation`, `before_model_call`, `after_model_call`, `before_tool_call`, `after_tool_call`)
- [ ] T009 Create `instrumentations/strands/src/llm_tracekit/strands/__init__.py` with public exports per `contracts/public-api.md`: `StrandsInstrumentor`, `setup_export_to_coralogix`, `enable_capture_content`, `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`
- [ ] T010 Create `instrumentations/strands/tests/conftest.py` with test fixtures: `InMemorySpanExporter`, `InMemoryMetricReader`, `StrandsInstrumentor` setup/teardown, matching the OpenAI Agents adapter test fixtures
- [ ] T011 [P] Create `instrumentations/strands/tests/utils.py` with span assertion helpers (find span by name, assert attributes, assert parent-child relationships)
- [ ] T012 Verify the package installs and imports correctly: `uv sync` and `python -c "from llm_tracekit.strands import StrandsInstrumentor"`

**Checkpoint**: Package structure ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Basic Agent Tracing (Priority: P1) MVP

**Goal**: A developer activates the instrumentation and sees a complete span hierarchy (agent → cycle → model/tool) with GenAI semantic attributes for every Strands agent invocation.

**Independent Test**: Instrument a Strands agent with one tool, invoke it, and assert the expected span hierarchy with correct attributes using `InMemorySpanExporter`.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T013 [P] [US1] Test basic agent span creation in `instrumentations/strands/tests/test_agent_tracing.py` — invoke agent, assert `invoke_agent {name}` span exists with `gen_ai.system`, `gen_ai.operation.name`, `gen_ai.agent.name`, `gen_ai.agent.tools`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` attributes
- [ ] T014 [P] [US1] Test cycle span creation in `instrumentations/strands/tests/test_agent_tracing.py` — assert `cycle {id}` spans as children of agent span with `strands.agent.cycle.id` and optional `event_loop.parent_cycle_id`
- [ ] T015 [P] [US1] Test model invocation span in `instrumentations/strands/tests/test_agent_tracing.py` — assert `chat {model}` span as child of cycle span with `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.response.finish_reasons`, `gen_ai.usage.cache_read_input_tokens`, `gen_ai.usage.cache_write_input_tokens`
- [ ] T016 [P] [US1] Test tool span creation in `instrumentations/strands/tests/test_agent_tracing.py` — assert `execute_tool {name}` span as child of cycle span with `gen_ai.tool.call.id`, `gen_ai.tool.status`, `name`, `type`
- [ ] T017 [P] [US1] Test multi-cycle agent in `instrumentations/strands/tests/test_agent_tracing.py` — invoke agent requiring multiple cycles, assert each cycle produces its own span with model/tool children
- [ ] T018 [P] [US1] Test agent with no tools in `instrumentations/strands/tests/test_agent_tracing.py` — invoke agent without tools, assert agent → cycle → model spans only (no tool spans)
- [ ] T019 [P] [US1] Test error handling in `instrumentations/strands/tests/test_agent_tracing.py` — trigger model error, assert span status is ERROR with `error.type` attribute; trigger tool error, assert same
- [ ] T020 [P] [US1] Test metrics emission in `instrumentations/strands/tests/test_agent_tracing.py` — assert `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` histograms are recorded via `InMemoryMetricReader`

### Implementation for User Story 1

- [ ] T021 [US1] Implement `StrandsHookProvider` agent span logic in `instrumentations/strands/src/llm_tracekit/strands/hook_provider.py` — `before_invocation` starts agent span (`invoke_agent {name}`, kind=INTERNAL) with attributes per data-model.md; `after_invocation` records aggregated token usage and ends span
- [ ] T022 [US1] Implement `StrandsHookProvider` cycle span logic in `instrumentations/strands/src/llm_tracekit/strands/hook_provider.py` — track cycle transitions via cycle ID changes in model/tool callbacks; start/end cycle spans with `strands.agent.cycle.id` and `event_loop.parent_cycle_id`
- [ ] T023 [US1] Implement `StrandsHookProvider` model span logic in `instrumentations/strands/src/llm_tracekit/strands/hook_provider.py` — `before_model_call` starts `chat {model}` span (kind=CLIENT); `after_model_call` records token usage (including cache tokens), finish reasons, and ends span
- [ ] T024 [US1] Implement `StrandsHookProvider` tool span logic in `instrumentations/strands/src/llm_tracekit/strands/hook_provider.py` — `before_tool_call` starts `execute_tool {name}` span (kind=INTERNAL) with `gen_ai.tool.call.id`, `name`, `type`; `after_tool_call` records `gen_ai.tool.status` and ends span
- [ ] T025 [US1] Implement error handling in `instrumentations/strands/src/llm_tracekit/strands/hook_provider.py` — use core `handle_span_exception(span, error)` on `AfterModelCallEvent.exception` and `AfterToolCallEvent.exception`; handle agent-level errors in `after_invocation`
- [ ] T026 [US1] Implement metrics recording in `instrumentations/strands/src/llm_tracekit/strands/hook_provider.py` — instantiate core `Instruments` from meter; record `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` on model span end
- [ ] T027 [US1] Wire up `StrandsInstrumentor._instrument()` in `instrumentations/strands/src/llm_tracekit/strands/instrumentor.py` — create tracer and `StrandsHookProvider`; patch `Agent.__init__` via wrapt to inject hook provider; create meter and `Instruments`
- [ ] T028 [US1] Wire up `StrandsInstrumentor._uninstrument()` in `instrumentations/strands/src/llm_tracekit/strands/instrumentor.py` — remove wrapt patch; disable hook provider
- [ ] T029 [US1] Create VCR cassettes in `instrumentations/strands/tests/cassettes/` for basic agent test scenarios (single tool, multi-cycle, no tools, model error, tool error)
- [ ] T030 [US1] Run all US1 tests and verify they pass

**Checkpoint**: Basic agent tracing works end-to-end. The adapter produces a complete span hierarchy with GenAI attributes and metrics.

---

## Phase 4: User Story 2 — Content Capture (Priority: P2)

**Goal**: When content capture is enabled, model invocation spans include prompt/completion content with tool call sub-attributes in the per-index format that Coralogix's AI Center can render.

**Independent Test**: Enable content capture, invoke an agent with tools, and assert `gen_ai.prompt.{n}.*` and `gen_ai.completion.{n}.*` attributes appear on model spans, including tool call sub-attributes.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T031 [P] [US2] Test prompt/completion content capture in `instrumentations/strands/tests/test_content_capture.py` — enable content capture, invoke agent, assert `gen_ai.prompt.{n}.role`, `gen_ai.prompt.{n}.content`, `gen_ai.completion.{n}.role`, `gen_ai.completion.{n}.content` on model span
- [ ] T032 [P] [US2] Test tool call attributes on model span in `instrumentations/strands/tests/test_content_capture.py` — assert `gen_ai.prompt.{n}.tool_calls.{m}.id`, `.type`, `.function.name`, `.function.arguments`, and `gen_ai.prompt.{n}.tool_call_id` for tool result messages
- [ ] T033 [P] [US2] Test completion tool call attributes in `instrumentations/strands/tests/test_content_capture.py` — assert `gen_ai.completion.{n}.tool_calls.{m}.*` when model requests tool calls
- [ ] T034 [P] [US2] Test content capture disabled by default in `instrumentations/strands/tests/test_content_capture.py` — invoke agent without enabling capture, assert no content attributes on spans
- [ ] T035 [P] [US2] Test tool span content capture in `instrumentations/strands/tests/test_content_capture.py` — enable content capture, assert `input` and `output` attributes on tool spans

### Implementation for User Story 2

- [ ] T036 [US2] Implement model span content capture in `instrumentations/strands/src/llm_tracekit/strands/hook_provider.py` — in `after_model_call`, convert Strands messages to core `Message`/`Choice` models; call `generate_message_attributes()` and `generate_choice_attributes()` from core; set attributes on model span
- [ ] T037 [US2] Implement tool span content capture in `instrumentations/strands/src/llm_tracekit/strands/hook_provider.py` — in `after_tool_call`, if content capture enabled, set `input` (tool arguments) and `output` (tool result) and `mcp_data` (if MCP) on tool span
- [ ] T038 [US2] Create VCR cassettes in `instrumentations/strands/tests/cassettes/` for content capture scenarios (with/without tools, with content enabled/disabled)
- [ ] T039 [US2] Run all US2 tests and verify they pass

**Checkpoint**: Content capture works. Coralogix AI Center can render full conversation views including tool call/response segments.

---

## Phase 5: User Story 3 — Coralogix Integration (Priority: P3)

**Goal**: A developer can set up Strands tracing export to Coralogix with a single function call.

**Independent Test**: Call `setup_export_to_coralogix()` with test credentials, verify the tracer provider is configured with the Coralogix OTLP endpoint.

### Implementation for User Story 3

- [ ] T040 [US3] Verify `setup_export_to_coralogix` re-export works in `instrumentations/strands/src/llm_tracekit/strands/__init__.py` — this was done in T009; write a smoke test in `instrumentations/strands/tests/test_coralogix_integration.py` confirming the import path and that it configures a `TracerProvider`
- [ ] T041 [US3] Run US3 test and verify it passes

**Checkpoint**: Coralogix integration works via the re-exported helper.

---

## Phase 6: User Story 4 — Uninstrumentation (Priority: P4)

**Goal**: A developer can cleanly disable and re-enable tracing at runtime.

**Independent Test**: Instrument, run agent (assert spans), uninstrument, run agent (assert no new spans), re-instrument, run agent (assert spans resume).

### Tests for User Story 4

- [ ] T042 [US4] Test uninstrument/re-instrument lifecycle in `instrumentations/strands/tests/test_uninstrument.py` — instrument → invoke agent (assert spans) → uninstrument → invoke agent (assert no new spans) → re-instrument → invoke agent (assert spans resume)

### Implementation for User Story 4

- [ ] T043 [US4] Verify uninstrument logic in `instrumentations/strands/src/llm_tracekit/strands/instrumentor.py` — ensure `_uninstrument()` fully removes wrapt patch and disables hook provider so no spans are emitted; ensure re-instrument works cleanly
- [ ] T044 [US4] Create VCR cassettes in `instrumentations/strands/tests/cassettes/` for uninstrument test scenarios
- [ ] T045 [US4] Run US4 test and verify it passes

**Checkpoint**: Full lifecycle management works — instrument, uninstrument, re-instrument.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, concurrent execution, final validation

- [ ] T046 [P] Create `instrumentations/strands/README.md` with overview, installation, usage, semantic conventions table (matching the OpenAI adapter README format). Must include a prominent note to disable Strands' built-in telemetry (`StrandsTelemetry`) when using llm-tracekit to avoid duplicate traces
- [ ] T047 [P] Test concurrent agent executions in `instrumentations/strands/tests/test_agent_tracing.py` — run 3+ agents concurrently, assert independent traces with no context leakage (FR-009, SC-006)
- [ ] T048 Run the full test suite across all adapters to verify no regressions (SC-005)
- [ ] T049 Run quickstart.md validation — follow the quickstart steps manually and verify the output matches expectations
- [ ] T050 Code cleanup: run `ruff check` and `ruff format`, verify `pyright` passes with no errors

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3–6)**: All depend on Foundational phase completion
  - US1 (Basic Tracing) must complete before US2 (Content Capture) — US2 extends the hook provider built in US1
  - US3 (Coralogix) can start after Foundational — independent of US1/US2
  - US4 (Uninstrumentation) can start after US1 — tests the instrument/uninstrument lifecycle
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational (Phase 2) — no dependencies on other stories
- **US2 (P2)**: Depends on US1 — extends the hook provider with content capture logic
- **US3 (P3)**: Can start after Foundational (Phase 2) — independent re-export verification
- **US4 (P4)**: Depends on US1 — tests lifecycle of the instrumentor built in US1

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Hook provider logic before instrumentor wiring
- Core span logic before content capture extensions
- Implementation complete before VCR cassette creation
- Story complete before moving to next priority

### Parallel Opportunities

- T003, T004 can run in parallel (Setup)
- T006–T011 foundation tasks: T011 can run in parallel with others
- US1 test tasks (T013–T020) can all run in parallel
- US2 test tasks (T031–T035) can all run in parallel
- US3 and US4 can run in parallel with each other (after US1)
- T046, T047 can run in parallel (Polish)

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together (they will fail initially):
Task: T013 "Test basic agent span creation"
Task: T014 "Test cycle span creation"
Task: T015 "Test model invocation span"
Task: T016 "Test tool span creation"
Task: T017 "Test multi-cycle agent"
Task: T018 "Test agent with no tools"
Task: T019 "Test error handling"
Task: T020 "Test metrics emission"

# Then implement sequentially:
Task: T021 "Agent span logic"
Task: T022 "Cycle span logic"
Task: T023 "Model span logic"
Task: T024 "Tool span logic"
Task: T025 "Error handling"
Task: T026 "Metrics recording"
Task: T027 "Wire _instrument()"
Task: T028 "Wire _uninstrument()"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Basic Agent Tracing)
4. **STOP and VALIDATE**: Test US1 independently — invoke a Strands agent and verify the span hierarchy in InMemorySpanExporter
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Package ready
2. Add US1 (Basic Tracing) → Test independently → MVP
3. Add US2 (Content Capture) → Test independently → Coralogix conversation views work
4. Add US3 (Coralogix Integration) → Test independently → One-line setup works
5. Add US4 (Uninstrumentation) → Test independently → Full lifecycle management
6. Polish → README, concurrency, regression tests

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
