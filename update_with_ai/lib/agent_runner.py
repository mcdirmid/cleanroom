from typing import Protocol
from dataclasses import dataclass
from . import agent_conversation_history
from . import tool_provider

@dataclass(frozen=True)
class AgentOutcome:
    is_success: bool
    response: tool_provider.Response
    conversation_history: agent_conversation_history.ConversationHistory

class AgentRunner(Protocol):
    def run(self) -> AgentOutcome:
        ...

