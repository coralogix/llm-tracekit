import pytest

from fastapi.testclient import TestClient

from guardrails.tests.main import app
from guardrails.src.models import (
    PII, PromptInjection, CustomGuardrail,
    GuardrailsRequest
)


# Test client for FastAPI
client = TestClient(app)

def test_pii_model_creation(sample_pii_config):
    """Test PII model creation and attributes"""
    assert sample_pii_config.name == "test-pii"
    assert sample_pii_config.type == "pii"
    assert "email" in sample_pii_config.categories
    assert sample_pii_config.threshold == 0.8

def test_pii_model_default_values():
    """Test PII model with default values"""
    pii = PII(name="minimal-pii")
    
    assert pii.name == "minimal-pii"
    assert pii.type == "pii"
    assert pii.categories == []
    assert pii.threshold == 0.7 

def test_custom_guardrail_requires_criteria():
    """Test that CustomGuardrail requires criteria field"""
    with pytest.raises(Exception):  # Pydantic validation error
        CustomGuardrail(name="invalid")

def test_model_serialization(sample_pii_config):
    """Test model serialization to dict"""
    data = sample_pii_config.model_dump()
    
    assert data["name"] == "test-pii"
    assert data["type"] == "pii"
    assert data["categories"] == ["email", "phone", "credit_card"]
    assert data["threshold"] == 0.8


def test_guardrails_request_with_multiple_guardrails():
    """Test GuardrailsRequest with different guardrail types"""
    pii = PII(name="pii", categories=["email"])
    injection = PromptInjection(name="injection", categories=["code_execution"])
    custom = CustomGuardrail(name="custom", criteria="Test criteria")
    
    request = GuardrailsRequest(
        api_key="test",
        application_name="app",
        subsystem_name="subsystem",
        domain_url="domain-url",
        message="Test message",
        guardrails_config=[pii, injection, custom]
    )
    
    assert len(request.guardrails_config) == 3
    assert request.guardrails_config[0].type == "pii"
    assert request.guardrails_config[1].type == "prompt_injection"
    assert request.guardrails_config[2].type == "custom"


if __name__ == "__main__":
    # Run tests when script is executed directly
    pytest.main([__file__, "-v"])