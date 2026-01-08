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

from cx_guardrails.error import (
    GuardrailsError,
    GuardrailsAPIConnectionError,
    GuardrailsAPITimeoutError,
    GuardrailsAPIResponseError,
    GuardrailViolation,
    GuardrailsTriggered,
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
        assert_that(error.message).is_equal_to(
            "Request failed with HTTP status_code=500"
        )
        assert_that(error).is_instance_of(GuardrailsError)

    def test_response_error_with_body(self):
        error = GuardrailsAPIResponseError(status_code=400, body="Bad request")
        assert_that(error.status_code).is_equal_to(400)
        assert_that(error.body).is_equal_to("Bad request")

    def test_response_error_with_message(self):
        error = GuardrailsAPIResponseError(
            status_code=404, body="Not found", message="Resource not found"
        )
        assert_that(error.status_code).is_equal_to(404)
        assert_that(error.message).is_equal_to("Resource not found")


class TestGuardrailViolation:
    def test_basic_violation(self):
        violation = GuardrailViolation(guardrail_type="pii")
        assert_that(violation.guardrail_type).is_equal_to("pii")
        assert_that(violation.name).is_none()
        assert_that(str(violation)).is_equal_to("pii")

    def test_violation_with_name(self):
        violation = GuardrailViolation(
            guardrail_type="pii",
            name="PII Detection",
        )
        assert_that(violation.guardrail_type).is_equal_to("pii")
        assert_that(violation.name).is_equal_to("PII Detection")

    def test_violation_message_format(self):
        violation = GuardrailViolation(
            guardrail_type="pii",
            name="PII Detection",
        )
        message = str(violation)
        assert_that(message).contains("pii")
        assert_that(message).contains("name='PII Detection'")

    def test_violation_prompt_injection(self):
        violation = GuardrailViolation(guardrail_type="prompt_injection")
        assert_that(violation.guardrail_type).is_equal_to("prompt_injection")
        assert_that(str(violation)).contains("prompt_injection")

    def test_violation_is_guardrails_error(self):
        violation = GuardrailViolation(guardrail_type="pii")
        assert_that(violation).is_instance_of(GuardrailsError)


class TestGuardrailsTriggered:
    def test_triggered_with_single_violation(self):
        violation = GuardrailViolation(guardrail_type="pii")
        error = GuardrailsTriggered([violation])
        assert_that(error.triggered).is_length(1)
        assert_that(error.triggered[0].guardrail_type).is_equal_to("pii")
        assert_that(str(error)).contains("1 guardrails triggered")

    def test_triggered_with_multiple_violations(self):
        violations = [
            GuardrailViolation(guardrail_type="pii"),
            GuardrailViolation(guardrail_type="prompt_injection"),
        ]
        error = GuardrailsTriggered(violations)
        assert_that(error.triggered).is_length(2)
        assert_that(str(error)).contains("2 guardrails triggered")

    def test_triggered_is_guardrails_error(self):
        violation = GuardrailViolation(guardrail_type="pii")
        error = GuardrailsTriggered([violation])
        assert_that(error).is_instance_of(GuardrailsError)

    def test_triggered_can_be_caught_as_exception(self):
        with pytest.raises(GuardrailsTriggered) as exc_info:
            raise GuardrailsTriggered([GuardrailViolation(guardrail_type="pii")])
        assert_that(exc_info.value.triggered).is_length(1)
        assert_that(exc_info.value.triggered[0].guardrail_type).is_equal_to("pii")

    def test_triggered_can_be_caught_as_guardrails_error(self):
        with pytest.raises(GuardrailsError):
            raise GuardrailsTriggered([GuardrailViolation(guardrail_type="pii")])
