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

from timeit import default_timer
from typing import Any

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.semconv._incubating.attributes import (
    server_attributes as ServerAttributes,
)
from opentelemetry.trace import SpanKind, Tracer
from opentelemetry.util.types import AttributeValue

from llm_tracekit.core import handle_span_exception, Instruments
from llm_tracekit.microsoft_foundry.utils import (
    MICROSOFT_FOUNDRY_SYSTEM,
    get_chat_request_attributes,
    get_chat_response_attributes,
    get_responses_request_attributes,
    get_responses_response_attributes,
    get_embedding_request_attributes,
    get_embedding_response_attributes,
    is_streaming,
)
from llm_tracekit.microsoft_foundry.stream_wrappers import (
    ChatStreamWrapper,
    AsyncChatStreamWrapper,
    ResponsesStreamWrapper,
    AsyncResponsesStreamWrapper,
)


def _usage_prompt_and_completion_tokens(result: Any) -> tuple[int | None, int | None]:
    """Read token counts from Chat Completions or Responses usage objects."""
    if result is None:
        return None, None
    usage = getattr(result, "usage", None)
    if usage is None:
        return None, None
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    if prompt is not None or completion is not None:
        return prompt, completion
    input_tok = getattr(usage, "input_tokens", None)
    output_tok = getattr(usage, "output_tokens", None)
    return input_tok, output_tok


def _record_metrics(
    instruments: Instruments,
    duration: float,
    result: Any,
    span_attributes: dict,
    error_type: str | None,
    operation_name: str = GenAIAttributes.GenAiOperationNameValues.CHAT.value,
):
    common_attributes: dict[str, AttributeValue] = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: operation_name,
        GenAIAttributes.GEN_AI_SYSTEM: MICROSOFT_FOUNDRY_SYSTEM,
    }

    request_model = span_attributes.get(GenAIAttributes.GEN_AI_REQUEST_MODEL)
    if request_model:
        common_attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL] = request_model

    if error_type:
        common_attributes["error.type"] = error_type

    if result and getattr(result, "model", None):
        common_attributes[GenAIAttributes.GEN_AI_RESPONSE_MODEL] = result.model

    if result and getattr(result, "service_tier", None):
        common_attributes[GenAIAttributes.GEN_AI_OPENAI_RESPONSE_SERVICE_TIER] = (
            result.service_tier
        )

    if result and getattr(result, "system_fingerprint", None):
        common_attributes[GenAIAttributes.GEN_AI_OPENAI_RESPONSE_SYSTEM_FINGERPRINT] = (
            result.system_fingerprint
        )

    if ServerAttributes.SERVER_ADDRESS in span_attributes:
        common_attributes[ServerAttributes.SERVER_ADDRESS] = span_attributes[
            ServerAttributes.SERVER_ADDRESS
        ]

    if ServerAttributes.SERVER_PORT in span_attributes:
        common_attributes[ServerAttributes.SERVER_PORT] = span_attributes[
            ServerAttributes.SERVER_PORT
        ]

    instruments.operation_duration_histogram.record(
        duration,
        attributes=common_attributes,
    )

    prompt_tokens, completion_tokens = _usage_prompt_and_completion_tokens(result)
    if prompt_tokens is not None:
        input_attributes = {
            **common_attributes,
            GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.INPUT.value,
        }
        instruments.token_usage_histogram.record(
            prompt_tokens,
            attributes=input_attributes,
        )

    if completion_tokens is not None:
        completion_attributes = {
            **common_attributes,
            GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.COMPLETION.value,
        }
        instruments.token_usage_histogram.record(
            completion_tokens,
            attributes=completion_attributes,
        )


def _record_embedding_metrics(
    instruments: Instruments,
    duration: float,
    result: Any,
    span_attributes: dict,
    error_type: str | None,
):
    common_attributes: dict[str, AttributeValue] = {
        GenAIAttributes.GEN_AI_OPERATION_NAME: GenAIAttributes.GenAiOperationNameValues.EMBEDDINGS.value,
        GenAIAttributes.GEN_AI_SYSTEM: MICROSOFT_FOUNDRY_SYSTEM,
    }

    request_model = span_attributes.get(GenAIAttributes.GEN_AI_REQUEST_MODEL)
    if isinstance(request_model, str) and request_model:
        common_attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL] = request_model

    if error_type:
        common_attributes["error.type"] = error_type

    if result and getattr(result, "model", None):
        common_attributes[GenAIAttributes.GEN_AI_RESPONSE_MODEL] = result.model

    if ServerAttributes.SERVER_ADDRESS in span_attributes:
        server_address = span_attributes[ServerAttributes.SERVER_ADDRESS]
        if isinstance(server_address, str) and server_address:
            common_attributes[ServerAttributes.SERVER_ADDRESS] = server_address

    if ServerAttributes.SERVER_PORT in span_attributes:
        server_port = span_attributes[ServerAttributes.SERVER_PORT]
        if isinstance(server_port, int):
            common_attributes[ServerAttributes.SERVER_PORT] = server_port

    instruments.operation_duration_histogram.record(
        duration,
        attributes=common_attributes,
    )

    usage = getattr(result, "usage", None) if result else None
    if usage:
        prompt_tokens = getattr(usage, "prompt_tokens", None) or getattr(
            usage, "total_tokens", None
        )
        if prompt_tokens is not None:
            input_attributes: dict[str, AttributeValue] = {
                **common_attributes,
                GenAIAttributes.GEN_AI_TOKEN_TYPE: GenAIAttributes.GenAiTokenTypeValues.INPUT.value,
            }
            instruments.token_usage_histogram.record(
                prompt_tokens,
                attributes=input_attributes,
            )


