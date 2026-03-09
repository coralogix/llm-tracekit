# Design principles

## Strategies

### Non-invasive instrumentation

Instrumentation uses `wrapt.wrap_function_wrapper` to wrap target methods. Application code is unchanged; users add a few lines to enable tracing. Patches are applied at import/runtime, not via code generation.

### Content capture opt-in

Message content (prompts, responses) is sensitive. Capture is controlled by:

- `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` environment variable
- `capture_content` in `setup_export_to_coralogix()`

When disabled, spans include model, tokens, latency, and metadata but not message bodies.

### Idempotent instrumentation

`instrument()` can be called multiple times; OpenTelemetry instrumentors typically guard against double-patching. `uninstrument()` cleanly removes patches via `opentelemetry.instrumentation.utils.unwrap`.

### Span exception handling

`handle_span_exception` in core records error attributes on the span and re-raises the original exception. The application sees the same error; observability is preserved without swallowing failures.

### Attribute filtering

`remove_attributes_with_null_values` and `attribute_generator` ensure only non-null attributes are set on spans, keeping trace payloads lean and compliant with semantic conventions.

## Invariants

1. **OpenTelemetry semantic conventions** — Spans and metrics follow `opentelemetry.semconv` (e.g. `gen_ai_attributes`, `gen_ai_metrics`).
2. **Provider-agnostic core** — Core span builders and metrics are shared; each instrumentation maps provider-specific responses to common attribute shapes.
3. **Internal modules** — Core internals use leading underscores (`_span_builder`, `_metrics`, `_config`); public API is via `llm_tracekit.core` exports.
4. **Entry points** — Instrumentations register `opentelemetry_instrumentor` entry points for auto-instrumentation tooling.

## Versioning

- **Semantic versioning** — Packages follow semver (e.g. `2.1.2`).
- **Independent package versions** — Each instrumentation can be versioned independently; core is a shared dependency.
- **Python support** — Python 3.10–3.13 (see `requires-python` in `pyproject.toml`).

## Related documentation

- [Overview](overview.md) — Mental model, workflows, quick start
- [Architecture](architecture.md) — Components, data flow, dependencies
- [Testing strategy](testing-strategy.md) — Frameworks, coverage, definition of done
