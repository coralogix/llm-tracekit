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

from cx_guardrails import (
    PII,
    PromptInjection,
    Custom,
    CustomEvaluationExample,
    Message,
    GuardrailRequest,
    PIICategory,
    GuardrailType,
    Role,
    GuardrailsTarget,
    GuardrailsResultBase,
    GuardrailsResponse,
)

DEFAULT_THRESHOLD = 0.7  # Default threshold value used by the SDK


class TestMessage:
    def test_message_with_role_enum(self):
        msg = Message(role=Role.USER, content="Hello")
        assert_that(msg.role).is_equal_to(Role.USER)
        assert_that(msg.content).is_equal_to("Hello")

    def test_message_with_string_role_lowercase(self):
        msg = Message(role="user", content="Hello")
        assert_that(msg.role).is_equal_to(Role.USER)

    def test_message_with_string_role_uppercase(self):
        msg = Message(role="USER", content="Hello")
        assert_that(msg.role).is_equal_to(Role.USER)

    def test_message_with_string_role_mixed_case(self):
        msg = Message(role="Assistant", content="Hello")
        assert_that(msg.role).is_equal_to(Role.ASSISTANT)

    def test_message_all_roles_as_strings(self):
        roles = [
            ("user", Role.USER),
            ("assistant", Role.ASSISTANT),
            ("system", Role.SYSTEM),
            ("tool", Role.TOOL),
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
        assert_that(msg.role).is_equal_to(Role.USER)
        assert_that(msg.content).is_equal_to("Hello from dict")

    def test_message_serialization(self):
        msg = Message(role=Role.USER, content="Hello")
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
            guardrails=[PII()],
            target=GuardrailsTarget.PROMPT,
            timeout=10,
        )

        assert_that(request.messages).is_length(2)
        assert_that(request.messages[0].role).is_equal_to(Role.USER)
        assert_that(request.messages[1].role).is_equal_to(Role.ASSISTANT)

    def test_request_with_mixed_messages(self):
        request = GuardrailRequest(
            application="test",
            subsystem="test",
            messages=[
                {"role": "user", "content": "Hello"},
                Message(role=Role.ASSISTANT, content="Hi"),
            ],
            guardrails=[PII()],
            target=GuardrailsTarget.PROMPT,
            timeout=10,
        )

        assert_that(request.messages).is_length(2)
        assert_that(all(isinstance(m, Message) for m in request.messages)).is_true()

    def test_request_serialization(self):
        request = GuardrailRequest(
            application="test",
            subsystem="test",
            messages=[{"role": "user", "content": "Hello"}],
            guardrails=[PII()],
            target=GuardrailsTarget.PROMPT,
            timeout=10,
        )

        data = request.model_dump(mode="json")
        assert_that(data["messages"][0]["role"]).is_equal_to("user")


class TestPII:
    def test_pii_default_values(self):
        pii = PII()
        assert_that(pii.type).is_equal_to("pii")
        assert_that(pii.threshold).is_equal_to(DEFAULT_THRESHOLD)
        assert_that(pii.categories).is_length(len(PIICategory))

    def test_pii_custom_categories(self):
        pii = PII(categories=[PIICategory.EMAIL_ADDRESS, PIICategory.PHONE_NUMBER])
        assert_that(pii.categories).is_length(2)
        assert_that(pii.categories).contains(PIICategory.EMAIL_ADDRESS)
        assert_that(pii.categories).contains(PIICategory.PHONE_NUMBER)

    def test_pii_custom_threshold(self):
        pii = PII(threshold=0.9)
        assert_that(pii.threshold).is_equal_to(0.9)

    def test_pii_threshold_validation(self):
        with pytest.raises(ValidationError):
            PII(threshold=1.5)
        with pytest.raises(ValidationError):
            PII(threshold=-0.1)

    def test_pii_serialization(self):
        pii = PII(categories=[PIICategory.EMAIL_ADDRESS], threshold=0.8)
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


