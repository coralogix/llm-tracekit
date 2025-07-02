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
    session_id: str,
    input_text: str,
    expect_content: bool,
    enable_trace: bool,
):
    result = bedrock_agent_client.invoke_agent(
        agentAliasId=agent_alias_id,
        agentId=agent_id,
        inputText=input_text,
        sessionId=session_id,
        enableTrace=enable_trace,
    )

    response_text = ""
    usage_input_tokens = 0
    usage_output_tokens = 0
    foundation_model = None
    temperature = None
    top_p = None
    top_k = None
    max_tokens = None

    for event in result["completion"]:
        if "chunk" in event:
            response_text += event["chunk"]["bytes"].decode()

        if enable_trace and "trace" in event and "trace" in event.get("trace", {}):
            trace_data = event["trace"]["trace"]
            for key in [
                "preProcessingTrace",
                "postProcessingTrace",
                "orchestrationTrace",
                "routingClassifierTrace",
            ]:
                if key not in trace_data:
                    continue

                sub_trace = trace_data[key]
                usage_data = (
                    sub_trace.get("modelInvocationOutput", {})
                    .get("metadata", {})
                    .get("usage", {})
                )
                usage_input_tokens += usage_data.get("inputTokens", 0)
                usage_output_tokens += usage_data.get("outputTokens", 0)

                model_invocation_input = sub_trace.get("modelInvocationInput", {})
                if foundation_model is None:
                    foundation_model = model_invocation_input.get("foundationModel")

                inference_config = model_invocation_input.get(
                    "inferenceConfiguration", {}
                )
                temperature = inference_config.get("temperature")
                top_p = inference_config.get("topP")
                top_k = inference_config.get("topK")
                max_tokens = inference_config.get("maximumLength")

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    final_input_tokens = usage_input_tokens if enable_trace else None
    final_output_tokens = usage_output_tokens if enable_trace else None

    assert_attributes_in_span(
        span=span,
        span_name="bedrock.invoke_agent",
        agent_id=agent_id,
        agent_alias_id=agent_alias_id,
        usage_input_tokens=final_input_tokens,
        usage_output_tokens=final_output_tokens,
        foundation_model=foundation_model,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        max_tokens=max_tokens,
    )

    expected_prompts = [{"role": "user", "content": input_text}]
    expected_completions = [{"message": {"role": "assistant", "content": response_text}}]

    assert_messages_in_span(
        span=span,
        expected_messages=expected_prompts,
        expect_content=expect_content,
    )

    assert_choices_in_span(
        span=span,
        expected_choices=expected_completions,
        expect_content=expect_content,
    )

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1
    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        usage_input_tokens=final_input_tokens,
        usage_output_tokens=final_output_tokens,
        foundation_model=foundation_model,
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
        input_text="say this is a test",
        expect_content=True,
        enable_trace=True,
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
        input_text="say this is a test",
        expect_content=False,
        enable_trace=True,
    )


@pytest.mark.vcr()
def test_invoke_agent_with_trace_disabled(
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
        session_id="no-trace-01",
        input_text="hello",
        expect_content=True,
        enable_trace=False,
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
