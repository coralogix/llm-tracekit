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

GUARDRAILS_TRIGGERED: Final = "guardrails.triggered"
"""
Boolean indicating a guardrail detected a violation or flagged content.
"""

SCORE: Final = "gen_ai.{target}.guardrails.{guardrail_type}.score"
"""
The guardrail response score.
"""

CUSTOM_GUARDRAIL_SCORE: Final = "gen_ai.{target}.guardrails.custom.{index}.score"
"""
The custom guardrail response score.
"""

THRESHOLD: Final = "gen_ai.{target}.guardrails.{guardrail_type}.threshold"
"""
The guardrail threshold.
"""

CUSTOM_GUARDRAIL_THRESHOLD: Final = "gen_ai.{target}.guardrails.custom.{index}.threshold"
"""
The custom guardrail threshold.
"""

TRIGGERED: Final = "gen_ai.{target}.guardrails.{guardrail_type}.triggered"
"""
Boolean indicating a specific guardrail detected a violation or flagged content.
"""

CUSTOM_GUARDRAIL_TRIGGERED: Final = "gen_ai.{target}.guardrails.custom.{index}.triggered"
"""
Boolean indicating a specific custom guardrail detected a violation or flagged content.
"""

CUSTOM_GUARDRAIL_NAME: Final = "gen_ai.{target}.guardrails.custom.{index}.name"
"""
The custom guardrail name.
"""

CUSTOM_GUARDRAIL_CATEGORY: Final = "gen_ai.{target}.guardrails.custom.{index}.category"
"""
The custom guardrail category (security or quality).
"""

PROMPT: Final = "guardrails.prompt.{index}"
"""
The evaluated prompt at index.
"""

RESPONSE: Final = "guardrails.response.{index}"
"""
The evaluated response at index.
"""

APPLICATION_NAME: Final = "cx.application.name"
"""
The application name.
"""

SUBSYSTEM_NAME: Final = "cx.subsystem.name"
"""
The subsystem name.
"""
