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
    response_model: str = None,
    agent_name: Optional[str] = None,
    operation_name = "chat"
):
    assert operation_name == span.attributes[GenAIAttributes.GEN_AI_OPERATION_NAME]

    assert (
        GenAIAttributes.GenAiSystemValues.OPENAI.value
        == span.attributes[GenAIAttributes.GEN_AI_SYSTEM]
    )

    if response_model:
        assert response_model == span.attributes[GenAIAttributes.GEN_AI_RESPONSE_MODEL]
    else:
        assert GenAIAttributes.GEN_AI_RESPONSE_MODEL not in span.attributes

    if agent_name is not None:
        assert agent_name == span.attributes[GenAIAttributes.GEN_AI_AGENT_NAME]
    else:
        assert GenAIAttributes.GEN_AI_AGENT_NAME not in span.attributes