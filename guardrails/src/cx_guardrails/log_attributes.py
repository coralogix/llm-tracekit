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

EVENT_NAME: Final = "event.name"
"""
The log record attribute identifying the kind of event being emitted.
"""

EVALUATION_RESULT_EVENT: Final = "gen_ai.evaluation.result"
"""
The event name for a guardrail evaluation result log record.
"""

EVALUATION_NAME: Final = "gen_ai.evaluation.name"
"""
The name of the evaluation -- the guardrail type, or the custom guardrail's name.
"""

EVALUATION_SCORE_VALUE: Final = "gen_ai.evaluation.score.value"
"""
The evaluation score.
"""

EVALUATION_SCORE_LABEL: Final = "gen_ai.evaluation.score.label"
"""
The evaluation score label (e.g. "p1"), when provided by the guardrails service.
"""

EVALUATION_TARGET: Final = "cx.evaluation.target"
"""
What was evaluated -- "prompt" or "response".
"""

EVALUATION_TRACE_ID: Final = "cx.evaluation.trace_id"
"""
The trace ID of the span the evaluation was performed on.
"""

EVALUATION_SPAN_ID: Final = "cx.evaluation.span_id"
"""
The span ID of the span the evaluation was performed on.
"""

EVALUATION_POLICY_TYPE: Final = "cx.evaluation.policy_type"
"""
The evaluation policy category -- "security" or "quality".
"""

EVALUATION_USER_ID: Final = "cx.evaluation.user_id"
"""
Optional end-user id, attached to the evaluation logs when provided.
"""

# Coralogix routes logs whose *resource* carries these integration attributes to
# the default/ai.evaluations dataset; record attributes alone are not enough.
INTEGRATION_SOURCE_TYPE_KEY: Final = "cx.integration.source.type"
"""
The resource attribute identifying the integration source type.
"""

INTEGRATION_SOURCE_TYPE_VALUE: Final = "ai_agent"
"""
The integration source type Coralogix expects for AI evaluation logs.
"""

INTEGRATION_SOURCE_VERSION_KEY: Final = "cx.integration.source.version"
"""
The resource attribute identifying the integration source version.
"""

INTEGRATION_SOURCE_VERSION_VALUE: Final = "1.0.0"
"""
The integration source version Coralogix expects for AI evaluation logs.
"""
