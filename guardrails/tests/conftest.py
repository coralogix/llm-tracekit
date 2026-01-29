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

import os
import pytest


@pytest.fixture
def guardrails_env_vars():
    """Set up environment variables for guardrails configuration."""
    env_vars = {
        "CX_GUARDRAILS_TOKEN": "test-api-key",
        "CX_APPLICATION_NAME": "test-app",
        "CX_SUBSYSTEM_NAME": "test-subsystem",
        "CX_GUARDRAILS_ENDPOINT": "https://api.eu2.coralogix.com",
    }
    original_values = {}
    for key, value in env_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value

    yield env_vars

    for key, original_value in original_values.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


@pytest.fixture
def clear_guardrails_env_vars():
    """Clear all guardrails environment variables."""
    env_keys = [
        "CX_GUARDRAILS_TOKEN",
        "CX_APPLICATION_NAME",
        "CX_SUBSYSTEM_NAME",
        "CX_GUARDRAILS_ENDPOINT",
    ]
    original_values = {}
    for key in env_keys:
        original_values[key] = os.environ.pop(key, None)

    yield

    for key, original_value in original_values.items():
        if original_value is not None:
            os.environ[key] = original_value
