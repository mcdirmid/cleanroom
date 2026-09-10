import json
from typing import List, Optional
from . import agent_conversation_history
from . import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry

class ConversationHistory(agent_conversation_history.ConversationHistory, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._messages: List[agent_conversation_history.Message] = []

    @property
    def messages(self) -> List[agent_conversation_history.Message]:
        # Invariant: Presents current sequence of conversation messages in session
        return list(self._messages)

    def append_message(self, message: agent_conversation_history.Message) -> None:
        # Requirement: [ConversationHistory] Appending messages and tool responses adds them in chronological order.
        self._messages.append(message)

    def append_tool_response(
        self,
        response: tool_provider.Response,
        tool_name: str,
        tool_call_id: str,
        wire_parameter_bindings: Optional[tool_provider.WireParameterBindings] = None,
    ) -> None:
        # Requirement: Each unprompted tool response presented at session start is preceded in the conversation history by a synthetic assistant tool invocation message formatted according to OpenAI tool calling conventions, correlating with the response tool call identifier and ordering serialized argument parameters deterministically by parameter name, presenting the tool execution as if initiated by the model.
        has_assistant_call = any(
            m.role == "assistant" and m.tool_call_id == tool_call_id
            for m in self._messages
        )
        if not has_assistant_call:
            args_dict = dict(wire_parameter_bindings.bindings) if wire_parameter_bindings is not None else {}
            self._messages.append(
                agent_conversation_history.Message(
                    role="assistant",
                    content="",
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_arguments=json.dumps(args_dict, sort_keys=True),
                )
            )

        # Requirement: When an appended tool result supersedes an earlier result for the same resource, earlier tool results matching the resource identifier—such as the target read-write file alias identified by internal metadata markers or single-instance tool executions—are replaced in place with a stub, while tool results for distinct resources and read-only files are preserved.
        new_resource = None
        new_kind = None
        for line in response.content.splitlines():
            if line.startswith("_resource:"):
                new_resource = line.split(":", 1)[1].strip()
            elif line.startswith("_kind:"):
                new_kind = line.split(":", 1)[1].strip()
            elif not line.startswith("_"):
                break

        effective_reminder = response.reminder
        if new_kind != "read_only":
            for i, m in enumerate(self._messages):
                if m.role == "tool" and not isinstance(m, agent_conversation_history.Stub):
                    m_resource = None
                    m_kind = None
                    for line in m.content.splitlines():
                        if line.startswith("_resource:"):
                            m_resource = line.split(":", 1)[1].strip()
                        elif line.startswith("_kind:"):
                            m_kind = line.split(":", 1)[1].strip()
                        elif not line.startswith("_"):
                            break

                    should_supersede = False
                    if new_resource is not None and new_kind == "read_write":
                        should_supersede = (m_resource == new_resource and m_kind == "read_write")
                    elif new_resource is None and m_resource is None:
                        should_supersede = (m.tool_name == tool_name)

                    if should_supersede:
                        if effective_reminder is None:
                            effective_reminder = m.reminder
                        # Requirement: A stub retains any reminder provided in the superseded tool response to remind the agent in subsequent turns, and when the newly appended tool result does not supply a reminder, it inherits the reminder from the superseded response.
                        self._messages[i] = agent_conversation_history.Stub(
                            role="tool",
                            content="[Superseded]",
                            tool_call_id=m.tool_call_id,
                            tool_name=m.tool_name,
                            reminder=m.reminder,
                        )

        self._messages.append(
            agent_conversation_history.Message(
                role="tool",
                content=response.content,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                reminder=effective_reminder,
            )
        )

    def get_model_request(self) -> agent_conversation_history.ModelRequest:
        # Requirement: The conversation history formats messages in a model request according to OpenAI chat completion conventions for system, user, assistant, and tool messages.
        formatted: List[agent_conversation_history.Message] = []
        for m in self._messages:
            # Requirement: Messages in a model request omit internal metadata fields starting with an underscore.
            lines = [line for line in m.content.splitlines() if not line.strip().startswith("_")]
            clean_content = "\n".join(lines) if m.content else ""
            # Requirement: Tool execution response notes, content, and reminders from the tool provider are included in visible tool message content, formatting active reminders on messages and superseded stubs to remind the agent in the assembled model request.
            if m.reminder:
                if clean_content:
                    clean_content = f"{clean_content}\n\nReminder: {m.reminder}"
                else:
                    clean_content = f"Reminder: {m.reminder}"
            formatted.append(
                agent_conversation_history.Message(
                    role=m.role,
                    content=clean_content,
                    tool_call_id=m.tool_call_id,
                    tool_name=m.tool_name,
                    reminder=m.reminder,
                    tool_arguments=m.tool_arguments,
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
