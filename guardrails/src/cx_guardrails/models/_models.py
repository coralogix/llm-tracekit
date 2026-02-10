from enum import Enum


class PIICategory(str, Enum):
    PHONE_NUMBER = "phone_number"
    EMAIL_ADDRESS = "email_address"
    CREDIT_CARD = "credit_card"
    IBAN_CODE = "iban_code"
    US_SSN = "us_ssn"


class GuardrailType(str, Enum):
    PII = "pii"
    PROMPT_INJECTION = "prompt_injection"
    CUSTOM = "custom"
    TOXICITY = "toxicity"
    TEST_POLICY = "test_policy"


class GuardrailsTarget(str, Enum):
    PROMPT = "prompt"
    RESPONSE = "response"


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
