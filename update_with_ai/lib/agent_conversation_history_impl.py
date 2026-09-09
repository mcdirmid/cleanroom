from typing import List, Optional
from . import agent_conversation_history
from . import tool_provider
from .lifecycle import LifecycleRegistry, Singleton, get_default_registry

class ConversationHistory(agent_conversation_history.ConversationHistory, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._messages: List[agent_conversation_history.Message] = []

    @property
    def messages(self) -> List[agent_conversation_history.Message]:
        # Invariant: Presents current sequence of conversation messages in session
        return list(self._messages)

    def append_message(self, message: agent_conversation_history.Message) -> None:
        # Requirement: Appending messages adds them in chronological order
        self._messages.append(message)

    def append_tool_response(
        self, response: tool_provider.Response, tool_name: str, tool_call_id: str
    ) -> None:
        # Requirement: Prepend synthetic assistant invocation when unprompted at session start
        has_assistant_call = any(
            m.role == "assistant" and (m.tool_call_id == tool_call_id or m.tool_name == tool_name)
            for m in self._messages
        )
        if not has_assistant_call:
            self._messages.append(
                agent_conversation_history.Message(
                    role="assistant",
                    content="",
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                )
            )

        # Requirement: Superseded tool results for the same resource are replaced in place with stubs
        for i, m in enumerate(self._messages):
            if m.role == "tool" and m.tool_name == tool_name and not isinstance(m, agent_conversation_history.Stub):
                self._messages[i] = agent_conversation_history.Stub(
                    role="tool",
                    content="[Superseded]",
                    tool_call_id=m.tool_call_id,
                    tool_name=m.tool_name,
                )

        # Requirement: Tool execution response notes and content are included in visible tool message content
        self._messages.append(
            agent_conversation_history.Message(
                role="tool",
                content=response.content,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
            )
        )

    def get_model_request(self) -> agent_conversation_history.ModelRequest:
        # Requirement: Formats messages into a provider model request
        formatted: List[agent_conversation_history.Message] = []
        for m in self._messages:
            # Requirement: Strips internal metadata markers from model request messages
            lines = [line for line in m.content.splitlines() if not line.strip().startswith("_")]
            clean_content = "\n".join(lines) if m.content else ""
            formatted.append(
                agent_conversation_history.Message(
                    role=m.role,
                    content=clean_content,
                    tool_call_id=m.tool_call_id,
                    tool_name=m.tool_name,
                )
            )
        return agent_conversation_history.ModelRequest(messages=formatted)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        ConversationHistory,
        keys=[ConversationHistory, agent_conversation_history.ConversationHistory],
        tier="agent_session",
    )
