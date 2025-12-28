from dataclasses import dataclass
from typing import Any, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from enum import Enum

GR_THRESHOLD = 0.7


class GuardrailsEndpoint(Enum):
    PROMPT_ENDPOINT = "guard_prompt"
    RESPONSE_ENDPOINT = "guard_response"


class PIICategories(Enum):
    email = "email"
    phone = "phone"
    user_name = "user_name"
    address = "address"
    credit_card = "credit_card"
    social_security_number = "social_security_number"
    passport = "passport"
    driver_license = "driver_license"

    @classmethod
    def values(cls):
        return [category.value for category in cls.__members__.values()]


class PromptInjectionCategories(Enum):
    change_personality = "change_personality"
    forget_instructions = "forget_instructions"
    illegal_topics = "illegal_topics"
    say_command = "say_command"
    instructions_leakage = "instructions_leakage"
    code_execution = "code_execution"
    contains_emojis = "contains_emojis"
    contains_encoding = "contains_encoding"
    prompt_repetition = "prompt_repetition"
    contains_gibberish = "contains_gibberish"

    @classmethod
    def values(cls):
        return [category.value for category in cls.__members__.values()]


class GuardrailType(Enum):
    pii = "pii"
    prompt_injection = "prompt_injection"
    custom = "custom"


class Labels(Enum):
    P1 = "P1"


class BaseGuardrailConfig(BaseModel):
    threshold: float = Field(default=GR_THRESHOLD, ge=0.0, le=1.0)


class PII(BaseGuardrailConfig):
    type: Literal["pii"] = "pii"
    categories: List[PIICategories] = Field(default_factory=lambda: list(PIICategories))


class PromptInjection(BaseGuardrailConfig):
    type: Literal["prompt_injection"] = "prompt_injection"


@dataclass
class CustomEvaluationExample:
    """An example for custom guardrail evaluation criteria.
    
    Attributes:
        history: The conversation history (previous turns). Can contain multiple
                 lines with user/assistant messages.
        response: The assistant response being evaluated.
        expected_result: The expected evaluation result (0 for SAFE, 1 for VIOLATES).
    """
    history: Optional[str]
    response: Optional[str]
    expected_result: Literal[0, 1]

    def __str__(self):
        parts = ["Content:"]
        if self.history:
            parts.append("History:")
            parts.append(self.history)
            parts.append("")
        if self.response:
            parts.append("Response:")
            parts.append(f"assistant: {self.response}")
            parts.append("")
        parts.append("Answer (0 or 1):")
        parts.append(str(self.expected_result))
        return "\n".join(parts)


class CustomEvaluationCriteria(BaseModel):
    """Evaluation criteria for a custom guardrail.
    
    Attributes:
        title: The title/header of the evaluation criteria.
        instructions: Instructions for evaluating the content.
        violates: Description of what constitutes a violation (label 1).
        safe: Description of what constitutes safe content (label 0).
        examples: Optional list of examples demonstrating the criteria.
    """
    title: str
    instructions: str
    violates: Optional[str] = None
    safe: Optional[str] = None
    examples: Optional[List[CustomEvaluationExample]] = None

    def __str__(self):
        parts = [f"# {self.title}", "", "## INSTRUCTIONS", "", self.instructions]
        if self.violates:
            parts.extend(["", "---", "", "## VIOLATES (1)", "", self.violates])
        if self.safe:
            parts.extend(["", "---", "", "## SAFE (0)", "", self.safe])
        if self.examples:
            parts.extend(["", "---", "", "## EXAMPLES", ""])
            for i, example in enumerate(self.examples):
                parts.append(str(example))
                if i < len(self.examples) - 1:
                    parts.extend(["", "---", ""])
        return "\n".join(parts)


class CustomGuardrail(BaseGuardrailConfig):
    """A custom guardrail configuration.
    
    Attributes:
        name: The name of the custom guardrail.
        evaluation_criteria: The evaluation criteria as a string or CustomEvaluationCriteria object.
                            If a CustomEvaluationCriteria is provided, it will be converted to string.
    """
    type: Literal["custom"] = "custom"
    name: str
    evaluation_criteria: str

    @field_validator("evaluation_criteria", mode="before")
    @classmethod
    def convert_criteria_to_string(cls, v: Any) -> str:
        if isinstance(v, str):
            return v
        if isinstance(v, CustomEvaluationCriteria):
            return str(v)
        raise ValueError(
            f"evaluation_criteria must be a string or CustomEvaluationCriteria instance, got {type(v).__name__}"
        )

class GuardrailsRequest(BaseModel):
    application: str
    subsystem: str
    prompt: Optional[str] = None
    response: Optional[str]
    guardrails_configs: List[PII | PromptInjection | CustomGuardrail]


class GuardrailsConfig(BaseModel):
    pii: Optional[PII] = None
    prompt_injection: Optional[PromptInjection] = None
    custom_guardrail: Optional[List[CustomGuardrail]] = Field(default_factory=list)

    def to_list(self) -> List:
        out = []
        if self.pii is not None:
            out.append(self.pii)
        if self.prompt_injection is not None:
            out.append(self.prompt_injection)
        if self.custom_guardrail:
            out.extend(self.custom_guardrail)
        return out


class GuardrailsResult(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True
    )  # Allow both 'type' and 'detection_type'
    detection_type: GuardrailType = Field(alias="type")
    detected_categories: Optional[Any] = None
    label: Optional[Labels] = None
    name: Optional[str] = None
    detected: bool
    score: float = Field(ge=0.0, le=1.0)
    explanation: Optional[str] = None
    config: Optional[Any] = None
    threshold: float = Field(default=GR_THRESHOLD, ge=0.0, le=1.0)

    @field_validator("detection_type", mode="before")
    @classmethod
    def normalize_type(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.lower()
        return v


class GuardrailsResponse(BaseModel):
    results: List[GuardrailsResult] = Field(default_factory=list)


class GuardrailsTarget(Enum):
    prompt = "prompt"
    response = "response"
