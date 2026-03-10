# Feature Specification: Strands Agents Instrumentation Adapter

**Feature Branch**: `001-strands-agent`
**Created**: 2026-03-09
**Status**: Draft
**Input**: User description: "Add an adapter for Strands Agents support."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Basic Agent Tracing (Priority: P1)

A developer building an AI agent with Strands Agents SDK wants to gain visibility into agent execution. They activate the instrumentation and run their agent. Each agent invocation produces traces with spans covering the agent lifecycle: the top-level agent span, individual reasoning cycles, model invocations, and tool executions. The developer can view these traces in their observability backend to understand latency, token usage, and execution flow.

**Why this priority**: Without basic tracing, the adapter delivers no value. This is the foundational capability that all other stories build upon.

**Independent Test**: Can be fully tested by instrumenting a simple Strands agent that calls a model and uses a tool, then asserting that the expected span hierarchy (agent → cycle → model invoke, tool) is produced with correct GenAI semantic attributes.

**Acceptance Scenarios**:

1. **Given** a Strands agent with one tool and the instrumentation is activated, **When** the agent processes a user message, **Then** traces are emitted containing an agent span, at least one cycle span, a model invocation span, and a tool span, each with standard GenAI semantic attributes (model name, token usage, operation type).
2. **Given** a Strands agent that requires multiple reasoning cycles, **When** the agent completes its task, **Then** each cycle is represented as a separate child span under the agent span, and all cycles are accounted for.
3. **Given** a Strands agent with no tools, **When** the agent processes a user message, **Then** traces are emitted with agent and model invocation spans but no tool spans.

---

### User Story 2 - Content Capture (Priority: P2)

A developer debugging agent behavior wants to see the actual prompts sent to the model and the completions returned. They enable content capture and can inspect the full message payloads (user prompts, system instructions, assistant responses, tool call arguments and results) within the trace spans.

**Why this priority**: Content capture is essential for debugging but secondary to the core tracing structure. It follows the existing project pattern of being opt-in.

**Independent Test**: Can be tested by enabling content capture on the instrumentor, running an agent, and asserting that prompt and completion content attributes appear on the relevant spans.

**Acceptance Scenarios**:

1. **Given** content capture is enabled, **When** a Strands agent processes a message, **Then** model invocation spans contain prompt and completion content as span attributes following GenAI semantic conventions.
2. **Given** content capture is disabled (default), **When** a Strands agent processes a message, **Then** no prompt or completion content appears in span attributes.
3. **Given** content capture is enabled and the agent uses tools, **When** a tool is invoked, **Then** tool call arguments and results are captured in the corresponding span attributes.

---

### User Story 3 - Coralogix Integration (Priority: P3)

A developer using Coralogix for observability wants a streamlined setup experience. They call the provided setup function with their Coralogix API key and the instrumentation is fully configured to export traces to Coralogix with no additional boilerplate.

**Why this priority**: Coralogix integration is a convenience layer that reuses existing core infrastructure. It adds polish but is not required for the adapter to function.

**Independent Test**: Can be tested by calling the Coralogix setup function and verifying that the trace exporter is correctly configured to the Coralogix OTLP endpoint.

**Acceptance Scenarios**:

1. **Given** a developer calls the Coralogix setup function with valid credentials, **When** a Strands agent runs, **Then** traces are exported to the specified Coralogix endpoint.
2. **Given** a developer uses manual OpenTelemetry configuration instead of the Coralogix helper, **When** a Strands agent runs, **Then** traces are exported to the manually configured backend.

---

### User Story 4 - Uninstrumentation (Priority: P4)

A developer wants to disable tracing at runtime without restarting their application. They call the uninstrument method and the adapter cleanly removes its hooks, restoring original behavior.

**Why this priority**: Clean uninstrumentation is required for lifecycle management but is a lower-priority user journey.

**Independent Test**: Can be tested by instrumenting, running an agent (asserting spans), uninstrumenting, running the agent again (asserting no new spans), then re-instrumenting and verifying spans resume.

**Acceptance Scenarios**:

1. **Given** the instrumentation is active, **When** the developer calls uninstrument, **Then** subsequent agent invocations produce no trace spans.
2. **Given** the instrumentation was uninstrumented, **When** the developer re-instruments, **Then** tracing resumes and spans are emitted again.

