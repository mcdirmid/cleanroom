# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 2f12ff4aedff
# GROUNDING_QA_AUDIT: 2026-10-05T04:28:01Z
# --- END CLEANROOM METADATA ---

"""Loop conversation grounding specification module."""

from __future__ import annotations
from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Sequence
from support.lib.grounding_support import InTier, AgentSessionTier
from parts.sandbox.grounding import tool_provider

ToolCallId = NewType("ToolCallId", str)
MessageRole = NewType("MessageRole", str)
ConversationContent = NewType("ConversationContent", str)
SerializedArguments = NewType("SerializedArguments", str)


@dataclass(frozen=True)
class ConversationMessage:
    """An entry in an agent conversation.

    COVERED:
    - Encapsulates role, content, correlation identifiers, and suppression stub state.
    """

    role: MessageRole
    content: ConversationContent
    tool_call_id: Optional[ToolCallId] = None
    tool_name: Optional[tool_provider.ToolName] = None
    reminder: Optional[tool_provider.ToolReminder] = None
    tool_arguments: Optional[SerializedArguments] = None
    is_stub: bool = False


@dataclass(frozen=True)
class ModelRequest:
    """Formatted sequence of messages prepared for language model transmission.

    COVERED:
    - Encapsulates sequence of conversation messages.
    """

    messages: Sequence[ConversationMessage]


class Conversation(InTier[AgentSessionTier], Protocol):
    """Session service maintaining chronological messages and stubbing superseded results."""

    def initialize(self, initial_messages: Sequence[ConversationMessage]) -> None:
        """
        DEFERRED:
        - MUST initialize conversation history with task instructions.
          - Deferred to refining implementation in openai_conversation_impl.py.
        """
        raise NotImplementedError

    def append_message(self, message: ConversationMessage) -> None:
        """
        DEFERRED:
        - MUST append the message to the conversation.
          - Deferred to refining implementation in openai_conversation_impl.py.
        """
        raise NotImplementedError

    def append_tool_response(
        self,
        tool_response: tool_provider.ToolResponse,
        tool_call_id: ToolCallId,
        tool_name: tool_provider.ToolName,
        tool_arguments: SerializedArguments,
    ) -> None:
        """
        DEFERRED:
        - MUST append the tool response to the conversation.
        - MUST stub previous responses and correlating arguments matching suppression keys.
          - Deferred to refining implementation in openai_conversation_impl.py.
        """
        raise NotImplementedError

    def get_model_request(self) -> ModelRequest:
        """
        COVERED:
        - MUST return a formatted model request for language model transmission.
          - Consequent knowledge: construct ModelRequest with representative ConversationMessage.

        DEFERRED:
        - History formatting and prompt construction deferred to openai_conversation_impl.py.
        """
        sample_msg = ConversationMessage(
            role=MessageRole("user"),
            content=ConversationContent("hello"),
        )
        _req = ModelRequest(messages=[sample_msg])
        raise NotImplementedError
