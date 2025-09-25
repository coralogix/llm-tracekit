import pytest

from guardrails.src.models import PII, PromptInjection, CustomGuardrail
from guardrails.src.guardrails import Guardrails



# Fixtures for reusable test data
@pytest.fixture
def sample_pii_config():
    """Fixture providing a sample PII configuration"""
    return PII(
        name="test-pii",
        categories=["email", "phone", "credit_card"],
        threshold=0.8
    )


@pytest.fixture
def sample_injection_config():
    """Fixture providing a sample prompt injection configuration"""
    return PromptInjection(
        name="test-injection",
        categories=["code_execution", "illegal_topics"],
        threshold=0.7
    )


@pytest.fixture
def sample_custom_config():
    """Fixture providing a sample custom guardrail configuration"""
    return CustomGuardrail(
        name="test-custom",
        criteria="Check for brand safety and appropriate content",
        threshold=0.6
    )


@pytest.fixture
def guardrails_client():
    """Fixture providing a configured guardrails client"""
    return Guardrails(
        api_key="test-api-key",
        application_name="test-app",
        subsystem_name="test-subsystem",
        domain_url="test-domain-url",
    )


@pytest.fixture
def sample_request_data():
    """Fixture providing sample request data"""
    return {
        "message": "Please contact me at john.doe@example.com or call 555-123-4567",
        "api_key": "test-key",
        "application_name": "test-app",
        "subsystem_name": "test-subsystem",
        "domain_url": "test-domain-url"
    }