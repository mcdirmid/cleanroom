"""Agent driver interface and data types."""

from dataclasses import dataclass
from typing import Optional, Protocol
from . import agent_conversation
from update_with_ai.parts.sandbox.lib import tool_provider


@dataclass(frozen=True)
class AgentOutcome:
    is_success: bool
    response: tool_provider.Response
    conversation: agent_conversation.Conversation

    def __init__(
        self,
        is_success: bool,
        response: tool_provider.Response,
        conversation: Optional[agent_conversation.Conversation] = None,
        conversation_history: Optional[agent_conversation.Conversation] = None,
    ) -> None:
        conv = conversation if conversation is not None else conversation_history
        if conv is None:
            raise TypeError("AgentOutcome missing required conversation argument")
        object.__setattr__(self, "is_success", is_success)
        object.__setattr__(self, "response", response)
        object.__setattr__(self, "conversation", conv)

    @property
    def conversation_history(self) -> agent_conversation.Conversation:
        return self.conversation


class AgentDriver(Protocol):
    def run(self) -> AgentOutcome: ...
