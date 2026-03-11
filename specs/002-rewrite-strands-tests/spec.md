# Feature Specification: Rewrite Strands Agents Tests with VCR and Real SDK

**Feature Branch**: `001-strands-agent`  
**Created**: 2026-03-10  
**Status**: Draft  
**Input**: User description: "Rewrite strands-agents tests in the same manner as other adapters (using vcr and asyncio). Look at both google-adk, openai-agents and openai as examples. They use the actual respective SDKs within the tests and record real responses using VCR. Use AWS Bedrock-based Claude Sonnet 4.6 as the underlying model."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consistent Test Pattern Across Adapters (Priority: P1)

A contributor working on the llm-tracekit project opens the strands-agents test suite and finds tests that follow the same conventions as the openai-agents and google-adk adapters. The tests use the actual Strands Agents SDK (`strands.Agent`, `strands.models.bedrock.BedrockModel`) with real HTTP interactions recorded via VCR cassettes. This consistency reduces the learning curve when switching between adapter test suites and gives confidence that the instrumentation works against real SDK behavior.

**Why this priority**: Test consistency is the primary goal of this rewrite. Without it, the strands-agents tests remain an outlier that is harder to maintain and less trustworthy.

**Independent Test**: Can be fully tested by running the rewritten test suite with VCR cassettes present and verifying all tests pass, producing the expected span hierarchy and attributes.

**Acceptance Scenarios**:

1. **Given** the rewritten test suite, **When** a contributor runs `pytest` in the strands-agents directory, **Then** all tests pass using VCR-recorded responses without requiring live AWS credentials.
2. **Given** a contributor with valid AWS credentials and VCR in record mode, **When** they run the test suite, **Then** new cassettes are recorded from actual Bedrock API calls using Claude Sonnet 4.6.
3. **Given** the strands-agents test files (`conftest.py`, `test_strands_agents.py`, `utils.py`), **When** compared to the openai-agents test files, **Then** the structure, fixture patterns, and assertion helpers follow the same conventions (VCR configuration, span exporters, instrumentor lifecycle, content capture toggling).

---

### User Story 2 - Simple Completion Tracing Verification (Priority: P1)

A contributor wants to verify that a basic Strands agent invocation (no tools) produces the correct span hierarchy and attributes. The test creates a simple agent backed by AWS Bedrock Claude Sonnet 4.6, sends a straightforward prompt, and asserts the resulting spans.

**Why this priority**: This is the most fundamental test case—if single-turn, tool-free invocation doesn't produce correct spans, nothing else matters.

**Independent Test**: Can be tested by running a single test function that invokes a Strands agent with a simple prompt and asserts agent span, cycle span, and chat span attributes.

**Acceptance Scenarios**:

1. **Given** a Strands agent with no tools and content capture enabled, **When** the agent processes "Say 'This is a test.' and nothing else.", **Then** an agent span, at least one cycle span, and exactly one chat span are emitted.
2. **Given** the emitted spans, **When** inspecting the agent span, **Then** it contains `gen_ai.system = "strands"`, `gen_ai.operation_name = "invoke_agent"`, `gen_ai.agent.name`, and `gen_ai.request.model`.
3. **Given** the emitted spans, **When** inspecting the chat span, **Then** it contains prompt messages (system + user) and completion content (assistant response) as span attributes.
4. **Given** the emitted spans, **When** inspecting span hierarchy, **Then** the cycle span is a child of the agent span, and the chat span is a child of the cycle span.

---

### User Story 3 - Tool Usage Tracing Verification (Priority: P1)

A contributor wants to verify that tool calls are correctly traced. The test creates an agent with a tool (e.g., `get_weather`), sends a prompt that triggers tool use, and asserts that tool spans are emitted with correct attributes alongside the multi-cycle chat spans.

**Why this priority**: Tool usage is a core agent capability. Verifying its tracing is essential for confidence in the instrumentation.

**Independent Test**: Can be tested by running a single test function with a tool-equipped agent and asserting tool span attributes and the chat span's tool call content.

**Acceptance Scenarios**:

