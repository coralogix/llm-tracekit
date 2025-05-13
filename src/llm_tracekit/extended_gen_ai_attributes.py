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

GEN_AI_OPENAI_REQUEST_USER: Final = "gen_ai.openai.request.user"
"""
The user of the request.
"""

GEN_AI_OPENAI_REQUEST_TOOLS_TYPE: Final = (
    "gen_ai.openai.request.tools.{tool_index}.type"
)
"""
The type of the tool. Expected to be `function`.
"""

GEN_AI_OPENAI_REQUEST_TOOLS_FUNCTION_NAME: Final = (
    "gen_ai.openai.request.tools.{tool_index}.function.name"
)
"""
The name of the tool function.
"""

GEN_AI_OPENAI_REQUEST_TOOLS_FUNCTION_DESCRIPTION: Final = (
    "gen_ai.openai.request.tools.{tool_index}.function.description"
)
"""
The description of the tool function.
"""

GEN_AI_OPENAI_REQUEST_TOOLS_FUNCTION_PARAMETERS: Final = (
    "gen_ai.openai.request.tools.{tool_index}.function.parameters"
)
"""
The parameters of the tool function in JSON format.
"""

GEN_AI_BEDROCK_AGENT_ALIAS_ID: Final = "gen_ai.bedrock.agent_alias.id"
"""
The ID of the Bedrock agent alias.
"""
GEN_AI_BEDROCK_REQUEST_TOOLS_FUNCTION_NAME: Final = (
    "gen_ai.bedrock.request.tools.{tool_index}.function.name"
)
"""
The name of the tool function.
"""

GEN_AI_BEDROCK_REQUEST_TOOLS_FUNCTION_DESCRIPTION: Final = (
    "gen_ai.bedrock.request.tools.{tool_index}.function.description"
)
"""
The description of the tool function.
"""

GEN_AI_BEDROCK_REQUEST_TOOLS_FUNCTION_PARAMETERS: Final = (
    "gen_ai.bedrock.request.tools.{tool_index}.function.parameters"
)
"""
The parameters of the tool function in JSON format.
"""

GEN_AI_PROMPT_ROLE: Final = "gen_ai.prompt.{prompt_index}.role"
"""
The role of the prompt.
"""

GEN_AI_PROMPT_CONTENT: Final = "gen_ai.prompt.{prompt_index}.content"
"""
The content of the prompt.
Only captured if OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT is set to `true`.
"""

GEN_AI_PROMPT_TOOL_CALL_ID: Final = "gen_ai.prompt.{prompt_index}.tool_call_id"
"""
The id of the tool call.
"""

GEN_AI_PROMPT_TOOL_CALLS_ID: Final = (
    "gen_ai.prompt.{prompt_index}.tool_calls.{tool_call_index}.id"
)
"""
The id of the tool call.
"""

GEN_AI_PROMPT_TOOL_CALLS_TYPE: Final = (
    "gen_ai.prompt.{prompt_index}.tool_calls.{tool_call_index}.type"
)
"""
The type of the tool call. Expected to be `function`.
"""

GEN_AI_PROMPT_TOOL_CALLS_FUNCTION_NAME: Final = (
    "gen_ai.prompt.{prompt_index}.tool_calls.{tool_call_index}.function.name"
)
"""
The name of the tool function.
"""

GEN_AI_PROMPT_TOOL_CALLS_FUNCTION_ARGUMENTS: Final = (
    "gen_ai.prompt.{prompt_index}.tool_calls.{tool_call_index}.function.arguments"
)
"""
The arguments of the tool function in JSON format.
Only captured if OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT is set to `true`.
"""

GEN_AI_COMPLETION_ROLE: Final = "gen_ai.completion.{completion_index}.role"
"""
The role of the completion.
"""

GEN_AI_COMPLETION_FINISH_REASON: Final = (
    "gen_ai.completion.{completion_index}.finish_reason"
)
"""
The finish reason of the completion.
"""

GEN_AI_COMPLETION_CONTENT: Final = "gen_ai.completion.{completion_index}.content"
"""
The content of the completion. 
Only captured if OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT is set to `true`.
"""

GEN_AI_COMPLETION_TOOL_CALLS_ID: Final = (
    "gen_ai.completion.{completion_index}.tool_calls.{tool_call_index}.id"
)
"""
The id of the tool call.
"""

GEN_AI_COMPLETION_TOOL_CALLS_TYPE: Final = (
    "gen_ai.completion.{completion_index}.tool_calls.{tool_call_index}.type"
)
"""
The type of the tool call. Expected to be `function`.
"""

GEN_AI_COMPLETION_TOOL_CALLS_FUNCTION_NAME: Final = (
    "gen_ai.completion.{completion_index}.tool_calls.{tool_call_index}.function.name"
)
"""
The name of the tool function.
"""

GEN_AI_COMPLETION_TOOL_CALLS_FUNCTION_ARGUMENTS: Final = "gen_ai.completion.{completion_index}.tool_calls.{tool_call_index}.function.arguments"
"""
The arguments of the tool function in JSON format.
Only captured if OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT is set to `true`.
"""
