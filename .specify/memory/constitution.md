<!--
Sync Impact Report
- Version change: 1.0.0 → 2.0.0
- Modified principles:
  - I. OpenTelemetry Standards (unchanged)
  - II. Workspace Modularity (expanded with cld-spec architecture patterns)
  - III. Instrumentation Consistency (expanded with schema-first and layer separation)
  - IV. Test-Driven with VCR (expanded with cld-spec testing standards)
  - V. Type Safety & Linting (expanded with development conventions)
  - VI. Semantic Versioning (expanded with migration and compatibility)
- Added sections: Security, Operations & Observability, Performance, AI Agent Behavior
- Removed sections: None
- Templates requiring updates: ✅ No updates needed (templates are generic)
- Follow-up TODOs: None
-->

# LLM Tracekit Constitution

## Core Principles

### I. OpenTelemetry Standards

All instrumentation code MUST conform to OpenTelemetry semantic conventions for Generative AI. Spans, metrics, and attributes MUST use standard GenAI attribute names (`gen_ai.*`). Custom attributes MUST be namespaced under project-specific prefixes and documented. The `opentelemetry-semantic-conventions` package is the source of truth for attribute naming. All public APIs MUST be documented with clear contracts and versioned for breaking changes.

### II. Workspace Modularity

The project is a uv workspace with independent packages: `llm-tracekit` (meta), `llm-tracekit-core`, and per-provider/framework instrumentation packages. Each package MUST be independently installable, testable, and publishable. Cross-package dependencies MUST flow through `llm-tracekit-core`; instrumentation packages MUST NOT depend on each other. New providers/frameworks MUST follow the established package layout: `instrumentations/<name>/src/llm_tracekit/<name>/`, `instrumentations/<name>/tests/`, `instrumentations/<name>/pyproject.toml`.

**Architecture rules** (from cld-spec shared/architecture):
- Simplicity first: start simple, add abstraction only when it reduces duplication or clarifies boundaries.
- No duplication: shared logic belongs in `core` with clear ownership.
- Clear boundaries: feature ownership MUST be obvious; avoid cross-domain imports between instrumentation packages.
- Safe change: incremental refactors, preserve behavior, version breaking changes with migration plans.
- Decision framework: (1) Does it exist in core? Reuse. (2) Can we extend core? Extend minimally. (3) Must create new package? Document ownership.

### III. Instrumentation Consistency

Every instrumentor MUST extend `BaseInstrumentor` and implement `_instrument()` / `_uninstrument()`. Patching MUST use `wrapt.wrap_function_wrapper`. Each instrumentation package MUST expose:
- `package.py` with `_instruments` for dependency detection
- `instrumentor.py` with the public instrumentor class
- `patch.py` with wrapper functions

Internal modules MUST use leading underscores. Span creation, metric recording, and error handling MUST follow the patterns established in `core`.

**Layer separation** (from cld-spec backend/conventions):
- API layer: request handling, validation (instrumentor entry points)
- Service layer: business logic (span building, metric recording)
- No business logic in the API/patch layer; delegate to core utilities.
- Dependency direction: inner layers (core) MUST NOT depend on outer layers (instrumentations).
- Error handling: return/propagate errors explicitly; wrap with context; do not expose internal details in span attributes.

### IV. Test-Driven with VCR

Tests MUST use `pytest` with `pytest-vcr` for HTTP recording/replay and `assertpy` for assertions. Async tests MUST use `pytest-asyncio`. VCR cassettes MUST be stored in `tests/cassettes/*.yaml`. Each package MUST have its own `conftest.py` with in-memory exporters (`InMemorySpanExporter`, `InMemoryMetricReader`).

**Testing standards** (from cld-spec shared/testing, backend/testing):
- Test behavior, not implementation. Each test MUST have a clear purpose.
- Avoid redundant coverage across layers. Use realistic test data.
- Test pyramid: unit tests for pure logic, integration tests for component interactions, E2E tests for critical user journeys.
- Critical paths MUST have coverage. New features require tests. Bug fixes require regression tests.
- Arrange–Act–Assert pattern for unit tests; mocked dependencies, no I/O.
- New instrumentations MUST include tests covering both sync and async code paths.

### V. Type Safety & Linting

All source code MUST pass `ruff check` and `ruff format`. Type hints MUST be used throughout source files. `mypy` MUST pass with `ignore_missing_imports = true` and `namespace_packages = true`. Test files are excluded from mypy checks. Pre-commit hooks MUST enforce these standards before commits reach CI.

