from io import BytesIO
import json
from functools import wraps, partial
from timeit import default_timer
from typing import Any, Callable, Dict, Optional

# TODO: importing botocore at module-scope will not work if it's not installed
from botocore.eventstream import EventStream
from botocore.response import StreamingBody
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.trace import Span, SpanKind, Tracer

from llm_tracekit.bedrock.utils import parse_converse_message
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
from llm_tracekit.bedrock.stream_wrappers import ConverseStreamWrapper


def _record_metrics(
    instruments: Instruments,
    duration: float,
    model: Optional[str] = None,
    usage_input_tokens: Optional[int] = None,
    usage_output_tokens: Optional[int] = None,
    error_type: Optional[str] = None,
):
    common_attributes = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: GenAIAttributes.GenAiOperationNameValues.CHAT.value,
        GenAIAttributes.GEN_AI_SYSTEM: GenAIAttributes.GenAiSystemValues.AWS_BEDROCK.value,
    }

    if model is not None:
        common_attributes.update(
            {
                GenAIAttributes.GEN_AI_REQUEST_MODEL: model,
                GenAIAttributes.GEN_AI_RESPONSE_MODEL: model,
            }
        )

    if error_type:
        common_attributes["error.type"] = error_type

    instruments.operation_duration_histogram.record(
        duration,
        attributes=common_attributes,
    )

    if usage_input_tokens is not None:
        input_attributes = {
            **common_attributes,
            GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.INPUT.value,
        }
        instruments.token_usage_histogram.record(
            usage_input_tokens,
            attributes=input_attributes,
        )

    if usage_output_tokens is not None:
        completion_attributes = {
            **common_attributes,
            GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.COMPLETION.value,
        }
        instruments.token_usage_histogram.record(
            usage_output_tokens,
            attributes=completion_attributes,
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


def _generate_attributes_from_converse_input(
    kwargs: Dict[str, Any], capture_content: bool
) -> Dict[str, Any]:
    inference_config = kwargs.get("inferenceConfig", {})
    messages = []
    for system_message in kwargs.get("system", []):
        messages.append(Message(role="system", content=system_message.get("text")))

    for message in kwargs.get("messages", []):
        messages.append(
            parse_converse_message(
                role=message.get("role"), content_parts=message.get("content")
            )
        )

    # TODO: record tool definitions
    return {
        **generate_base_attributes(
            system=GenAIAttributes.GenAiSystemValues.AWS_BEDROCK
        ),
        **generate_request_attributes(
            model=kwargs.get("modelId"),
            temperature=inference_config.get("temperature"),
            top_p=inference_config.get("topP"),
            max_tokens=inference_config.get("maxTokens"),
        ),
        **generate_message_attributes(
            messages=messages, capture_content=capture_content
        ),
    }


def converse_wrapper(
    original_function: Callable,
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        model = kwargs.get("modelId")
        span_attributes = _generate_attributes_from_converse_input(
            kwargs=kwargs, capture_content=capture_content
        )

        with tracer.start_as_current_span(
            name="bedrock.converse",
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            start = default_timer()
            usage_input_tokens = None
            usage_output_tokens = None
            error_type = None
            try:
                result = original_function(*args, **kwargs)

                finish_reason = result.get("stopReason")
                if "stopReason" in result:
                    finish_reason = result["stopReason"]

                usage_data = result.get("usage", {})
                usage_input_tokens = usage_data.get("inputTokens")
                usage_output_tokens = usage_data.get("outputTokens")

                response_attributes = generate_response_attributes(
                    model=model,
                    finish_reasons=None if finish_reason is None else [finish_reason],
                    usage_input_tokens=usage_input_tokens,
                    usage_output_tokens=usage_output_tokens,
                )
                span.set_attributes(response_attributes)

                response_message = result.get("output", {}).get("message")
                if response_message is not None:
                    parsed_response_message = parse_converse_message(
                        role=response_message.get("role"),
                        content_parts=response_message.get("content"),
                    )
                    choice = Choice(
                        finish_reason=finish_reason,
                        role=parsed_response_message.role,
                        content=parsed_response_message.content,
                        tool_calls=parsed_response_message.tool_calls,
                    )
                    span.set_attributes(
                        generate_choice_attributes(
                            choices=[choice], capture_content=capture_content
                        )
                    )

                span.end()
                return result
            except Exception as error:
                error_type = type(error).__qualname__
                handle_span_exception(span, error)
                raise
            finally:
                duration = max((default_timer() - start), 0)
                _record_metrics(
                    instruments=instruments,
                    duration=duration,
                    model=model,
                    usage_input_tokens=usage_input_tokens,
                    usage_output_tokens=usage_output_tokens,
                    error_type=error_type,
                )

    return wrapper


def _stream_error_callback(
    error: Exception,
    span: Span,
    start_time: float,
    instruments: Instruments,
    model: Optional[str],
):
    duration = max((default_timer() - start_time), 0)
    handle_span_exception(span, error)
    _record_metrics(
        instruments=instruments,
        duration=duration,
        model=model,
        error_type=error.__qualname__,
    )


def _stream_success_callback(
    result: dict,
    span: Span,
    start_time: float,
    instruments: Instruments,
    capture_content: bool,
    model: Optional[str],
):
    # TODO: combine with converse wrapper function
    finish_reason = result.get("stopReason")
    if "stopReason" in result:
        finish_reason = result["stopReason"]

    usage_data = result.get("usage", {})
    usage_input_tokens = usage_data.get("inputTokens")
    usage_output_tokens = usage_data.get("outputTokens")

    response_attributes = generate_response_attributes(
        model=model,
        finish_reasons=None if finish_reason is None else [finish_reason],
        usage_input_tokens=usage_input_tokens,
        usage_output_tokens=usage_output_tokens,
    )
    span.set_attributes(response_attributes)

    response_message = result.get("output", {}).get("message")
    if response_message is not None:
        parsed_response_message = parse_converse_message(
            role=response_message.get("role"),
            content_parts=response_message.get("content"),
        )
        choice = Choice(
            finish_reason=finish_reason,
            role=parsed_response_message.role,
            content=parsed_response_message.content,
            tool_calls=parsed_response_message.tool_calls,
        )
        span.set_attributes(
            generate_choice_attributes(
                choices=[choice], capture_content=capture_content
            )
        )

    span.end()

    duration = max((default_timer() - start_time), 0)
    _record_metrics(
        instruments=instruments,
        duration=duration,
        model=model,
        usage_input_tokens=usage_input_tokens,
        usage_output_tokens=usage_output_tokens,
    )


def converse_stream_wrapper(
    original_function: Callable,
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        model = kwargs.get("modelId")
        span_attributes = _generate_attributes_from_converse_input(
            kwargs=kwargs, capture_content=capture_content
        )

        with tracer.start_as_current_span(
            name="bedrock.converse_stream",
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            start = default_timer()
            try:
                result = original_function(*args, **kwargs)
                if "stream" in result and isinstance(result["stream"], EventStream):
                    result["stream"] = ConverseStreamWrapper(
                        stream=result["stream"],
                        stream_done_callback=partial(
                            _stream_success_callback,
                            span=span,
                            start_time=start,
                            instruments=instruments,
                            capture_content=capture_content,
                            model=model,
                        ),
                        stream_error_callback=partial(
                            _stream_error_callback,
                            span=span,
                            start_time=start,
                            instruments=instruments,
                            model=model
                        ),
                    )
                    
                return result
            except Exception as error:
                handle_span_exception(span, error)
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
            client.invoke_model_with_response_stream = invoke_model_with_response_stream_wrapper(
                original_function=client.invoke_model_with_response_stream,
                tracer=tracer,
                instruments=instruments,
                capture_content=capture_content,
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
