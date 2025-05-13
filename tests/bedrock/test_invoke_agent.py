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

import boto3
import pytest
from botocore.exceptions import ClientError

from tests.bedrock.utils import assert_attributes_in_span, assert_expected_metrics
from tests.utils import assert_choices_in_span, assert_messages_in_span


def _run_and_check_invoke_agent(
    bedrock_agent_client,
    span_exporter,
    metric_reader,
    agent_id: str,
    agent_alias_id: str,
    expect_content: bool,
    session_id: str,
):
    result = bedrock_agent_client.invoke_agent(
        agentAliasId=agent_alias_id,
        agentId=agent_id,
        inputText="say this is a test",
        sessionId=session_id,
        enableTrace=True,
    )
    response_text = ""
    usage_input_tokens = 0
    usage_output_tokens = 0
    for event in result["completion"]:
        if "chunk" in event:
            response_text += event["chunk"]["bytes"].decode()
        if "trace" in event:
            for key in [
                "preProcessingTrace",
                "postProcessingTrace",
                "orchestrationTrace",
                "routingClassifierTrace",
            ]:
                usage_data = (
                    event["trace"]["trace"]
                    .get(key, {})
                    .get("modelInvocationOutput", {})
                    .get("metadata", {})
                    .get("usage", {})
                )
                usage_input_tokens += usage_data.get("inputTokens", 0)
                usage_output_tokens += usage_data.get("outputTokens", 0)

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    assert_attributes_in_span(
        span=spans[0],
        span_name="bedrock.invoke_agent",
        agent_id=agent_id,
        agent_alias_id=agent_alias_id,
        usage_input_tokens=usage_input_tokens,
        usage_output_tokens=usage_output_tokens,
    )

    expected_messages = [
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(
        span=spans[0],
        expected_messages=expected_messages,
        expect_content=expect_content,
    )

    expected_choice = {
        "message": {
            "role": "assistant",
            "content": response_text,
        }
    }
    assert_choices_in_span(
        span=spans[0], expected_choices=[expected_choice], expect_content=expect_content
    )

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        usage_input_tokens=usage_input_tokens,
        usage_output_tokens=usage_output_tokens,
    )


@pytest.mark.vcr()
def test_invoke_agent_with_content(
    bedrock_agent_client_with_content,
    span_exporter,
    metric_reader,
    agent_id: str,
    agent_alias_id: str,
):
    _run_and_check_invoke_agent(
        bedrock_agent_client=bedrock_agent_client_with_content,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        agent_id=agent_id,
        agent_alias_id=agent_alias_id,
        session_id="11",
        expect_content=True,
    )


@pytest.mark.vcr()
def test_invoke_agent_no_content(
    bedrock_agent_client_no_content,
    span_exporter,
    metric_reader,
    agent_id: str,
    agent_alias_id: str,
):
    _run_and_check_invoke_agent(
        bedrock_agent_client=bedrock_agent_client_no_content,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
        agent_id=agent_id,
        agent_alias_id=agent_alias_id,
        session_id="22",
        expect_content=False,
    )


@pytest.mark.vcr()
def test_invoke_agent_bad_auth(
    instrument_with_content,
    span_exporter,
    metric_reader,
    agent_id: str,
    agent_alias_id: str,
):
    client = boto3.client(
        "bedrock-agent-runtime",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        aws_session_token="test",
    )
    with pytest.raises(ClientError):
        client.invoke_agent(
            agentAliasId=agent_alias_id,
            agentId=agent_id,
            inputText="say this is a test",
            sessionId="123456",
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    assert_attributes_in_span(
        span=spans[0],
        span_name="bedrock.invoke_agent",
        agent_id=agent_id,
        agent_alias_id=agent_alias_id,
        error="ClientError",
    )

    expected_messages = [
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(
        span=spans[0], expected_messages=expected_messages, expect_content=True
    )

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        error="ClientError",
    )


@pytest.mark.vcr()
def test_invoke_agent_non_existing_agent(
    bedrock_agent_client_with_content, span_exporter, metric_reader
):
    agent_id = "agent_id"
    agent_alias_id = "agent_alias"
    with pytest.raises(Exception):
        bedrock_agent_client_with_content.invoke_agent(
            agentAliasId=agent_alias_id,
            agentId=agent_id,
            inputText="say this is a test",
            sessionId="123456",
        )

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1

    assert_attributes_in_span(
        span=spans[0],
        span_name="bedrock.invoke_agent",
        agent_id=agent_id,
        agent_alias_id=agent_alias_id,
        error="ValidationException",
    )

    expected_messages = [
        {"role": "user", "content": "say this is a test"},
    ]
    assert_messages_in_span(
        span=spans[0], expected_messages=expected_messages, expect_content=True
    )

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        error="ValidationException",
    )