1. **Given** a Strands agent with a `get_weather` tool and content capture enabled, **When** the agent processes a weather query, **Then** at least one tool span with `gen_ai.operation_name = "execute_tool"` and `name = "get_weather"` is emitted.
2. **Given** the emitted tool span, **When** inspecting its attributes, **Then** it contains `gen_ai.tool.status = "success"` and captured input/output content.
3. **Given** the emitted chat spans, **When** inspecting the first chat span's completion, **Then** it contains a tool call reference to `get_weather`.
4. **Given** the emitted chat spans, **When** inspecting the last chat span, **Then** it contains the final assistant text response.

---

### User Story 4 - Content Capture Toggle Verification (Priority: P2)

A contributor wants to verify that content capture can be toggled off. When disabled, prompt/completion content and tool input/output must not appear in span attributes, while structural attributes (model name, operation type, token counts) remain.

**Why this priority**: Content capture toggling is a privacy-critical feature that must work correctly, but it's secondary to basic tracing correctness.

**Independent Test**: Can be tested by running the agent with content capture disabled and asserting the absence of content attributes.

**Acceptance Scenarios**:

1. **Given** content capture is disabled, **When** a Strands agent processes a message, **Then** `gen_ai.prompt.*.content` and `gen_ai.completion.*.content` attributes are absent from chat spans.
2. **Given** content capture is disabled and the agent uses tools, **When** a tool is invoked, **Then** `input` and `output` attributes are absent from tool spans.
3. **Given** content capture is disabled, **When** inspecting chat span attributes, **Then** structural attributes (`gen_ai.system`, `gen_ai.operation_name`, `gen_ai.request.model`) are still present.

---

### User Story 5 - Tool Error Tracing Verification (Priority: P2)

A contributor wants to verify that tool errors are captured correctly. The test creates an agent with a tool that raises an exception and asserts that the tool span records the error status.

**Why this priority**: Error handling is important for debuggability but depends on the basic tracing infrastructure being correct first.

**Independent Test**: Can be tested by running an agent with a deliberately failing tool and asserting error status on the tool span.

**Acceptance Scenarios**:

1. **Given** a Strands agent with a tool that always raises `ValueError`, **When** the agent processes a prompt that triggers the tool, **Then** the tool span has `gen_ai.tool.status = "error"`.
2. **Given** the emitted spans, **When** the agent recovers from the tool error and provides a final response, **Then** the agent span completes successfully and includes all child spans.

---

### User Story 6 - Multi-Cycle Tracing Verification (Priority: P2)

A contributor wants to verify that multi-cycle agent executions (e.g., tool use triggering additional model calls) produce the correct span hierarchy with multiple cycle spans.

**Why this priority**: Multi-cycle is the common pattern when tools are used. It's important but covered implicitly by the tool test.

**Independent Test**: Can be tested by running an agent with a tool and asserting that multiple cycle spans appear as children of the agent span.

**Acceptance Scenarios**:

1. **Given** a Strands agent with a tool, **When** the agent processes a prompt requiring tool use, **Then** at least 2 cycle spans are emitted (one for tool call, one for final response).
2. **Given** the emitted spans, **When** inspecting the agent span, **Then** aggregated token usage (`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`) is greater than zero.

---

### User Story 7 - Uninstrumentation Verification (Priority: P3)

A contributor wants to verify that uninstrumenting stops trace emission. After calling `uninstrument()`, agent invocations must not produce agent-related spans.

**Why this priority**: Uninstrumentation is a lifecycle management feature that has lower testing priority.

**Independent Test**: Can be tested by instrumenting, running an agent, uninstrumenting, running again, and asserting no new agent spans appear.

**Acceptance Scenarios**:

1. **Given** the instrumentation is active and an agent produces spans, **When** `uninstrument()` is called and a new agent runs, **Then** no new agent spans (`invoke_agent`) are emitted.

---

### User Story 8 - Metrics Verification (Priority: P2)

A contributor wants to verify that the instrumentation emits standard metrics (operation duration, token usage) alongside traces.

**Why this priority**: Metrics complement tracing and are checked in the existing test, so they should be preserved.

**Independent Test**: Can be tested by running an agent and checking that `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` metrics are recorded.

**Acceptance Scenarios**:

1. **Given** a Strands agent with the instrumentation active, **When** the agent processes a message, **Then** the metric reader contains `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` metrics.

---

### Edge Cases

