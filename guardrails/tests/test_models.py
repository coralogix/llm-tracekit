# Copyright Coralogix Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
from assertpy import assert_that
from pydantic import ValidationError

from guardrails.models import (
    PII,
    PromptInjection,
    PIICategories,
    GuardrailsResultBase,
    GuardrailsResponse,
    GuardrailType,
    GR_THRESHOLD,
)


class TestPII:
    def test_pii_default_values(self):
        pii = PII()
        assert_that(pii.type).is_equal_to("pii")
        assert_that(pii.threshold).is_equal_to(GR_THRESHOLD)
        assert_that(pii.categories).is_length(len(PIICategories))

    def test_pii_custom_categories(self):
        pii = PII(categories=[PIICategories.email, PIICategories.phone])
        assert_that(pii.categories).is_length(2)
        assert_that(pii.categories).contains(PIICategories.email)
        assert_that(pii.categories).contains(PIICategories.phone)

    def test_pii_custom_threshold(self):
        pii = PII(threshold=0.9)
        assert_that(pii.threshold).is_equal_to(0.9)

    def test_pii_threshold_validation(self):
        with pytest.raises(ValidationError):
            PII(threshold=1.5)
        with pytest.raises(ValidationError):
            PII(threshold=-0.1)

    def test_pii_serialization(self):
        pii = PII(categories=[PIICategories.email], threshold=0.8)
        data = pii.model_dump(mode="json")
        assert_that(data["type"]).is_equal_to("pii")
        assert_that(data["threshold"]).is_equal_to(0.8)
        assert_that(data["categories"]).is_equal_to(["email"])


class TestPromptInjection:
    def test_prompt_injection_default_values(self):
        pi = PromptInjection()
        assert_that(pi.type).is_equal_to("prompt_injection")
        assert_that(pi.threshold).is_equal_to(GR_THRESHOLD)

    def test_prompt_injection_custom_threshold(self):
        pi = PromptInjection(threshold=0.5)
        assert_that(pi.threshold).is_equal_to(0.5)

    def test_prompt_injection_threshold_validation(self):
        with pytest.raises(ValidationError):
            PromptInjection(threshold=2.0)

    def test_prompt_injection_serialization(self):
        pi = PromptInjection(threshold=0.8)
        data = pi.model_dump(mode="json")
        assert_that(data["type"]).is_equal_to("prompt_injection")
        assert_that(data["threshold"]).is_equal_to(0.8)


class TestPIICategories:

    def test_category_values(self):
        assert_that(PIICategories.email.value).is_equal_to("email")
        assert_that(PIICategories.credit_card.value).is_equal_to("credit_card")


class TestGuardrailsResultBase:
    def test_result_parsing(self):
        data = {
            "type": "pii",
            "detected": True,
            "score": 0.95,
            "threshold": 0.7,
        }
        result = GuardrailsResultBase.model_validate(data)
        assert_that(result.type).is_equal_to(GuardrailType.pii)
        assert_that(result.detected).is_true()
        assert_that(result.score).is_equal_to(0.95)

    def test_result_case_insensitive_type(self):
        """Test that type handles case variations from API."""
        data = {
            "type": "PII",
            "detected": False,
            "score": 0.1,
        }
        result = GuardrailsResultBase.model_validate(data)
        assert_that(result.type).is_equal_to(GuardrailType.pii)

    def test_result_prompt_injection_type(self):
        data = {
            "type": "prompt_injection",
            "detected": True,
            "score": 0.85,
        }
        result = GuardrailsResultBase.model_validate(data)
        assert_that(result.type).is_equal_to(GuardrailType.prompt_injection)

    def test_result_score_validation(self):
        with pytest.raises(ValidationError):
            GuardrailsResultBase.model_validate({
                "type": "pii",
                "detected": False,
                "score": 1.5,
            })

    def test_result_optional_fields(self):
        data = {
            "type": "pii",
            "detected": False,
            "score": 0.1,
        }
        result = GuardrailsResultBase.model_validate(data)
        assert_that(result.label).is_none()


class TestGuardrailsResponse:
    def test_empty_response(self):
        response = GuardrailsResponse(results=[])
        assert_that(response.results).is_empty()

    def test_response_with_results(self):
        data = {
            "results": [
                {"type": "pii", "detected": False, "score": 0.1},
                {"type": "prompt_injection", "detected": True, "score": 0.9},
            ]
        }
        response = GuardrailsResponse.model_validate(data)
        assert_that(response.results).is_length(2)
        assert_that(response.results[0].type).is_equal_to(GuardrailType.pii)
        assert_that(response.results[1].detected).is_true()

    def test_response_from_json(self):
        json_str = '{"results": [{"type": "pii", "detected": false, "score": 0.2}]}'
        response = GuardrailsResponse.model_validate_json(json_str)
        assert_that(response.results).is_length(1)
        assert_that(response.results[0].score).is_equal_to(0.2)