def chat_completions_create(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    """Wrap chat.completions.create for tracing."""

    def traced_method(wrapped, instance, args, kwargs):
        span_attributes = {
            **get_chat_request_attributes(kwargs, instance, capture_content)
        }

        span_name = f"{span_attributes[GenAIAttributes.GEN_AI_OPERATION_NAME]} {span_attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL]}"
        with tracer.start_as_current_span(
            name=span_name,
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            start = default_timer()
            result = None
            error_type = None
            try:
                result = wrapped(*args, **kwargs)
                if is_streaming(kwargs):
                    return ChatStreamWrapper(result, span, capture_content)

                if span.is_recording():
                    span.set_attributes(
                        get_chat_response_attributes(result, capture_content)
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
                    instruments,
                    duration,
                    result,
                    span_attributes,
                    error_type,
                )

    return traced_method


def async_chat_completions_create(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    """Wrap async chat.completions.create for tracing."""

    async def traced_method(wrapped, instance, args, kwargs):
        span_attributes = {
            **get_chat_request_attributes(kwargs, instance, capture_content)
        }

        span_name = f"{span_attributes[GenAIAttributes.GEN_AI_OPERATION_NAME]} {span_attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL]}"
        with tracer.start_as_current_span(
            name=span_name,
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            start = default_timer()
            result = None
            error_type = None
            try:
                result = await wrapped(*args, **kwargs)
                if is_streaming(kwargs):
                    return AsyncChatStreamWrapper(result, span, capture_content)

                if span.is_recording():
                    span.set_attributes(
                        get_chat_response_attributes(result, capture_content)
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
                    instruments,
                    duration,
                    result,
                    span_attributes,
                    error_type,
                )

    return traced_method


def responses_create(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    """Wrap responses.create for tracing."""

    def traced_method(wrapped, instance, args, kwargs):
        span_attributes = {
            **get_responses_request_attributes(dict(kwargs), instance, capture_content)
        }

        span_name = f"{span_attributes[GenAIAttributes.GEN_AI_OPERATION_NAME]} {span_attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL]}"
        with tracer.start_as_current_span(
            name=span_name,
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            start = default_timer()
            result = None
            error_type = None
            try:
                result = wrapped(*args, **kwargs)
                if is_streaming(kwargs):
                    return ResponsesStreamWrapper(result, span, capture_content)

                if span.is_recording():
                    span.set_attributes(
                        get_responses_response_attributes(result, capture_content)
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
                    instruments,
                    duration,
                    result,
                    span_attributes,
                    error_type,
                )

    return traced_method


def async_responses_create(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    """Wrap async responses.create for tracing."""

    async def traced_method(wrapped, instance, args, kwargs):
        span_attributes = {
            **get_responses_request_attributes(dict(kwargs), instance, capture_content)
        }

        span_name = f"{span_attributes[GenAIAttributes.GEN_AI_OPERATION_NAME]} {span_attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL]}"
        with tracer.start_as_current_span(
            name=span_name,
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            start = default_timer()
            result = None
            error_type = None
            try:
                result = await wrapped(*args, **kwargs)
                if is_streaming(kwargs):
                    return AsyncResponsesStreamWrapper(result, span, capture_content)

                if span.is_recording():
                    span.set_attributes(
                        get_responses_response_attributes(result, capture_content)
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
                    instruments,
                    duration,
                    result,
                    span_attributes,
                    error_type,
                )

    return traced_method


def embeddings_create(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    """Wrap embeddings.create for tracing."""

    def traced_method(wrapped, instance, args, kwargs):
        span_attributes = get_embedding_request_attributes(
            kwargs=kwargs,
            client_instance=instance,
            capture_content=capture_content,
        )

        span_name = f"{span_attributes[GenAIAttributes.GEN_AI_OPERATION_NAME]} {span_attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL]}"
        with tracer.start_as_current_span(
            name=span_name,
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            start = default_timer()
            result = None
            error_type = None
            try:
                result = wrapped(*args, **kwargs)
                if span.is_recording():
                    span.set_attributes(
                        get_embedding_response_attributes(result, capture_content)
                    )
                span.end()
                return result
            except Exception as error:
                error_type = type(error).__qualname__
                handle_span_exception(span, error)
                raise
            finally:
                duration = max((default_timer() - start), 0)
                _record_embedding_metrics(
                    instruments=instruments,
                    duration=duration,
                    result=result,
                    span_attributes=span_attributes,
                    error_type=error_type,
                )

    return traced_method


def async_embeddings_create(
    tracer: Tracer,
    instruments: Instruments,
    capture_content: bool,
):
    """Wrap async embeddings.create for tracing."""

    async def traced_method(wrapped, instance, args, kwargs):
        span_attributes = get_embedding_request_attributes(
            kwargs=kwargs,
            client_instance=instance,
            capture_content=capture_content,
        )

        span_name = f"{span_attributes[GenAIAttributes.GEN_AI_OPERATION_NAME]} {span_attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL]}"

        with tracer.start_as_current_span(
            name=span_name,
            kind=SpanKind.CLIENT,
            attributes=span_attributes,
            end_on_exit=False,
        ) as span:
            start = default_timer()
            result = None
            error_type = None
            try:
                result = await wrapped(*args, **kwargs)
                if span.is_recording():
                    span.set_attributes(
                        get_embedding_response_attributes(result, capture_content)
                    )
                span.end()
                return result
            except Exception as error:
                error_type = type(error).__qualname__
                handle_span_exception(span, error)
                raise
            finally:
                duration = max((default_timer() - start), 0)
                _record_embedding_metrics(
                    instruments=instruments,
                    duration=duration,
                    result=result,
                    span_attributes=span_attributes,
                    error_type=error_type,
                )

    return traced_method
