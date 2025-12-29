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

from typing import Final

LABEL: Final = ("guardrails.{target}.{guardrail_type}.label")
"""
The label of the guardrail from guardrail response.
"""

NAME: Final = ("guardrails.{target}.{guardrail_type}.name")
"""
The name of the guardrail from guardrail response.
"""

SCORE: Final = ("guardrails.{target}.{guardrail_type}.score")
"""
The score of the guardrail from guardrail response.
"""

EXPLANATION: Final = ("guardrails.{target}.{guardrail_type}.explanation")
"""
The explanation of the guardrail result from guardrail response.
"""

DETECTION_THRESHOLD: Final = ("guardrails.{target}.{guardrail_type}.detection_threshold")
"""
The threshold of the guardrail.
"""

CUSTOM_GUARDRAIL_NAME: Final = ("guardrails.{target}.{guardrail_type}.name")
"""
The custom guardrail spesific name.
"""

PROMPT: Final = ("guardrails.prompt")
"""
The evaluated prompt.
"""

RESPONSE: Final = ("guardrails.response")
"""
The valuated response.
"""

APPLICATION_NAME: Final = ("cx.application.name")
"""
The application name.
"""

SUBSYSTEM_NAME: Final = ("cx.subsystem.name")
"""
The subsystem name.
"""

