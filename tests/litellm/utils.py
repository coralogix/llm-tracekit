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


from typing import Optional

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)

def assert_attributes(
    span: ReadableSpan,
    system: str,
    operation_name: str,
    request_model: str,
    response_model: Optional[str] = None,
    response_id: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None
):
    assert system == span.attributes[GenAIAttributes.GEN_AI_SYSTEM]

    assert operation_name == span.attributes[GenAIAttributes.GEN_AI_OPERATION_NAME]

    assert request_model == span.attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL]

    if response_model is not None:
        assert response_model == span.attributes[GenAIAttributes.GEN_AI_RESPONSE_MODEL]
        
    if response_id is not None:
        assert response_id == span.attributes[GenAIAttributes.GEN_AI_RESPONSE_ID]   

    if input_tokens is not None:
        assert input_tokens == span.attributes[GenAIAttributes.GEN_AI_USAGE_INPUT_TOKENS]   

    if output_tokens is not None:
        assert output_tokens == span.attributes[GenAIAttributes.GEN_AI_USAGE_OUTPUT_TOKENS]


def find_last_response_span(spans: list[ReadableSpan]) -> ReadableSpan:
    for span in reversed(spans):
        if span.name == "litellm_request":
            return span