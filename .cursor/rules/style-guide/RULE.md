---
globs: *.py
alwaysApply: false
description: "Python style guide for llm-tracekit instrumentation library"
---
# Style Guide

This document defines the Python style guide for the llm-tracekit project - an OpenTelemetry instrumentation library for LLM/GenAI applications.

## Table of Contents

1. [Overview](#overview)
2. [Python Style Conventions](#python-style-conventions)
3. [Instrumentation Patterns](#instrumentation-patterns)
4. [Error Handling](#error-handling)
5. [Testing](#testing)
6. [Code Organization](#code-organization)

## Overview

### Core Principles

- **Type Safety**: Use type hints throughout (Python 3.10+)
- **Fail Silently**: Instrumentation should never break the user's application
- **Follow Semantic Conventions**: Use OpenTelemetry GenAI semantic conventions

### Technology Stack

- **Python**: 3.10+ (using `|` union syntax, PEP 604)
- **Type Checking**: `mypy`
- **Linting**: `ruff`
- **Package Manager**: `uv`

## Python Style Conventions

### Type Hints

Use Python 3.10+ type hints throughout. Prefer `|` union syntax over `Union`.

```python
# ✅ Good
def process_response(response: LlmResponse | None) -> dict[str, Any]:
    ...

# ❌ Bad
from typing import Union
def process_response(response: Union[LlmResponse, None]) -> Dict[str, Any]:
    ...
```

**Required Type Hints:**
- All function parameters
- All return types (except when function returns nothing - no need for `-> None`)
- Class attributes
- Module-level variables (when not obvious)

### Naming Conventions

- **Functions/Methods**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private methods/functions**: `_leading_underscore`
- **Type aliases**: `PascalCase`

```python
# ✅ Good
class GoogleADKInstrumentor:
    def _process_request(self, llm_request) -> dict[str, Any]:
        ...

MAX_RETRIES = 3
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
```

### Early Returns

Use early returns for guard clauses to reduce nesting:

```python
# ✅ Good - early return for guard clause
def on_end(self, span: ReadableSpan) -> None:
    if span.name != "call_llm":
        return
    
    attributes = span.attributes
    if attributes is None:
        return
    
    # Continue with main logic
    ...
```

### Docstrings

Use docstrings for public functions, classes, and complex logic:

```python
# ✅ Good
def create_wrapped_trace_call_llm(original_func, capture_content: bool):
    """Create a wrapped version of trace_call_llm that adds semantic convention attributes.
    
    Args:
        original_func: The original trace_call_llm function to wrap
        capture_content: Whether to capture message content
    
    Returns:
        Wrapped function that adds semantic attributes to the current span
    """
    ...
```

## Instrumentation Patterns

### BaseInstrumentor Pattern

All instrumentors should extend `BaseInstrumentor`:

```python
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor

class MyLibraryInstrumentor(BaseInstrumentor):
    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments  # From package.py
    
    def _instrument(self, **kwargs):
        # Apply patches/wrappers
        ...
    
    def _uninstrument(self, **kwargs):
        # Remove patches/wrappers
        ...
```

### Patching Libraries That Write Spans

When a library already writes OpenTelemetry spans, wrap its tracing function:

```python
def create_wrapped_trace_call_llm(original_func, capture_content: bool):
    def wrapped_trace_call_llm(invocation_context, event_id, llm_request, llm_response):
        # Call original first
        original_func(invocation_context, event_id, llm_request, llm_response)
        
        # Add our attributes to the current span
        span = trace.get_current_span()
        if span is None or not span.is_recording():
            return
        
        try:
            attributes = _build_semantic_attributes(llm_request, llm_response, capture_content)
            span.set_attributes(attributes)
        except Exception:
            pass  # Never break the user's application
    
    return wrapped_trace_call_llm
```

### Using span_builder

Use the shared `span_builder` module for generating semantic convention attributes:

```python
from llm_tracekit.span_builder import (
    Choice,
    Message,
    ToolCall,
    generate_choice_attributes,
    generate_message_attributes,
    generate_tools_attributes,
)

# Build Message objects
messages = [
    Message(role="system", content="You are helpful"),
    Message(role="user", content="Hello"),
]
attrs = generate_message_attributes(messages=messages, capture_content=True)
```

## Error Handling

### Instrumentation Should Never Break User Code

```python
# ✅ Good - silently ignore errors
try:
    attributes = _build_semantic_attributes(request, response, capture_content)
    span.set_attributes(attributes)
except Exception:
    pass  # Silently ignore errors to not break the application

# ❌ Bad - can break user's application
attributes = _build_semantic_attributes(request, response, capture_content)
span.set_attributes(attributes)  # May raise and break user code
```

### Use Specific Exceptions for Internal Logic

```python
# ✅ Good - specific exception for expected cases
try:
    llm_request = json.loads(llm_request_json)
except json.JSONDecodeError:
    return {}  # Return empty if can't parse

# ❌ Bad - bare exception hides bugs during development
except Exception:
    return {}
```

## Testing

### Test Structure

Tests should be placed in `tests/<library_name>/` with this structure:
- `__init__.py` - Package marker
- `conftest.py` - Fixtures for instrumentor setup, VCR config
- `test_*.py` - Test files
- `cassettes/` - VCR recordings of API calls
- `utils.py` - Helper functions for assertions

### Key Testing Patterns

```python
@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_my_library_completion(span_exporter, instrument):
    # Arrange
    agent = create_agent(...)
    
    # Act
    await agent.run(...)
    
    # Assert
    spans = span_exporter.get_finished_spans()
    call_llm_spans = [s for s in spans if s.name == "call_llm"]
    assert len(call_llm_spans) == 1
    
    span = call_llm_spans[0]
    assert span.attributes.get("gen_ai.prompt.0.role") == "system"
    assert span.attributes.get("gen_ai.prompt.1.role") == "user"
```

### Fixture Pattern for Libraries with Module-Level Tracers

Some libraries (like Google ADK) create tracers at module import time. Set up the tracer provider BEFORE importing the library:

```python
# conftest.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

# Set up BEFORE any library imports
_span_exporter = InMemorySpanExporter()
_tracer_provider = TracerProvider()
_tracer_provider.add_span_processor(SimpleSpanProcessor(_span_exporter))
trace.set_tracer_provider(_tracer_provider)

@pytest.fixture(scope="function")
def span_exporter():
    _span_exporter.clear()
    return _span_exporter
```

## Code Organization

### Module Structure for Instrumentations

```
src/llm_tracekit/<library>/
├── __init__.py          # Export instrumentor
├── instrumentor.py      # Main instrumentor class
├── package.py           # _instruments tuple
├── patch.py             # Patching functions (if library writes spans)
└── utils.py             # Helper functions (optional)
```

### Keep Modules Focused

- Each file should have a single responsibility
- Extract helpers into separate modules when they grow
- Use private functions (`_leading_underscore`) for internal helpers

## Summary

1. **Use type hints** throughout (Python 3.10+ syntax)
2. **Never break user code** - wrap all instrumentation in try/except
3. **Follow semantic conventions** - use `span_builder` module
4. **Patch, don't process** - for libraries that write spans, wrap their functions
5. **Write tests** with VCR cassettes for reproducibility
