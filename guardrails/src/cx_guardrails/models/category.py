from enum import Enum


class GuardrailCategory(str, Enum):
    SECURITY = "security"
    QUALITY = "quality"
