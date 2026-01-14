# LLM TraceKit - Google ADK Instrumentation

OpenTelemetry instrumentation for [Google ADK (Agent Development Kit)](https://github.com/google/adk-python).

## Installation

```bash
pip install llm-tracekit-google-adk
```

## Usage

```python
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from llm_tracekit.google_adk import GoogleADKInstrumentor

# Enable instrumentation
GoogleADKInstrumentor().instrument()

# Create and run your agent
agent = Agent(
    name="MyAgent",
    model="gemini-2.0-flash",
    instruction="You are a helpful assistant.",
)

session_service = InMemorySessionService()
runner = Runner(
    agent=agent,
    app_name="my_app",
    session_service=session_service,
)

# All LLM calls will now be traced with OpenTelemetry spans
```

## Features

- Automatic tracing of LLM calls in Google ADK agents
- Captures prompt messages with conversation history
- Captures completion responses
- Captures tool calls and tool results
- Follows OpenTelemetry GenAI semantic conventions

## Captured Attributes

The instrumentation adds the following semantic convention attributes to spans:

- `gen_ai.prompt.<n>.role` - Role of each message (system, user, assistant, tool)
- `gen_ai.prompt.<n>.content` - Content of each message (when content capture is enabled)
- `gen_ai.completion.0.role` - Role of the response
- `gen_ai.completion.0.content` - Response content (when content capture is enabled)
- `gen_ai.completion.0.finish_reason` - Why generation stopped
- `gen_ai.request.tools.<n>.*` - Tool definitions
- Tool call attributes for function calls

## Content Capture

By default, message content is not captured. To enable content capture:

```bash
export OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true
```

## License

Apache 2.0
