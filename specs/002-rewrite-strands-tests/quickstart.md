# Quickstart: Rewrite Strands Agents Tests

## Prerequisites

- Python 3.10+
- uv (workspace package manager)
- AWS credentials (only for re-recording cassettes, not for running existing tests)

## Running Existing Tests (Cassette Replay)

```bash
cd instrumentations/strands-agents
uv run pytest tests/ -v
```

Tests will replay pre-recorded VCR cassettes. No AWS credentials or network access required.

## Re-recording Cassettes

To re-record cassettes against live Bedrock:

```bash
# Set real AWS credentials
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_SESSION_TOKEN="your-token"  # if using temporary credentials
export AWS_DEFAULT_REGION="us-east-1"

# Delete existing cassettes
rm -rf tests/cassettes/*.yaml

# Run tests — VCR will record new cassettes
cd instrumentations/strands-agents
uv run pytest tests/ -v
```

## Test Structure

```
tests/
├── __init__.py              # Package marker
├── conftest.py              # OTel fixtures, VCR config, instrumentor fixtures
├── test_strands_agents.py   # All test cases (8 functions)
├── utils.py                 # Span filtering + assertion helpers
└── cassettes/               # VCR-recorded Bedrock responses
    └── *.yaml
```

## Key Patterns

### Agent creation

```python
from strands import Agent
from strands.models.bedrock import BedrockModel

MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"

model = BedrockModel(model_id=MODEL_ID)
agent = Agent(model=model, system_prompt="Be helpful.", tools=[])
agent("Say hello.")
```

### Tool definition

```python
@Agent.tool
def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: The city name.

    Returns:
        Weather description.
    """
    return f"The weather in {city} is 22°C and sunny."
```

### Fixture usage in tests

```python
@pytest.mark.vcr()
def test_example(span_exporter, metric_reader, instrument_with_content):
    agent = _make_agent()
    agent("prompt")

    agent_spans = get_agent_spans(span_exporter)
    assert len(agent_spans) == 1
```
