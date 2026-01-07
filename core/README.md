# LLM Tracekit Core

Core utilities for LLM Tracekit instrumentations and Coralogix integration.

## Installation

```bash
pip install llm-tracekit-core
```


## Usage

### Setting up Coralogix Export

Use `setup_export_to_coralogix` to configure tracing and export spans to Coralogix:

```python
from llm_tracekit.core import setup_export_to_coralogix

setup_export_to_coralogix(
    service_name="ai-service",
    application_name="ai-application",
    subsystem_name="ai-subsystem",
    capture_content=True,
)
```

#### Environment Variables

The exporter reads connection details from environment variables:

```bash
export CX_TOKEN="your-coralogix-api-key"
export CX_ENDPOINT="https://your-domain.coralogix.com"
```

### Manual Tracing Setup

Alternatively, set up tracing manually using OpenTelemetry:

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

tracer_provider = TracerProvider(
    resource=Resource.create({SERVICE_NAME: "ai-service"}),
)
exporter = OTLPSpanExporter()
span_processor = SimpleSpanProcessor(exporter)
tracer_provider.add_span_processor(span_processor)
trace.set_tracer_provider(tracer_provider)
```

### Enabling Message Content Capture

Message content (prompts, completions, function arguments, return values) is **not captured by default**.

To enable capture:
- Pass `capture_content=True` when calling `setup_export_to_coralogix`
- Or set the environment variable `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`

> **Note:** Most Coralogix AI evaluations require message content, so enabling capture is highly recommended.

## API Reference

### `setup_export_to_coralogix`

```python
def setup_export_to_coralogix(
    service_name: str,
    application_name: str,
    subsystem_name: str,
    capture_content: bool = False,
) -> None
```

Configures OpenTelemetry to export spans to Coralogix.

**Parameters:**
- `service_name`: Name of your service
- `application_name`: Coralogix application name
- `subsystem_name`: Coralogix subsystem name
- `capture_content`: Whether to capture message content in spans

## License

Apache License 2.0

