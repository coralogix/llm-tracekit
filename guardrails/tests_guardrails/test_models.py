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

from guardrails.models.request import (
    PII,
    PromptInjection,
    Message,
    GuardrailRequest,
)
from guardrails.models.constants import DEFAULT_THRESHOLD
from guardrails.models.enums import PIICategorie, GuardrailType, Role, GuardrailsTarget
from guardrails.models.response import GuardrailsResultBase, GuardrailsResponse


class TestMessage:
    def test_message_with_role_enum(self):
        msg = Message(role=Role.User, content="Hello")
        assert_that(msg.role).is_equal_to(Role.User)
        assert_that(msg.content).is_equal_to("Hello")

    def test_message_with_string_role_lowercase(self):
        msg = Message(role="user", content="Hello")
        assert_that(msg.role).is_equal_to(Role.User)

    def test_message_with_string_role_uppercase(self):
        msg = Message(role="USER", content="Hello")
        assert_that(msg.role).is_equal_to(Role.User)

    def test_message_with_string_role_mixed_case(self):
        msg = Message(role="Assistant", content="Hello")
        assert_that(msg.role).is_equal_to(Role.Assistant)

    def test_message_all_roles_as_strings(self):
        roles = [
            ("user", Role.User),
            ("assistant", Role.Assistant),
            ("system", Role.System),
            ("tool", Role.Tool),
        ]
        for string_role, expected_enum in roles:
            msg = Message(role=string_role, content="test")
            assert_that(msg.role).is_equal_to(expected_enum)

    def test_message_invalid_role_string(self):
        with pytest.raises(ValidationError):
            Message(role="invalid_role", content="Hello")

    def test_message_from_dict(self):
        data = {"role": "user", "content": "Hello from dict"}
        msg = Message(**data)
        assert_that(msg.role).is_equal_to(Role.User)
        assert_that(msg.content).is_equal_to("Hello from dict")

    def test_message_serialization(self):
        msg = Message(role=Role.User, content="Hello")
        data = msg.model_dump(mode="json")
        assert_that(data["role"]).is_equal_to("user")
        assert_that(data["content"]).is_equal_to("Hello")

class TestGuardrailRequest:
    def test_request_with_dict_messages(self):
        request = GuardrailRequest(
            application="test",
            subsystem="test",
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
            ],
            guardrails_configs=[PII()],
            target=GuardrailsTarget.prompt,
            timeout=10,
        )
        
        assert_that(request.messages).is_length(2)
        assert_that(request.messages[0].role).is_equal_to(Role.User)
        assert_that(request.messages[1].role).is_equal_to(Role.Assistant)

    def test_request_with_mixed_messages(self):
        request = GuardrailRequest(
            application="test",
            subsystem="test",
            messages=[
                {"role": "user", "content": "Hello"},
                Message(role=Role.Assistant, content="Hi"),
            ],
            guardrails_configs=[PII()],
            target=GuardrailsTarget.prompt,
            timeout=10,
        )
        
        assert_that(request.messages).is_length(2)
        assert_that(all(isinstance(m, Message) for m in request.messages)).is_true()

    def test_request_serialization(self):
        request = GuardrailRequest(
            application="test",
            subsystem="test",
            messages=[{"role": "user", "content": "Hello"}],
            guardrails_configs=[PII()],
            target=GuardrailsTarget.prompt,
            timeout=10,
        )
        
        data = request.model_dump(mode="json")
        assert_that(data["messages"][0]["role"]).is_equal_to("user")


class TestPII:
    def test_pii_default_values(self):
        pii = PII()
        assert_that(pii.type).is_equal_to("pii")
        assert_that(pii.threshold).is_equal_to(DEFAULT_THRESHOLD)
        assert_that(pii.categories).is_length(len(PIICategorie))

    def test_pii_custom_categories(self):
        pii = PII(categories=[PIICategorie.email_address, PIICategorie.phone_number])
        assert_that(pii.categories).is_length(2)
        assert_that(pii.categories).contains(PIICategorie.email_address)
        assert_that(pii.categories).contains(PIICategorie.phone_number)

    def test_pii_custom_threshold(self):
        pii = PII(threshold=0.9)
        assert_that(pii.threshold).is_equal_to(0.9)

    def test_pii_threshold_validation(self):
        with pytest.raises(ValidationError):
            PII(threshold=1.5)
        with pytest.raises(ValidationError):
            PII(threshold=-0.1)

    def test_pii_serialization(self):
        pii = PII(categories=[PIICategorie.email_address], threshold=0.8)
        data = pii.model_dump(mode="json")
        assert_that(data["type"]).is_equal_to("pii")
        assert_that(data["threshold"]).is_equal_to(0.8)
        assert_that(data["categories"]).is_equal_to(["email_address"])


class TestPromptInjection:
    def test_prompt_injection_default_values(self):
        pi = PromptInjection()
        assert_that(pi.type).is_equal_to("prompt_injection")
        assert_that(pi.threshold).is_equal_to(DEFAULT_THRESHOLD)

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
        assert_that(PIICategorie.email_address.value).is_equal_to("email_address")
        assert_that(PIICategorie.credit_card.value).is_equal_to("credit_card")


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
            GuardrailsResultBase.model_validate(
                {
                    "type": "pii",
                    "detected": False,
                    "score": 1.5,
                }
            )

    def test_result_optional_fields(self):
        data = {
            "type": "pii",
            "detected": False,
            "score": 0.1,
        }
        result = GuardrailsResultBase.model_validate(data)


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
