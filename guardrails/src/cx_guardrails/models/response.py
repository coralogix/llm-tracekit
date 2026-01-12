from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._constants import DEFAULT_THRESHOLD
from ._models import GuardrailType


class GuardrailsResultBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: GuardrailType = Field(alias="type")
    detected: bool
    threshold: float = Field(default=DEFAULT_THRESHOLD, ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=1.0)

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.lower()
        return v


class PIIResult(GuardrailsResultBase):
    detected_categories: Any | None = None


class PromptInjectionResult(GuardrailsResultBase):
    pass


class TestPolicyResult(GuardrailsResultBase):
    pass


GuardrailsResponseType = PIIResult | PromptInjectionResult | TestPolicyResult


class GuardrailsResponse(BaseModel):
    results: list[GuardrailsResponseType] = Field(default_factory=list)
