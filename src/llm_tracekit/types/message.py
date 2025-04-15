from abc import ABC
from enum import Enum
from typing import Any, Literal, Annotated
from llm_tracekit.types.base import SpanAttributeGeneratingType
from pydantic import BaseModel, Field

from opentelemetry.semconv._incubating.attributes import (
    gen_ai_attributes as GenAIAttributes,
)
from llm_tracekit import extended_gen_ai_attributes as ExtendedGenAIAttributes


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class _BaseMessage(ABC, BaseModel):
    role: MessageRole

    def generate_message_metadata_span_attributes(self, message_index: int) -> dict[str, Any]:
        return {}

    def generate_message_content_span_attributes(self, message_index: int) -> dict[str, Any]:
        return {}


class SystemMessage(_BaseMessage):
    role: Literal[MessageRole.SYSTEM] = MessageRole.SYSTEM
    content: str

    def generate_message_span_attributes(self, message_index: int, capture_content: bool) -> dict[str, Any]:
        return {
            ExtendedGenAIAttributes.GEN_AI_PROMPT_ROLE.format(prompt_index=message_index): self.role.value,
        }
    
    def generate_message_content_span_attributes(self, message_index: int) -> dict[str, Any]:
        return {
            ExtendedGenAIAttributes.GEN_AI_PROMPT_CONTENT.format(prompt_index=message_index): self.content,
        }


class UserMessage(_BaseMessage):
    role: Literal[MessageRole.USER] = MessageRole.USER
    # TODO: support multipart
    content: str


class AssistantMessage(_BaseMessage):
    role: Literal[MessageRole.SYSTEM] = MessageRole.SYSTEM
    # TODO: support multipart
    content: str


class ToolMessage(_BaseMessage):
    role: Literal[MessageRole.SYSTEM] = MessageRole.SYSTEM
    # TODO: support multipart
    content: str


# TODO: this might be a bad idea, if we get an invalid role for example, do we still want to report the span?
Message = Annotated[
    SystemMessage | UserMessage | AssistantMessage | ToolMessage,
    Field(discriminator="role")
]