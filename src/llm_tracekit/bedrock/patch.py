# Copyright Coralogix Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from functools import partial, wraps
from io import BytesIO
from timeit import default_timer
from typing import Callable, Optional

from botocore.eventstream import EventStream
from botocore.response import StreamingBody
from opentelemetry.trace import Span, SpanKind, Tracer

from llm_tracekit.bedrock.converse import (
    ConverseStreamWrapper,
    generate_attributes_from_converse_input,
    record_converse_result_attributes,
)
from llm_tracekit.bedrock.invoke_agent import (
    InvokeAgentStreamWrapper,
    generate_attributes_from_invoke_agent_input,
    record_invoke_agent_result_attributes,
)
from llm_tracekit.bedrock.invoke_model import (
    InvokeModelWithResponseStreamWrapper,
    generate_attributes_from_invoke_input,
    record_invoke_model_result_attributes,
)
from llm_tracekit.bedrock.utils import record_metrics
from llm_tracekit.instrumentation_utils import handle_span_exception
from llm_tracekit.instruments import Instruments


def _handle_error(
    error: Exception,
    span: Span,
    start_time: float,
    instruments: Instruments,
    model: Optional[str] = None,
):
    duration = max((default_timer() - start_time), 0)
    handle_span_exception(span, error)
    record_metrics(
        instruments=instruments,
        duration=duration,
        request_model=model,
        error_type=type(error).__qualname__,
    )


def invoke_model_wrapper(
    original_function: Callable,
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        model = kwargs.get("modelId")
        span_attributes = generate_attributes_from_invoke_input(
            kwargs=kwargs, capture_content=capture_content
        )
        with tracer.start_as_current_span(
            name="bedrock.invoke_model",
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            start_time = default_timer()
            try:
                result = original_function(*args, **kwargs)
                body = result.get("body")
                if body is not None:
                    body_content = body.read()
                    # The response body is a stream, and reading the stream consumes it, so we have to recreate
                    # it to keep the original response usable
                    result["body"] = StreamingBody(
                        BytesIO(body_content), len(body_content)
                    )

                    record_invoke_model_result_attributes(
                        result_body=body_content,
                        span=span,
                        start_time=start_time,
                        instruments=instruments,
                        capture_content=capture_content,
                        model_id=model,
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


def invoke_model_with_response_stream_wrapper(
    original_function: Callable,
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    @wraps(original_function)
    def wrapper(*args, **kwargs):
        model = kwargs.get("modelId")
        span_attributes = generate_attributes_from_invoke_input(
            kwargs=kwargs, capture_content=capture_content
        )
        with tracer.start_as_current_span(
            name="bedrock.invoke_model_with_response_stream",
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            start_time = default_timer()
            try:
                result = original_function(*args, **kwargs)
                if "body" in result and isinstance(result["body"], EventStream):
                    result["body"] = InvokeModelWithResponseStreamWrapper(
                        stream=result["body"],
                        stream_done_callback=partial(
                            record_invoke_model_result_attributes,
                            span=span,
                            start_time=start_time,
                            instruments=instruments,
                            capture_content=capture_content,
                            model_id=model,
                        ),
                        stream_error_callback=partial(
                            _handle_error,
                            span=span,
                            start_time=start_time,
                            instruments=instruments,
                            model=model,
                        ),
                        model_id=model,
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
        span_attributes = generate_attributes_from_invoke_agent_input(
            kwargs=kwargs, capture_content=capture_content
        )
        with tracer.start_as_current_span(
            name="bedrock.invoke_agent",
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            start_time = default_timer()
            try:
                result = original_function(*args, **kwargs)
                if "completion" in result:
                    result["completion"] = InvokeAgentStreamWrapper(
                        stream=result["completion"],
                        stream_done_callback=partial(
                            record_invoke_agent_result_attributes,
                            span=span,
                            start_time=start_time,
                            instruments=instruments,
                            capture_content=capture_content,
                        ),
                        stream_error_callback=partial(
                            _handle_error,
                            span=span,
                            start_time=start_time,
                            instruments=instruments,
                        ),
                    )

                return result
            except Exception as error:
                _handle_error(
                    error=error,
                    span=span,
                    start_time=start_time,
                    instruments=instruments,
                )
                raise

    return wrapper


def create_client_wrapper(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    def traced_method(wrapped, instance, args, kwargs):
        service_name = kwargs.get("service_name")
        client = wrapped(*args, **kwargs)
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
