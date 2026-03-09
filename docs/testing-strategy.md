# Testing strategy

## Frameworks & tools

| Tool | Purpose |
|------|---------|
| **pytest** | Test runner |
| **pytest-asyncio** | Async test support |
| **pytest-vcr** | HTTP mocking via VCR cassettes (record/replay) |
| **assertpy** | Fluent assertions |
| **respx** | HTTP mocking for `httpx` (used in some tests) |
| **InMemorySpanExporter** | Capture spans for assertions |
| **InMemoryMetricReader** | Capture metrics for assertions |

## Test structure

```
<package>/
├── tests/
│   ├── conftest.py      # Fixtures: span_exporter, metric_reader, tracer_provider, meter_provider, instrumentor
│   ├── utils.py         # Shared assertions (assert_completion_attributes, assert_messages_in_span, etc.)
│   ├── test_*.py        # Test modules
│   └── cassettes/       # VCR-recorded HTTP responses (optional)
```

## Coverage expectations

- **Per-package** — Each instrumentation and core has its own `tests/` directory.
- **CI** — `test.yml` runs `uv run --group=dev --locked pytest` per package.
- **Path filtering** — `dorny/paths-filter` runs tests only for changed packages (plus core when core changes).
- **Python versions** — Tests run on Python 3.10, 3.11, 3.12, 3.13 in CI.

## Test patterns

| Pattern | Description |
|---------|-------------|
| **Instrumentor fixtures** | `instrument_with_content`, `instrument_no_content` (or equivalent) set up tracer/meter providers and instrument/uninstrument around each test. |
| **VCR cassettes** | `@pytest.mark.vcr()` records HTTP interactions; cassettes are replayed to avoid real API calls. Sensitive headers are filtered via `vcr_config`. |
| **Span assertions** | Tests use `span_exporter.get_finished_spans()` and assert on attributes (model, tokens, messages, choices) via shared utils. |
| **Metric assertions** | Tests use `metric_reader.get_metrics_data()` (or equivalent) to inspect recorded metrics. |

## Definition of done

A change is acceptable when:

1. **Tests pass** — `uv run pytest` succeeds for all affected packages.
2. **Lint passes** — `ruff check` and `mypy` pass (see `lint.yml`).
3. **No new regressions** — Existing VCR cassettes are not invalidated unless the change intentionally alters behavior.
4. **Sensitive data scrubbed** — VCR config filters authorization, API keys, and organization headers.

## Related documentation

- [Overview](overview.md) — Mental model, workflows, quick start
- [Architecture](architecture.md) — Components, data flow, dependencies
- [Design principles](design-principles.md) — Strategies, invariants, versioning