---

### Edge Cases

- What happens when the Strands agent encounters a model error (rate limit, auth failure) mid-execution? The span MUST record the error with appropriate status and error attributes.
- What happens when a tool raises an exception? The tool span MUST capture the exception and mark the span status as error.
- What happens when the agent runs with streaming enabled? The adapter MUST handle streaming responses without dropping span data or corrupting token counts.
- What happens when multiple Strands agents run concurrently? Each agent invocation MUST produce its own independent trace with correct parent-child span relationships.
- What happens when the Strands agent uses MCP (Model Context Protocol) tools? MCP tool invocations MUST be captured as tool spans with appropriate attributes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The adapter MUST produce a top-level agent span for each Strands agent invocation, containing the agent name and operation type.
- **FR-002**: The adapter MUST produce child spans for each reasoning cycle within an agent invocation.
- **FR-003**: The adapter MUST produce spans for model invocations with GenAI semantic attributes including model name, input token count, output token count, and finish reason.
- **FR-004**: The adapter MUST produce spans for tool executions with the tool name and type.
- **FR-005**: The adapter MUST support opt-in content capture for prompts, completions, and tool call payloads, controlled by a flag and an environment variable.
- **FR-006**: The adapter MUST follow the `BaseInstrumentor` pattern with `instrument()` and `uninstrument()` methods that cleanly attach and detach tracing hooks.
- **FR-007**: The adapter MUST re-export the Coralogix setup helper from `llm-tracekit-core` for streamlined Coralogix integration.
- **FR-008**: The adapter MUST handle errors in agent execution (model failures, tool exceptions) by recording error status and details on the relevant span without crashing the host application.
- **FR-009**: The adapter MUST support concurrent agent executions with correct trace context propagation.
- **FR-010**: The adapter MUST be installable as a standalone package (`llm-tracekit-strands-agents`) and optionally through the `llm-tracekit` meta-package.
- **FR-011**: The adapter MUST register an OpenTelemetry auto-instrumentation entry point so it can be activated without code changes when using the OpenTelemetry SDK's auto-instrumentation.

### Key Entities

- **Agent Span**: Represents the full lifecycle of a single Strands agent invocation. Attributes include agent name and operation type. Consistent with agent spans in OpenAI Agents (`openai.agent`) and Bedrock (`bedrock.invoke_agent`).
- **Cycle Span**: Represents one reasoning cycle (prompt → model → optional tool calls → response) within an agent invocation. Child of the agent span. This is a Strands-specific span with no equivalent in other adapters, similar to how LangGraph has framework-specific `LangGraph Node {name}` spans and OpenAI Agents has `Guardrail` and `Handoff` spans.
- **Model Invocation Span**: Represents a single call to the underlying LLM. Contains model name, token usage, finish reason. Child of a cycle span. Follows the same `chat {model}` pattern used by OpenAI, Gemini, Bedrock, LangChain, and LiteLLM adapters.
- **Tool Span**: Represents a single tool execution. Contains tool name and type. Child of a cycle span. Consistent with `Tool - {name}` spans in the OpenAI Agents adapter.

## Assumptions

- Strands Agents SDK provides sufficient instrumentation hooks (callbacks, processors, or patchable internals) to capture the required span hierarchy without invasive monkey-patching.
- The Strands Agents SDK already uses OpenTelemetry internally for some tracing; the adapter enriches or replaces these spans with GenAI semantic attributes rather than duplicating them.
- The adapter focuses on agent-level tracing. If the underlying model provider (e.g., Bedrock) is independently instrumented via its own `llm-tracekit` adapter, those spans are complementary, not conflicting.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can activate the adapter with a single function call and see Strands agent traces in their observability backend within 5 minutes of setup.
- **SC-002**: 100% of agent invocations produce a complete span hierarchy (agent → cycle → model/tool) with no missing or orphaned spans.
- **SC-003**: Token usage reported in spans matches the values returned by the underlying model provider with 100% accuracy.
- **SC-004**: The adapter introduces less than 5% overhead to agent execution latency.
- **SC-005**: All existing instrumentations continue to pass their test suites after the new adapter is added (no regressions).
- **SC-006**: The adapter handles at least 3 concurrent agent executions without trace corruption or context leakage.

