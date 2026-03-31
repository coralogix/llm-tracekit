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

import os

import pytest
from anthropic import Anthropic
from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from opentelemetry.semconv._incubating.attributes import (
    server_attributes as ServerAttributes,
)
from opentelemetry.semconv._incubating.metrics import gen_ai_metrics  # type: ignore[attr-defined]

MODEL = os.environ.get("ANTHROPIC_TEST_MODEL", "claude-haiku-4-5-20251001")


@pytest.mark.vcr()
def test_messages_metrics(metric_reader, instrument_with_content):
    client = Anthropic()
    client.messages.create(
        model=MODEL,
        max_tokens=1024,
        temperature=0,
        messages=[{"role": "user", "content": "Say this is a test"}],
    )

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1
    metric_data = metrics[0].scope_metrics[0].metrics
    assert len(metric_data) == 2

    duration_metric = next(
        m
        for m in metric_data
        if m.name == gen_ai_metrics.GEN_AI_CLIENT_OPERATION_DURATION
    )
    assert len(duration_metric.data.data_points) >= 1
    dp = duration_metric.data.data_points[0]
    assert (
        dp.attributes[GenAIAttributes.GEN_AI_SYSTEM]
        == GenAIAttributes.GenAiSystemValues.ANTHROPIC.value
    )
    assert dp.attributes[GenAIAttributes.GEN_AI_REQUEST_MODEL] == MODEL
    assert GenAIAttributes.GEN_AI_RESPONSE_MODEL in dp.attributes
    assert ServerAttributes.SERVER_ADDRESS in dp.attributes

    token_metric = next(
        m for m in metric_data if m.name == gen_ai_metrics.GEN_AI_CLIENT_TOKEN_USAGE
    )
    types = {
        p.attributes[GenAIAttributes.GEN_AI_TOKEN_TYPE]
        for p in token_metric.data.data_points
    }
    assert GenAIAttributes.GenAiTokenTypeValues.INPUT.value in types
    assert GenAIAttributes.GenAiTokenTypeValues.COMPLETION.value in types