**Development conventions** (from cld-spec shared/development, backend/conventions):
- Naming: descriptive, self-documenting; follow Python conventions (snake_case functions/variables, PascalCase classes, UPPER_SNAKE_CASE constants).
- Naming patterns: verb+noun for functions (`create_span`, `build_attributes`); `is_`/`has_`/`can_`/`should_` for booleans.
- Files: one primary class/export per module when practical; focused files with related functionality grouped.
- Documentation: document public APIs, complex business logic, architectural decisions, and configuration options. Update docs when APIs, architecture, or behavior change. Do not document obvious behavior.

### VI. Semantic Versioning & Compatibility

All packages follow semantic versioning. Breaking changes to public APIs require a MAJOR bump. New instrumentation support or features require a MINOR bump. Bug fixes and internal refactors require a PATCH bump. The meta-package `llm-tracekit` version is independent of individual package versions.

**Compatibility rules** (from cld-spec shared/integration):
- Maintain backwards compatibility within a major version.
- Version breaking changes with migration plans.
- Document all public APIs and integration points.
- Define data ownership at package boundaries.
- Validate at integration points.

## Technology Stack

- **Language**: Python 3.10–3.13
- **Package Manager**: uv (workspace mode)
- **Build System**: Hatchling
- **Core Framework**: OpenTelemetry API/SDK
- **Patching**: wrapt
- **Linting/Formatting**: Ruff
- **Type Checking**: Mypy
- **Testing**: pytest, pytest-asyncio, pytest-vcr, assertpy
- **CI/CD**: GitHub Actions (test, lint, publish workflows)
- **Publishing**: PyPI via trusted publishing
- **License**: Apache 2.0

## Security

(From cld-spec shared/security)

- No secrets in code or commits. Sensitive data MUST NOT appear in logs or span attributes.
- Validate all inputs; sanitize all outputs.
- Pin dependency versions in `uv.lock`; review advisories; update vulnerable dependencies promptly.
- Content capture (recording LLM request/response bodies) MUST be opt-in, never enabled by default.
- Follow data privacy rules; maintain audit trails for sensitive operations.

## Operations & Observability

(From cld-spec shared/operations)

- All changes MUST go through CI/CD (GitHub Actions).
- Maintain rollback capability via semantic versioning and PyPI.
- Log actionable information; use structured logging where applicable.
- The library itself provides observability (spans, metrics) to consuming applications — dogfood these patterns in development and testing.
- Document deployment procedures for publishing new releases.

## Performance

(From cld-spec shared/performance)

- Instrumentation MUST NOT significantly impact the performance of instrumented applications.
- Measure before optimizing; profile critical paths first.
- Avoid premature optimization; focus on hot paths (span creation, attribute building, metric recording).
- Document any known performance constraints or overhead characteristics.

## AI Agent Behavior

(From cld-spec shared/behavior, backend/behavior)

When AI agents work on this codebase, they MUST follow these guidelines:

- **Context-first**: Read repository context (this constitution, architecture docs, existing patterns) before making changes.
- **Explicit**: Provide actionable guidance with specific file/function references.
- **Consistent**: Enforce repository standards defined in this constitution.
- **Incremental**: Prefer safe, reviewable changes over large rewrites.

**Workflow**: Understand → Explore → Design (reuse first) → Plan → Execute (with tests) → Verify (update docs).

**Non-negotiables**:
- No dead code, hidden coupling, or skipping critical tests.
- No undocumented architectural decisions.
- No breaking changes without a migration plan.
- No secrets in code; maintain permission checks; validate/sanitize inputs.

## Development Workflow

- All changes MUST be submitted via pull requests.
- CI runs `ruff check`, `mypy`, and `pytest` per package on every PR.
- The `dorny/paths-filter` action detects changed packages; core changes trigger tests for all downstream packages.
- Source files MUST include Apache 2.0 license headers.
- Commits SHOULD follow conventional commit format. Atomic commits; reference issues/tickets.
- Publishing to PyPI is triggered by GitHub releases.
- Use feature flags for risky changes when applicable.

## Governance

- This constitution supersedes ad-hoc conventions and governs all development within the repository.
- Amendments require a pull request with clear rationale and MUST update the version line below.
- All PRs MUST be reviewed for compliance with these principles before merging.
- Complexity beyond these standards MUST be justified in the PR description.
- Architectural decisions MUST be documented (ADR or PR description with context, decision, consequences, and trade-offs).

**Version**: 2.0.0 | **Ratified**: 2026-03-09 | **Last Amended**: 2026-03-09
