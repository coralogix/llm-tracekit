from enum import Enum, auto


class PIICategorie(str, Enum):
    PHONE_NUMBER = "phone_number"
    EMAIL_ADDRESS = "email_address"
    CREDIT_CARD = "credit_card"
    US_SSN = "us_ssn"


class GuardrailType(str, Enum):
    PII = "pii"
    PROMPT_INJECTION = "prompt_injection"
    CUSTOM = "custom"


class GuardrailsTarget(str, Enum):
    PROMPT = "prompt"
    RESPONSE = "response"


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
