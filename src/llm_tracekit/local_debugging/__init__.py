from typing import Any
import os

from llm_tracekit.local_debugging.local_span_processor import LocalSpanProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry import trace

def is_local_debugging_enabled() -> bool:
    return 'LOCAL_DEBUGGING' in os.environ


def add_local_debugging(tracer_provider: Any | None):
    traces_directory = os.environ.get('LOCAL_DEBUGGING_TRACES_DIRECTORY')
    local_span_processor = LocalSpanProcessor(traces_directory)

    if tracer_provider is None:
        # No traces provider defined, create a new provider
        tracer_provider = TracerProvider()
        trace.set_tracer_provider(tracer_provider)        
    
    tracer_provider.add_span_processor(local_span_processor)
