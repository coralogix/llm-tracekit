import pytest

from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from httpx import Response, Request

from guardrails.tests.main import app
from guardrails.src.error import GuardrailsAPIResponseError


# Test client for FastAPI
client = TestClient(app)

def test_client_initialization(guardrails_client):
    """Test client initialization with required parameters"""
    assert guardrails_client.config.api_key == "test-api-key"
    assert guardrails_client.config.application_name == "test-app"
    assert guardrails_client.config.subsystem_name == "test-subsystem"
    assert guardrails_client.config.domain_url == "test-domain-url"
    assert guardrails_client.config.timeout == 100  # Default
    assert guardrails_client.config.retries == 3   # Default

@pytest.mark.asyncio
async def test_client_context_manager(guardrails_client):
    """Test client as async context manager"""
    async with guardrails_client as client:
        assert client is not None
        # Context manager should work without errors

@pytest.mark.asyncio
@patch('httpx.AsyncClient.post')
async def test_successful_guardrails_run(mock_post, guardrails_client, sample_pii_config):
    """Test successful guardrails run with mocked HTTP response"""
    # Mock successful response
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = '''{
        "results": [{
            "name": "test-result",
            "detected": true,
            "score": 0.9,
            "explanation": "Found PII in message",
            "threshold": 0.8
        }],
        "guardrails_config": []
    }'''
    mock_post.return_value = mock_response
    
    # Run guardrails
    results = await guardrails_client.run("Test message", [sample_pii_config])
    
    # Verify results
    assert len(results) == 1
    assert results[0].name == "test-result"
    assert results[0].detected is True
    assert results[0].score == 0.9
    
    # Verify HTTP call was made
    mock_post.assert_called_once()

@pytest.mark.asyncio
@patch('httpx.AsyncClient.post')
async def test_guardrails_run_http_error(mock_post, guardrails_client, sample_pii_config):
    """Test guardrails run with HTTP error response"""
    # Mock error response
    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_post.return_value = mock_response
    
    # Should raise exception for HTTP error
    with pytest.raises(Exception) as exc_info:
        await guardrails_client.run("Test message", [sample_pii_config])
    
    assert isinstance(exc_info.value, GuardrailsAPIResponseError)

@pytest.mark.asyncio
@patch('httpx.AsyncClient.post')
async def test_async_retrying_on_failure(mock_post, guardrails_client, sample_pii_config):
    """Test AsyncRetrying with mocked failed attempts"""
    # Mock failed response
    mock_response_failure = Response(
        status_code=500,
        text='Internal Server Error',
        request=Request("POST", "https://example.com/guardrails/run")
    )

    # Mock success response
    mock_response_success = Response(
        status_code=200,
        text='''{
            "results": [{
                "name": "test-result",
                "detected": true,
                "score": 0.9,
                "explanation": "Found PII in message",
                "threshold": 0.8
            }],
            "guardrails_config": []
        }''',
        request=Request("POST", "https://example.com/guardrails/run")
    )

    # Set up the mock to fail twice before succeeding
    mock_post.side_effect = [
        mock_response_failure,  # Fail 1
        mock_response_failure,  # Fail 2
        mock_response_success  # Success
    ]

    # Assign the mock to the client's post method
    guardrails_client._client.post = mock_post

    # Attempt to run guardrails, expecting retries
    results = await guardrails_client.run("Test message", [sample_pii_config])

    # Verify that retries were attempted
    assert mock_post.call_count == 3  # Ensure retries were attempted twice before success
    assert isinstance(results, list)
    assert len(results) == 1


if __name__ == "__main__":
    # Run tests when script is executed directly
    pytest.main([__file__, "-v"])