from enum import Enum, auto


class PIICategorie(Enum):
    phone_number = "phone_number"
    email_address = "email_address"
    credit_card = "credit_card"
    iban_code = "iban_code"
    us_ssn = "us_ssn"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]


class GuardrailType(Enum):
    pii = "pii"
    prompt_injection = "prompt_injection"
    custom = "custom"


class Label(Enum):
    P1 = "P1"


class GuardrailsTarget(Enum):
    prompt = "prompt"
    response = "response"


class Role(Enum):
    User = "user"
    Assistant = "assistant"
    System = "system"
    Tool = "tool"
