from enum import Enum
from typing import Any, Literal
from llm_tracekit.types.base import SpanAttributeGeneratingType
from pydantic import BaseModel


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class _BaseMessage(BaseModel):
    role: MessageRole


class SystemMessage(_BaseMessage):
    role: Literal[MessageRole.SYSTEM] = MessageRole.SYSTEM
    # TODO: support multipart
    content: str


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



class CompletionRequest(SpanAttributeGeneratingType):

    messages: list[Message]

    def generate_span_attributes(self) -> dict[str, Any]:
        return {
            **super().generate_span_attributes(),

        }