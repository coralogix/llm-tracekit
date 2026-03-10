# Quickstart: Strands Agent Instrumentation

**Branch**: `001-strands-agent` | **Date**: 2026-03-09

## Install

```bash
pip install llm-tracekit-strands
```

## Disable Strands Built-in Telemetry

The Strands SDK includes its own OpenTelemetry tracing (`StrandsTelemetry`). When using llm-tracekit, you should **not** initialize Strands' built-in telemetry to avoid duplicate traces. Simply skip any calls to `StrandsTelemetry.init()` or `StrandsTelemetry.setup()` — llm-tracekit handles all tracing setup.

## Basic Usage

```python
from strands import Agent
from strands.models.bedrock import BedrockModel
from llm_tracekit.strands import StrandsInstrumentor, setup_export_to_coralogix

# 1. Set up tracing export (replaces StrandsTelemetry — do NOT use both)
setup_export_to_coralogix(api_key="your-api-key", application="my-agent-app")

# 2. Activate instrumentation
StrandsInstrumentor().instrument()

# 3. Use Strands as normal — traces are emitted automatically
model = BedrockModel(model_id="anthropic.claude-sonnet-4-20250514")
agent = Agent(model=model)
response = agent("What is the weather in Paris?")
```

## Enable Content Capture

```python
import os
os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

StrandsInstrumentor().instrument()
```

## Verify

Run the agent and check your observability backend for spans:
- `invoke_agent {agent_name}` — agent invocation (e.g. `invoke_agent WeatherAgent`)
- `cycle {cycle_id}` — each reasoning cycle
- `chat {model}` — LLM calls (e.g. `chat anthropic.claude-sonnet-4-20250514`)
- `execute_tool {tool_name}` — tool executions (e.g. `execute_tool get_weather`)

## Disable

```python
StrandsInstrumentor().uninstrument()
```
