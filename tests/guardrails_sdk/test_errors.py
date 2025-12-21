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

from guardrails_sdk.error import (
    GuardrailsError,
    GuardrailsAPIConnectionError,
    GuardrailsAPITimeoutError,
    GuardrailsAPIResponseError,
    GuardrailTriggered,
)


class TestGuardrailsError:
    def test_base_error(self):
        error = GuardrailsError("test error")
        assert_that(str(error)).is_equal_to("test error")
        assert_that(error).is_instance_of(Exception)


class TestGuardrailsAPIConnectionError:
    def test_connection_error(self):
        error = GuardrailsAPIConnectionError("Failed to connect")
        assert_that(str(error)).is_equal_to("Failed to connect")
        assert_that(error).is_instance_of(GuardrailsError)


class TestGuardrailsAPITimeoutError:
    def test_timeout_error(self):
        error = GuardrailsAPITimeoutError("Request timed out")
        assert_that(str(error)).is_equal_to("Request timed out")
        assert_that(error).is_instance_of(GuardrailsError)


class TestGuardrailsAPIResponseError:
    def test_response_error_basic(self):
        error = GuardrailsAPIResponseError(status_code=500)
        assert_that(error.status_code).is_equal_to(500)
        assert_that(error.body).is_none()
        assert_that(error.message).is_equal_to("HTTP 500")
        assert_that(error).is_instance_of(GuardrailsError)

    def test_response_error_with_body(self):
        error = GuardrailsAPIResponseError(status_code=400, body="Bad request")
        assert_that(error.status_code).is_equal_to(400)
        assert_that(error.body).is_equal_to("Bad request")

    def test_response_error_with_message(self):
        error = GuardrailsAPIResponseError(
            status_code=404, 
            body="Not found", 
            message="Resource not found"
        )
        assert_that(error.status_code).is_equal_to(404)
        assert_that(error.message).is_equal_to("Resource not found")


class TestGuardrailTriggered:
    def test_basic_triggered(self):
        error = GuardrailTriggered(guardrail_type="pii")
        assert_that(error.guardrail_type).is_equal_to("pii")
        assert_that(error.name).is_none()
        assert_that(error.score).is_none()
        assert_that(error.explanation).is_none()
        assert_that(error.detected_categories).is_none()
        assert_that(str(error)).contains("Guardrail triggered: pii")

    def test_triggered_with_all_fields(self):
        error = GuardrailTriggered(
            guardrail_type="pii",
            name="PII Detection",
            score=0.95,
            explanation="Email address detected",
            detected_categories=["email", "phone"],
        )
        assert_that(error.guardrail_type).is_equal_to("pii")
        assert_that(error.name).is_equal_to("PII Detection")
        assert_that(error.score).is_equal_to(0.95)
        assert_that(error.explanation).is_equal_to("Email address detected")
        assert_that(error.detected_categories).is_equal_to(["email", "phone"])

    def test_triggered_message_format(self):
        error = GuardrailTriggered(
            guardrail_type="pii",
            name="PII Detection",
            score=0.95,
            explanation="Email detected",
            detected_categories=["email"],
        )
        message = str(error)
        assert_that(message).contains("Guardrail triggered: pii")
        assert_that(message).contains("name='PII Detection'")
        assert_that(message).contains("score=0.950")
        assert_that(message).contains("explanation='Email detected'")
        assert_that(message).contains("detected_categories=['email']")

    def test_triggered_custom_message(self):
        error = GuardrailTriggered(
            guardrail_type="pii",
            message="Custom error message",
        )
        assert_that(str(error)).is_equal_to("Custom error message")

    def test_triggered_prompt_injection(self):
        error = GuardrailTriggered(
            guardrail_type="prompt_injection",
            score=0.88,
            explanation="Jailbreak attempt detected",
        )
        assert_that(error.guardrail_type).is_equal_to("prompt_injection")
        assert_that(str(error)).contains("prompt_injection")
        assert_that(str(error)).contains("0.880")

    def test_triggered_is_guardrails_error(self):
        error = GuardrailTriggered(guardrail_type="pii")
        assert_that(error).is_instance_of(GuardrailsError)

    def test_triggered_can_be_caught_as_exception(self):
        with pytest.raises(GuardrailTriggered) as exc_info:
            raise GuardrailTriggered(
                guardrail_type="pii",
                score=0.9,
                detected_categories=["email"],
            )
        assert_that(exc_info.value.guardrail_type).is_equal_to("pii")
        assert_that(exc_info.value.score).is_equal_to(0.9)
        assert_that(exc_info.value.detected_categories).is_equal_to(["email"])

    def test_triggered_can_be_caught_as_guardrails_error(self):
        with pytest.raises(GuardrailsError):
            raise GuardrailTriggered(guardrail_type="pii")
