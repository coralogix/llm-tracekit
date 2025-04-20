import json
from functools import partial, wraps
from io import BytesIO
from timeit import default_timer
from typing import Any, Callable, Dict, Optional

# TODO: importing botocore at module-scope will not work if it's not installed
from botocore.eventstream import EventStream
from botocore.response import StreamingBody
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.trace import Span, SpanKind, Tracer

from llm_tracekit.bedrock.converse import (
    ConverseStreamWrapper,
    generate_attributes_from_converse_input,
    record_converse_result_attributes,
)
from llm_tracekit.bedrock.utils import parse_converse_message, record_metrics
from llm_tracekit.instrumentation_utils import handle_span_exception
from llm_tracekit.instruments import Instruments
from llm_tracekit.span_builder import (
    Choice,
    Message,
    generate_base_attributes,
    generate_choice_attributes,
    generate_message_attributes,
    generate_request_attributes,
    generate_response_attributes,
)


def _generate_attributes_from_invoke_input(
    model_id: str, body: Dict[str, Any], capture_content: bool
) -> Dict[str, Any]:
    return {
        **generate_base_attributes(
            system=GenAIAttributes.GenAiSystemValues.AWS_BEDROCK
        ),
        **generate_request_attributes(
            model=model_id,
            temperature=inference_config.get("temperature"),
            top_p=inference_config.get("topP"),
            max_tokens=inference_config.get("maxTokens"),
        ),
    }


def _handle_error(
    error: Exception,
    span: Span,
    start_time: float,
    instruments: Instruments,
    model: Optional[str],
):
    duration = max((default_timer() - start_time), 0)
    handle_span_exception(span, error)
    record_metrics(
        instruments=instruments,
        duration=duration,
        model=model,
        error_type=error.__qualname__,
    )


def invoke_model_wrapper(
    original_function: Callable,
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        span_attributes = {}
        with tracer.start_as_current_span(
            name="bedrock.invoke_model",
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
                invoke_model_result["body"] = StreamingBody(
                    BytesIO(response_body), len(response_body)
                )
                try:
                    parsed_response_body = json.loads(response_body)
                except json.JSONDecodeError:
                    # TODO:
                    pass

                # TODO: handle parsed response based on model type

        return invoke_model_result

    return wrapper


def invoke_model_with_response_stream_wrapper(
    original_function: Callable,
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        span_attributes = {}
        with tracer.start_as_current_span(
            name="bedrock.invoke_model_with_response_stream",
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
                invoke_model_result["body"] = StreamingBody(
                    response_body, len(response_body)
                )
                try:
                    parsed_response_body = json.loads(response_body)
                except json.JSONDecodeError:
                    # TODO:
                    pass

                # TODO: handle parsed response based on model type

        return invoke_model_result

    return wrapper


def converse_wrapper(
    original_function: Callable,
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        model = kwargs.get("modelId")
        span_attributes = generate_attributes_from_converse_input(
            kwargs=kwargs, capture_content=capture_content
        )

        with tracer.start_as_current_span(
            name="bedrock.converse",
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            start_time = default_timer()
            try:
                result = original_function(*args, **kwargs)
                record_converse_result_attributes(
                    result=result,
                    span=span,
                    start_time=start_time,
                    instruments=instruments,
                    capture_content=capture_content,
                    model=model,
                )
                return result
            except Exception as error:
                _handle_error(
                    error=error,
                    span=span,
                    start_time=start_time,
                    instruments=instruments,
                    model=model,
                )
                raise

    return wrapper


def converse_stream_wrapper(
    original_function: Callable,
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        model = kwargs.get("modelId")
        span_attributes = generate_attributes_from_converse_input(
            kwargs=kwargs, capture_content=capture_content
        )

        with tracer.start_as_current_span(
            name="bedrock.converse_stream",
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            start_time = default_timer()
            try:
                result = original_function(*args, **kwargs)
                if "stream" in result and isinstance(result["stream"], EventStream):
                    result["stream"] = ConverseStreamWrapper(
                        stream=result["stream"],
                        stream_done_callback=partial(
                            record_converse_result_attributes,
                            span=span,
                            start_time=start_time,
                            instruments=instruments,
                            capture_content=capture_content,
                            model=model,
                        ),
                        stream_error_callback=partial(
                            _handle_error,
                            span=span,
                            start_time=start_time,
                            instruments=instruments,
                            model=model,
                        ),
                    )

                return result
            except Exception as error:
                _handle_error(
                    error=error,
                    span=span,
                    start_time=start_time,
                    instruments=instruments,
                    model=model,
                )
                raise

    return wrapper


def invoke_agent_wrapper(
    original_function: Callable,
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
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
        client = wrapped(*args, **kwargs)
        # TODO: error handling
        if service_name == "bedrock-runtime":
            client.invoke_model = invoke_model_wrapper(
                original_function=client.invoke_model,
                tracer=tracer,
                instruments=instruments,
                capture_content=capture_content,
            )
            client.invoke_model_with_response_stream = (
                invoke_model_with_response_stream_wrapper(
                    original_function=client.invoke_model_with_response_stream,
                    tracer=tracer,
                    instruments=instruments,
                    capture_content=capture_content,
                )
            )
            client.converse = converse_wrapper(
                original_function=client.converse,
                tracer=tracer,
                instruments=instruments,
                capture_content=capture_content,
            )
            client.converse_stream = converse_stream_wrapper(
                original_function=client.converse_stream,
                tracer=tracer,
                instruments=instruments,
                capture_content=capture_content,
            )
        elif service_name == "bedrock-agent-runtime":
            client.invoke_agent = invoke_agent_wrapper(
                original_function=client.invoke_agent,
                tracer=tracer,
                instruments=instruments,
                capture_content=capture_content,
            )

        return client

    return traced_method
