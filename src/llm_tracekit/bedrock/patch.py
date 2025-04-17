import json
from functools import wraps
from typing import Callable

from opentelemetry.trace import Span, SpanKind, Tracer
from llm_tracekit.instruments import Instruments
# TODO: importing botocore at module-scope will not work if it's not installed
from botocore.response import StreamingBody
from llm_tracekit.span_builder import generate_base_attributes, generate_request_attributes, generate_response_attributes, Message, generate_message_attributes
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from llm_tracekit.bedrock.utils import parse_converse_message


def invoke_model_wrapper(original_function: Callable, tracer: Tracer, instruments: Instruments, capture_content: bool):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        span_attributes = {}

        span_name="TODO"
        with tracer.start_as_current_span(
            name=span_name,
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ):
            model_id = kwargs.get("modelId")
            body = kwargs.get("body")
            if body is not None:
                try:
                    # TODO: consider orjson
                    parsed_body = json.loads(body)
                    # TODO: handle parsed body based on model type
                except json.JSONDecodeError:
                    # TODO:
                    pass

            
            invoke_model_result = original_function(*args, **kwargs)
            if invoke_model_result["ResponseMetadata"]["HTTPStatusCode"] == 200:
                # TODO: 
                # The response body is a stream, and reading the stream consumes it, so we have to recreate
                # it to keep the original response usable
                response_body = invoke_model_result["body"].read()
                invoke_model_result["body"] = StreamingBody(response_body, len(response_body))
                try:
                    parsed_response_body = json.loads(response_body)
                except json.JSONDecodeError:
                    # TODO:
                    pass

                # TODO: handle parsed response based on model type

        return invoke_model_result
    
    return wrapper


def converse_wrapper(original_function: Callable, tracer: Tracer, instruments: Instruments, capture_content: bool):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        inference_config = kwargs.get("inferenceConfig", {})
        messages = []
        for system_message in kwargs.get("system", []):
            messages.append(Message(role="system", content=system_message.get("text")))

        for message in kwargs.get("messages", []):
            messages.append(parse_converse_message(role=message.get("role"), content_parts=message.get("content")))

        span_attributes = {
            **generate_base_attributes(system=GenAIAttributes.GenAiSystemValues.AWS_BEDROCK),
            **generate_request_attributes(
                model=kwargs.get("modelId"),
                temperature=inference_config.get("temperature"),
                top_p=inference_config.get("topP"),
                max_tokens=inference_config.get("maxTokens"),
            ),
            **generate_message_attributes(messages=messages, capture_content=capture_content),
        }
        with tracer.start_as_current_span(
            name="bedrock.converse",
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            response = original_function(*args, **kwargs)

            finish_reasons = []
            if "stopReason" in response:
                finish_reasons = [response["stopReason"]]
            
            usage_data = response.get("usage", {})

            response_attributes = generate_response_attributes(
                model=kwargs.get("modelId"),
                finish_reasons=finish_reasons,
                usage_input_tokens=usage_data.get("inputTokens"),
                usage_output_tokens=usage_data.get("outputTokens")
            )
            span.set_attributes(response_attributes)

            # TODO: handle choices
            # TODO: handle errors
            # TODO: record metrics
    
    return wrapper


def converse_stream_wrapper(original_function: Callable, tracer: Tracer, instruments: Instruments, capture_content: bool):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        # TODO: instrumentation
        return original_function(*args, **kwargs)
    
    return wrapper


def invoke_agent_wrapper(original_function: Callable, tracer: Tracer, instruments: Instruments, capture_content: bool):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        # TODO: instrumentation
        return original_function(*args, **kwargs)
    
    return wrapper


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