- What happens when VCR cassettes are missing and no AWS credentials are available? Tests should fail with a clear error rather than hang or produce misleading results.
- What happens when the Bedrock event-stream responses are base64-encoded in cassettes? The conftest must handle encoding/decoding correctly (existing `handle_recording_boto_response` pattern).
- What happens when the Strands SDK is not installed (Python < 3.10)? The test module should skip gracefully with an informative message.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Tests MUST use the actual Strands Agents SDK (`strands.Agent`, `strands.models.bedrock.BedrockModel`) rather than mocks.
- **FR-002**: Tests MUST use `pytest-recording` (VCR.py) to record and replay HTTP interactions with AWS Bedrock.
- **FR-003**: Tests MUST use AWS Bedrock Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-20250514-v1:0`) as the underlying model.
- **FR-004**: The `conftest.py` MUST follow the same structural pattern as the openai-agents conftest (span exporter, metric reader, tracer/meter provider fixtures, VCR configuration, instrumentor fixtures with content capture toggle).
- **FR-005**: The `conftest.py` MUST include Bedrock-specific VCR handling for event-stream responses (base64 encoding/decoding).
- **FR-006**: The `conftest.py` MUST set dummy AWS credentials when real ones are not present, to allow cassette replay without live credentials.
- **FR-007**: The `utils.py` MUST provide span filtering helpers (`get_agent_spans`, `get_cycle_spans`, `get_chat_spans`, `get_tool_spans`) and attribute assertion helpers consistent with the existing patterns.
- **FR-008**: All test cases MUST be consolidated into a single file (`test_strands_agents.py`), matching the single-file convention used by openai-agents (`test_agent_instrumentation.py`) and google-adk (`test_google_adk.py`). The old multi-file split (`test_agent_tracing.py`, `test_content_capture.py`, `test_uninstrumentation.py`) MUST be removed. Test cases covered: simple completion, tool usage, content capture disabled (no content), tool with content disabled, multi-cycle execution, tool error handling, uninstrumentation, and metrics emission.
- **FR-009**: Tests MUST be synchronous (matching Strands SDK's synchronous agent invocation API), not async.
- **FR-010**: VCR cassettes MUST filter sensitive headers (Authorization, AWS security tokens) and must store responses in a human-readable YAML format with pretty-printed JSON bodies.
- **FR-011**: The test module MUST skip gracefully when the Strands Agents SDK is not installed.
- **FR-012**: The `tests/__init__.py` MUST exist to make the test directory a proper Python package for relative imports.

### Key Entities

- **VCR Cassette**: A YAML file recording HTTP request/response pairs from AWS Bedrock. Stored in `instrumentations/strands-agents/tests/cassettes/` with filenames matching test function names.
- **Span Exporter**: In-memory OpenTelemetry span exporter used to collect and inspect spans emitted during test execution.
- **Metric Reader**: In-memory OpenTelemetry metric reader used to collect and inspect metrics emitted during test execution.
- **Instrumentor**: `StrandsInstrumentor` instance that attaches/detaches tracing hooks to the Strands SDK.

## Clarifications

### Session 2026-03-10

- Q: Should the rewrite consolidate all tests into a single file or keep the old multi-file split? → A: Single file (`test_strands_agents.py`), matching the openai-agents and google-adk adapter patterns.

## Assumptions

- The existing Strands Agents instrumentation code (`llm_tracekit.strands_agents`) is correct and functional. This spec covers only the test rewrite, not changes to the instrumentation itself.
- The VCR cassettes will be recorded once using real AWS credentials and committed to the repository. Subsequent test runs replay cassettes without network access.
- The Strands SDK's agent invocation API is synchronous (call-based, not async), matching the existing test patterns.
- The model `us.anthropic.claude-sonnet-4-20250514-v1:0` is available in the `us-east-1` AWS region.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 8 test functions pass when run with `pytest` using pre-recorded VCR cassettes, completing in under 30 seconds.
- **SC-002**: The test file structure (`conftest.py`, `test_strands_agents.py`, `utils.py`, `__init__.py`) mirrors the openai-agents adapter test layout with adapter-specific adaptations.
- **SC-003**: A contributor familiar with the openai-agents tests can understand the strands-agents tests without additional documentation.
- **SC-004**: The test suite achieves the same coverage of span hierarchy, attributes, content capture, error handling, and uninstrumentation as the existing tests, but with real SDK responses instead of mocks.
- **SC-005**: No test relies on hardcoded response content from the model—assertions check structural properties (span names, attribute keys, roles) rather than exact model output text.
