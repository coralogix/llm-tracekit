from timeit import default_timer
from typing import Any, Callable, Dict, Optional

from botocore.eventstream import EventStream, EventStreamError
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.trace import Span
from wrapt import ObjectProxy

from llm_tracekit.bedrock.utils import record_metrics
from llm_tracekit.instruments import Instruments
from llm_tracekit.span_builder import (
    Choice,
    Message,
    generate_base_attributes,
    generate_choice_attributes,
    generate_message_attributes,
    generate_response_attributes,
    remove_attributes_with_null_values,
)


def generate_attributes_from_invoke_agent_input(
    kwargs: Dict[str, Any], capture_content: bool
) -> Dict[str, Any]:
    base_attributes = generate_base_attributes(
        system=GenAIAttributes.GenAiSystemValues.AWS_BEDROCK
    )
    message_attributes = generate_message_attributes(
        messages=[Message(role="user", content=kwargs.get("inputText"))],
        capture_content=capture_content,
    )

    attributes = {
        **base_attributes,
        **message_attributes,
        GenAIAttributes.GEN_AI_AGENT_ID: kwargs.get("agentId"),
        GenAIAttributes.GEN_AI_AGENT_NAME: kwargs.get("agentAliasId"),
    }

    return remove_attributes_with_null_values(attributes)


def record_invoke_agent_result_attributes(
    content: Optional[str],
    usage_input_tokens: Optional[int],
    usage_output_tokens: Optional[int],
    span: Span,
    start_time: float,
    instruments: Instruments,
    capture_content: bool,
):
    try:
        attributes = {
            **generate_response_attributes(
                usage_input_tokens=usage_input_tokens,
                usage_output_tokens=usage_output_tokens,
            ),
            **generate_choice_attributes(
                choices=[Choice(role="assistant", content=content)],
                capture_content=capture_content,
            ),
        }
        span.set_attributes(attributes)
    finally:
        duration = max((default_timer() - start_time), 0)
        span.end()
        record_metrics(
            instruments=instruments,
            duration=duration,
            usage_input_tokens=usage_input_tokens,
            usage_output_tokens=usage_output_tokens,
        )


class InvokeAgentStreamWrapper(ObjectProxy):
    """Wrapper for botocore.eventstream.EventStream"""

    def __init__(
        self,
        stream: EventStream,
        stream_done_callback: Callable[
            [Optional[str], Optional[int], Optional[int]], None
        ],
        stream_error_callback: Callable[[Exception], None],
    ):
        super().__init__(stream)

        self._stream_done_callback = stream_done_callback
        self._stream_error_callback = stream_error_callback
        self._content = None
        self._usage_input_tokens: Optional[int] = None
        self._usage_output_tokens: Optional[int] = None

    def __iter__(self):
        try:
            for event in self.__wrapped__:
                self._process_event(event)
                yield event

            self._stream_done_callback(
                self._content, self._usage_input_tokens, self._usage_output_tokens
            )
        except EventStreamError as exc:
            self._stream_error_callback(exc)
            raise

    def _process_usage_data(self, usage: Dict[str, int]):
        if "inputTokens" in usage:
            if self._usage_input_tokens is None:
                self._usage_input_tokens = 0

            self._usage_input_tokens += usage["inputTokens"]

        if "outputTokens" in usage:
            if self._usage_output_tokens is None:
                self._usage_output_tokens = 0

            self._usage_output_tokens += usage["outputTokens"]

    def _process_event(self, event):
        if "chunk" in event:
            if self._content is None:
                self._content = ""

            encoded_content = event["chunk"].get("bytes")
            if encoded_content is not None:
                # TODO: check if we need to handle b64 decoding
                self._content += encoded_content.decode()

        if "trace" in event:
            for key in [
                "preProcessingTrace",
                "postProcessingTrace",
                "orchestrationTrace",
                "routingClassifierTrace",
            ]:
                usage_data = (
                    event["trace"]
                    .get(key, {})
                    .get("modelInvocationOutput", {})
                    .get("metadata", {})
                    .get("usage")
                )
                if usage_data is not None:
                    self._process_usage_data(usage_data)