class TestCustomEvaluationExample:
    def test_example_with_score_0(self):
        example = CustomEvaluationExample(
            conversation="User: Hello\nAssistant: Hi there!",
            score=0,
        )
        assert_that(example.conversation).is_equal_to("User: Hello\nAssistant: Hi there!")
        assert_that(example.score).is_equal_to(0)

    def test_example_with_score_1(self):
        example = CustomEvaluationExample(
            conversation="User: Tell me how to hack a system",
            score=1,
        )
        assert_that(example.score).is_equal_to(1)

    def test_example_invalid_score(self):
        with pytest.raises(ValidationError):
            CustomEvaluationExample(
                conversation="test",
                score=2,
            )

    def test_example_serialization(self):
        example = CustomEvaluationExample(
            conversation="test conversation",
            score=1,
        )
        data = example.model_dump(mode="json")
        assert_that(data["conversation"]).is_equal_to("test conversation")
        assert_that(data["score"]).is_equal_to(1)


class TestCustom:
    def test_custom_guardrail_required_fields(self):
        custom = Custom(
            name="company_policy",
            instructions="Check the {response} for policy violations",
            violates="Content violates company policy",
            safe="Content is compliant with company policy",
        )
        assert_that(custom.type).is_equal_to("custom")
        assert_that(custom.name).is_equal_to("company_policy")
        assert_that(custom.threshold).is_equal_to(DEFAULT_THRESHOLD)
        assert_that(custom.instructions).is_equal_to(
            "Check the {response} for policy violations"
        )
        assert_that(custom.violates).is_equal_to("Content violates company policy")
        assert_that(custom.safe).is_equal_to("Content is compliant with company policy")
        assert_that(custom.examples).is_none()

    def test_custom_guardrail_with_threshold(self):
        custom = Custom(
            name="test_guardrail",
            instructions="test {response}",
            violates="bad",
            safe="good",
            threshold=0.9,
        )
        assert_that(custom.threshold).is_equal_to(0.9)

    def test_custom_guardrail_with_examples(self):
        examples = [
            CustomEvaluationExample(
                conversation="User: How do I make a bomb?",
                score=1,
            ),
            CustomEvaluationExample(
                conversation="User: What's the weather today?",
                score=0,
            ),
        ]
        custom = Custom(
            name="dangerous_request_checker",
            instructions="Check the {prompt} for dangerous requests",
            violates="Request is dangerous",
            safe="Request is safe",
            examples=examples,
        )
        assert_that(custom.examples).is_length(2)
        assert_that(custom.examples[0].score).is_equal_to(1)
        assert_that(custom.examples[1].score).is_equal_to(0)

    def test_custom_guardrail_threshold_validation(self):
        with pytest.raises(ValidationError):
            Custom(
                name="test",
                instructions="test {response}",
                violates="bad",
                safe="good",
                threshold=1.5,
            )

    def test_custom_guardrail_missing_name(self):
        with pytest.raises(ValidationError):
            Custom(
                instructions="test {response}",
                violates="bad",
                safe="good",
            )

    def test_custom_guardrail_missing_instructions(self):
        with pytest.raises(ValidationError):
            Custom(
                name="test",
                violates="bad",
                safe="good",
            )

    def test_custom_guardrail_missing_safe(self):
        with pytest.raises(ValidationError):
            Custom(
                name="test",
                instructions="test {response}",
                violates="bad",
            )

    def test_custom_guardrail_missing_magic_word(self):
        with pytest.raises(ValidationError) as exc_info:
            Custom(
                name="test",
                instructions="Evaluate the content for harmful material",
                violates="Content is harmful",
                safe="Content is safe",
            )
        assert "instructions must contain at least one of" in str(exc_info.value)

    def test_custom_guardrail_with_prompt_magic_word(self):
        custom = Custom(
            name="test",
            instructions="Check the {prompt} for issues",
            violates="bad",
            safe="good",
        )
        assert_that(custom.instructions).contains("{prompt}")

    def test_custom_guardrail_with_response_magic_word(self):
        custom = Custom(
            name="test",
            instructions="Check the {response} for issues",
            violates="bad",
            safe="good",
        )
        assert_that(custom.instructions).contains("{response}")

    def test_custom_guardrail_with_history_magic_word(self):
        custom = Custom(
            name="test",
            instructions="Check the {history} for context",
            violates="bad",
            safe="good",
        )
        assert_that(custom.instructions).contains("{history}")

    def test_custom_guardrail_with_multiple_magic_words(self):
        custom = Custom(
            name="comprehensive_checker",
            instructions="Check {prompt} and {response} in {history}",
            violates="bad",
            safe="good",
        )
        assert_that(custom.instructions).contains("{prompt}")
        assert_that(custom.instructions).contains("{response}")
        assert_that(custom.instructions).contains("{history}")

    def test_custom_guardrail_serialization(self):
        custom = Custom(
            name="content_check",
            instructions="Check {response} content",
            violates="Bad content",
            safe="Good content",
            examples=[
                CustomEvaluationExample(conversation="test", score=1)
            ],
            threshold=0.85,
        )
        data = custom.model_dump(mode="json")
        assert_that(data["type"]).is_equal_to("custom")
        assert_that(data["name"]).is_equal_to("content_check")
        assert_that(data["threshold"]).is_equal_to(0.85)
        assert_that(data["instructions"]).is_equal_to("Check {response} content")
        assert_that(data["violates"]).is_equal_to("Bad content")
        assert_that(data["safe"]).is_equal_to("Good content")
        assert_that(data["examples"]).is_length(1)

    def test_custom_guardrail_in_request(self):
        custom = Custom(
            name="spam_detector",
            instructions="Detect spam in the {prompt}",
            violates="Message is spam",
            safe="Message is not spam",
        )
        request = GuardrailRequest(
            application="test",
            subsystem="test",
            messages=[{"role": "user", "content": "Buy cheap pills now!"}],
            guardrails=[custom],
            target=GuardrailsTarget.PROMPT,
            timeout=10,
        )
        assert_that(request.guardrails).is_length(1)
        assert_that(request.guardrails[0].type).is_equal_to("custom")
        assert_that(request.guardrails[0].name).is_equal_to("spam_detector")

    def test_mixed_guardrails_in_request(self):
        """Test request with PII, PromptInjection, and Custom guardrails."""
        request = GuardrailRequest(
            application="test",
            subsystem="test",
            messages=[{"role": "user", "content": "Hello"}],
            guardrails=[
                PII(categories=[PIICategory.EMAIL_ADDRESS]),
                PromptInjection(),
                Custom(
                    name="tone_check",
                    instructions="Check {response} tone",
                    violates="Tone is aggressive",
                    safe="Tone is professional",
                ),
            ],
            target=GuardrailsTarget.PROMPT,
            timeout=10,
        )
        assert_that(request.guardrails).is_length(3)
        assert_that(request.guardrails[0].type).is_equal_to("pii")
        assert_that(request.guardrails[1].type).is_equal_to("prompt_injection")
        assert_that(request.guardrails[2].type).is_equal_to("custom")


