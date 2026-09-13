import json
from typing import List, Optional
from . import agent_conversation
from . import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry

class Conversation(agent_conversation.Conversation, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._messages: List[agent_conversation.Message] = []
        self._suppression_keys: List[Optional[str]] = []

    @property
    def messages(self) -> List[agent_conversation.Message]:
        # Invariant: Presents current sequence of conversation messages in session
        return list(self._messages)

    def append_message(self, message: agent_conversation.Message) -> None:
        # Requirement: [Conversation] Appending messages and tool responses adds them in chronological order.
        self._messages.append(message)
        self._suppression_keys.append(None)

    def append_tool_response(
        self,
        response: tool_provider.Response,
        tool_name: str,
        tool_call_id: str,
        wire_parameter_bindings: Optional[tool_provider.WireParameterBindings] = None,
    ) -> None:
        # Requirement: Each unprompted tool response presented at session start is preceded in the conversation by a synthetic assistant tool invocation message formatted according to OpenAI tool calling conventions, correlating with the response tool call identifier and ordering serialized argument parameters deterministically by parameter name, presenting the tool execution as if initiated by the model.
        has_assistant_call = any(
            m.role == "assistant" and m.tool_call_id == tool_call_id
            for m in self._messages
        )
        if not has_assistant_call:
            args_dict = dict(wire_parameter_bindings.bindings) if wire_parameter_bindings is not None else {}
            self._messages.append(
                agent_conversation.Message(
                    role="assistant",
                    content="",
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_arguments=json.dumps(args_dict, sort_keys=True),
                )
            )
            self._suppression_keys.append(None)

        effective_reminder = response.reminder
        if response.suppression_key is not None:
            # Requirement: A tool response's suppression key identifies the latest preceding response with the same key in the conversation for replacement with a stub, while responses with unmatched keys are preserved intact.
            for i in range(len(self._messages) - 1, -1, -1):
                if self._suppression_keys[i] == response.suppression_key and not self._messages[i].is_stub:
                    old_msg = self._messages[i]
                    if effective_reminder is None:
                        # Requirement: A stub retains the reminder from the superseded tool response, which the newly appended response inherits when omitted.
                        effective_reminder = old_msg.reminder
                    self._messages[i] = agent_conversation.Message(
                        role=old_msg.role,
                        content="[Superseded]",
                        tool_call_id=old_msg.tool_call_id,
                        tool_name=old_msg.tool_name,
                        reminder=old_msg.reminder,
                        is_stub=True,
                    )
                    break

        self._messages.append(
            agent_conversation.Message(
                role="tool",
                content=response.content,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                reminder=effective_reminder,
            )
        )
        self._suppression_keys.append(response.suppression_key)

    def get_model_request(self) -> agent_conversation.ModelRequest:
        # Requirement: The conversation formats messages in a model request according to OpenAI chat completion conventions for system, user, assistant, and tool messages.
        formatted: List[agent_conversation.Message] = []
        for m in self._messages:
            clean_content = m.content if m.content else ""
            # Requirement: Tool execution response notes, content, and reminders from the tool provider are included in visible tool message content, formatting active reminders on messages and superseded stubs to remind the agent in the assembled model request.
            if m.reminder:
                if clean_content:
                    clean_content = f"{clean_content}\n\nReminder: {m.reminder}"
                else:
                    clean_content = f"Reminder: {m.reminder}"
            formatted.append(
                agent_conversation.Message(
                    role=m.role,
                    content=clean_content,
                    tool_call_id=m.tool_call_id,
                    tool_name=m.tool_name,
                    reminder=m.reminder,
                    tool_arguments=m.tool_arguments,
                    is_stub=m.is_stub,
                )
            )
        return agent_conversation.ModelRequest(messages=formatted)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        Conversation,
        keys=[Conversation, agent_conversation.Conversation],
        tier="agent_session",
    )
