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

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)


def assert_base_attributes(
    span: ReadableSpan,
    system: str,
    request_model: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
):
    """Assert base GenAI attributes on a span."""
    assert span.attributes is not None

    assert span.attributes[GenAIAttributes.GEN_AI_SYSTEM] == system
    assert span.attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL] == request_model

    if input_tokens is not None:
        assert (
            span.attributes[GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS] == input_tokens
        )

    if output_tokens is not None:
        assert (
            span.attributes[GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS] == output_tokens
        )


def get_call_llm_spans(spans: list[ReadableSpan]) -> list[ReadableSpan]:
    """Filter spans to get only call_llm spans."""
    return [span for span in spans if span.name == "call_llm"]
