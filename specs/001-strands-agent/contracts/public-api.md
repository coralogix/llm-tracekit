# Public API Contract: llm-tracekit-strands

**Branch**: `001-strands-agent` | **Date**: 2026-03-09

## Package: `llm_tracekit.strands`

### Exports (from `__init__.py`)

```python
from llm_tracekit.strands import (
    StrandsInstrumentor,          # BaseInstrumentor subclass
    setup_export_to_coralogix,    # Re-export from core
    enable_capture_content,       # Re-export from core
    OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT,  # Re-export from core
)
```

### StrandsInstrumentor

```python
class StrandsInstrumentor(BaseInstrumentor):
    def instrumentation_dependencies(self) -> Collection[str]:
        """Returns required dependencies: ('strands-agents>=...',)"""

    def _instrument(self, **kwargs) -> None:
        """
        Activate Strands tracing.

        kwargs:
            tracer_provider: Optional TracerProvider
        """

    def _uninstrument(self, **kwargs) -> None:
        """Deactivate Strands tracing. Cleanly removes hooks."""
```

### Usage

```python
from llm_tracekit.strands import StrandsInstrumentor, setup_export_to_coralogix

# Option A: Coralogix
setup_export_to_coralogix(api_key="...", application="my-app")
StrandsInstrumentor().instrument()

# Option B: Custom tracer provider
StrandsInstrumentor().instrument(tracer_provider=my_provider)

# Content capture
StrandsInstrumentor().instrument(capture_content=True)
# or via env var: OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true

# Uninstrument
StrandsInstrumentor().uninstrument()
```

### Entry Point (auto-instrumentation)

```toml
[project.entry-points.opentelemetry_instrumentor]
strands = "llm_tracekit.strands:StrandsInstrumentor"
```

### Dependencies

```
llm-tracekit-core>=1.0.0
opentelemetry-instrumentation>=0.53b1
strands-agents>=1.0.0
```
