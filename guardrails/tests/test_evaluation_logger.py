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
from assertpy import assert_that, soft_assertions
from unittest.mock import patch

from opentelemetry._logs import NoOpLogger
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import NoOpTracerProvider

from cx_guardrails.evaluation_logger import get_evaluation_logger
from cx_guardrails.log_attributes import (
    INTEGRATION_SOURCE_TYPE_KEY,
    INTEGRATION_SOURCE_TYPE_VALUE,
    INTEGRATION_SOURCE_VERSION_KEY,
    INTEGRATION_SOURCE_VERSION_VALUE,
)


@pytest.fixture(autouse=True)
def clear_evaluation_logger_cache():
    get_evaluation_logger.cache_clear()
    yield
    get_evaluation_logger.cache_clear()


class TestGetEvaluationLogger:
    def test_returns_noop_logger_without_sdk_tracer_provider(self):
        with patch(
            "opentelemetry.trace.get_tracer_provider",
            return_value=NoOpTracerProvider(),
        ):
            assert_that(get_evaluation_logger()).is_instance_of(NoOpLogger)

    def test_returns_noop_logger_without_endpoint(self, monkeypatch):
        monkeypatch.delenv("CX_ENDPOINT", raising=False)
        tracer_provider = TracerProvider(
            resource=Resource.create({SERVICE_NAME: "my-service"})
        )
        with patch(
            "opentelemetry.trace.get_tracer_provider", return_value=tracer_provider
        ):
            assert_that(get_evaluation_logger()).is_instance_of(NoOpLogger)

    def test_logger_provider_resource_has_service_name_and_integration_attributes(
        self, monkeypatch
    ):
        monkeypatch.setenv("CX_ENDPOINT", "https://test.example.com")
        monkeypatch.setenv("CX_TOKEN", "test-token")
        tracer_provider = TracerProvider(
            resource=Resource.create({SERVICE_NAME: "my-service"})
        )
        with patch(
            "opentelemetry.trace.get_tracer_provider", return_value=tracer_provider
        ), patch(
            "cx_guardrails.evaluation_logger.LoggerProvider"
        ) as mock_logger_provider_class, patch(
            "cx_guardrails.evaluation_logger.setup_log_exporter"
        ) as mock_setup_log_exporter:
            get_evaluation_logger()

        resource_attributes = mock_logger_provider_class.call_args.kwargs[
            "resource"
        ].attributes
        exporter_config = mock_setup_log_exporter.call_args.args[1]
        with soft_assertions():
            assert_that(resource_attributes[SERVICE_NAME]).is_equal_to("my-service")
            assert_that(resource_attributes[INTEGRATION_SOURCE_TYPE_KEY]).is_equal_to(
                INTEGRATION_SOURCE_TYPE_VALUE
            )
            assert_that(
                resource_attributes[INTEGRATION_SOURCE_VERSION_KEY]
            ).is_equal_to(INTEGRATION_SOURCE_VERSION_VALUE)
            assert_that(exporter_config.endpoint).is_equal_to(
                "https://test.example.com"
            )
            assert_that(exporter_config.headers["authorization"]).is_equal_to(
                "Bearer test-token"
            )
