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

class GuardrailCategory(str, Enum):
    SECURITY = "security"
    QUALITY = "quality"


class GuardrailModel(str, Enum):
    GPT_4O = "gpt-4o-2024-11-20"
    GPT_4_1 = "gpt-4.1-2025-04-14"
    GPT_4_1_MINI = "gpt-4.1-mini-2025-04-14"
    GPT_5 = "gpt-5"
    GPT_5_MINI = "gpt-5-mini"
    GPT_5_1 = "gpt-5.1-2025-11-13"
    GPT_5_2 = "gpt-5.2"
    GPT_5_4 = "gpt-5.4"
    GPT_5_4_MINI = "gpt-5.4-mini"
    GPT_5_5 = "gpt-5.5"
    O3 = "o3-2025-04-16"
    GEMINI_3_FLASH_PREVIEW = "gemini-3-flash-preview"
    GEMINI_3_1_FLASH_LITE_PREVIEW = "gemini-3.1-flash-lite-preview"
    CLAUDE_SONNET_4_5 = "claude-sonnet-4-5"
    CLAUDE_SONNET_4_6 = "claude-sonnet-4-6"
    CLAUDE_SONNET_5 = "claude-sonnet-5"
    CLAUDE_HAIKU_4_5 = "claude-haiku-4-5"
    CLAUDE_OPUS_4_6 = "claude-opus-4-6"
    CLAUDE_OPUS_4_8 = "claude-opus-4-8"