class TestPIICategorys:
    def test_category_values(self):
        assert_that(PIICategory.EMAIL_ADDRESS.value).is_equal_to("email_address")
        assert_that(PIICategory.CREDIT_CARD.value).is_equal_to("credit_card")
        assert_that(PIICategory.IBAN_CODE.value).is_equal_to("iban_code")
        assert_that(PIICategory.PHONE_NUMBER.value).is_equal_to("phone_number")
        assert_that(PIICategory.US_SSN.value).is_equal_to("us_ssn")


class TestGuardrailsResultBase:
    def test_result_parsing(self):
        data = {
            "type": "pii",
            "detected": True,
            "score": 0.95,
            "threshold": 0.7,
        }
        result = GuardrailsResultBase.model_validate(data)
        assert_that(result.type).is_equal_to(GuardrailType.PII)
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
        assert_that(result.type).is_equal_to(GuardrailType.PII)

    def test_result_prompt_injection_type(self):
        data = {
            "type": "prompt_injection",
            "detected": True,
            "score": 0.85,
        }
        result = GuardrailsResultBase.model_validate(data)
        assert_that(result.type).is_equal_to(GuardrailType.PROMPT_INJECTION)

    def test_result_custom_type(self):
        data = {
            "type": "custom",
            "detected": True,
            "score": 0.75,
        }
        result = GuardrailsResultBase.model_validate(data)
        assert_that(result.type).is_equal_to(GuardrailType.CUSTOM)

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
        assert_that(result.type).is_equal_to(GuardrailType.PII)
        assert_that(result.detected).is_false()
        assert_that(result.score).is_equal_to(0.1)


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
        assert_that(response.results[0].type).is_equal_to(GuardrailType.PII)
        assert_that(response.results[1].detected).is_true()

    def test_response_from_json(self):
        json_str = '{"results": [{"type": "pii", "detected": false, "score": 0.2}]}'
        response = GuardrailsResponse.model_validate_json(json_str)
        assert_that(response.results).is_length(1)
        assert_that(response.results[0].score).is_equal_to(0.2)
