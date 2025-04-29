import pytest

from tests.bedrock.utils import assert_attributes_in_span, assert_expected_metrics
from tests.utils import assert_messages_in_span

def test_invoke_agent_with_content():
    pytest.skip("TODO")


def test_invoke_agent_no_content():
    pytest.skip("TODO")


def test_invoke_agent_bad_auth():
    pytest.skip("TODO")


@pytest.mark.vcr()
def test_invoke_agent_non_existing_agent(bedrock_agent_client_with_content, span_exporter, metric_reader):
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
    assert_messages_in_span(span=spans[0], expected_messages=expected_messages, expect_content=True)

    metrics = metric_reader.get_metrics_data().resource_metrics
    assert len(metrics) == 1

    metric_data = metrics[0].scope_metrics[0].metrics
    assert_expected_metrics(
        metrics=metric_data,
        error="ValidationException",
    )