from functools import wraps
from typing import Callable

from opentelemetry.trace import Span, SpanKind, Tracer
from llm_tracekit.instruments import Instruments


def invoke_model_wrapper(original_function: Callable, tracer: Tracer, instruments: Instruments, capture_content: bool):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        # TODO: instrumentation
        return original_function(*args, **kwargs)


def converse_wrapper(original_function: Callable, tracer: Tracer, instruments: Instruments, capture_content: bool):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        # TODO: instrumentation
        return original_function(*args, **kwargs)


def converse_stream_wrapper(original_function: Callable, tracer: Tracer, instruments: Instruments, capture_content: bool):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        # TODO: instrumentation
        return original_function(*args, **kwargs)


def invoke_agent_wrapper(original_function: Callable, tracer: Tracer, instruments: Instruments, capture_content: bool):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        # TODO: instrumentation
        return original_function(*args, **kwargs)


def create_client_wrapper(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    def traced_method(wrapped, instance, args, kwargs):
        service_name = kwargs.get("service_name")
        # TODO: error handling
        if service_name == "bedrock-runtime":
            client = wrapped(*args, **kwargs)
            client.invoke_model = invoke_model_wrapper(
                original_function=client.invoke_model,
                tracer=tracer,
                instruments=instruments,
                capture_content=capture_content
            )
            client.converse = converse_wrapper(
                original_function=client.converse,
                tracer=tracer,
                instruments=instruments,
                capture_content=capture_content
            )
            client.converse_stream = converse_stream_wrapper(
                original_function=client.converse_stream,
                tracer=tracer,
                instruments=instruments,
                capture_content=capture_content
            )
        elif service_name == "bedrock-agent-runtime":
            client = wrapped(*args, **kwargs)
            client.invoke_agent = invoke_agent_wrapper(
                original_function=client.invoke_agent,
                tracer=tracer,
                instruments=instruments,
                capture_content=capture_content
            )

    return traced_method
