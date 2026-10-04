import json
from typing import Any, List, Optional, Sequence
from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.loop.lib import loop_conversation
from update_with_ai.parts.sandbox.lib import tool_provider
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)


class Conversation(loop_conversation.Conversation, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._messages: List[loop_conversation.ConversationMessage] = []
        self._suppression_keys: List[Optional[tool_provider.SuppressionKey]] = []

    @property
    def messages(self) -> List[loop_conversation.ConversationMessage]:
        return list(self._messages)

    def initialize(
        self, initial_messages: Sequence[loop_conversation.ConversationMessage] = ()
    ) -> None:
        self._messages = []
        self._suppression_keys = []
        for msg in initial_messages:
            if msg.role == loop_conversation.MessageRole("tool"):
                has_assistant_call = any(
                    m.role == loop_conversation.MessageRole("assistant") and m.tool_call_id == msg.tool_call_id
                    for m in self._messages
                )
                if not has_assistant_call:
                    formatted_args = str(msg.tool_arguments or "")
                    if formatted_args:
                        try:
                            parsed = json.loads(formatted_args)
                            if isinstance(parsed, dict):
                                formatted_args = json.dumps(parsed, sort_keys=True)
                        except (json.JSONDecodeError, TypeError):  # pragma: no cover (assumption: SerializedArguments contains valid JSON)
                            pass
                    self._messages.append(
                        loop_conversation.ConversationMessage(
                            role=loop_conversation.MessageRole("assistant"),
                            content=loop_conversation.ConversationContent(""),
                            tool_call_id=msg.tool_call_id,
                            tool_name=msg.tool_name,
                            tool_arguments=loop_conversation.SerializedArguments(formatted_args),
                        )
                    )
                    self._suppression_keys.append(None)
            self._messages.append(msg)
            self._suppression_keys.append(None)

    def append_message(self, message: loop_conversation.ConversationMessage) -> None:
        self._messages.append(message)
        self._suppression_keys.append(None)

    def append_tool_response(
        self,
        tool_response: tool_provider.ToolResponse,
        tool_call_id: loop_conversation.ToolCallId,
        tool_name: tool_provider.ToolName,
        tool_arguments: loop_conversation.SerializedArguments,
    ) -> None:
        has_assistant_call = any(
            m.role == loop_conversation.MessageRole("assistant") and m.tool_call_id == tool_call_id
            for m in self._messages
        )
        if not has_assistant_call:
            formatted_args = str(tool_arguments)
            if formatted_args:
                try:
                    parsed = json.loads(formatted_args)
                    if isinstance(parsed, dict):
                        formatted_args = json.dumps(parsed, sort_keys=True)
                except (json.JSONDecodeError, TypeError):  # pragma: no cover (assumption: SerializedArguments contains valid JSON)
                    pass
            self._messages.append(
                loop_conversation.ConversationMessage(
                    role=loop_conversation.MessageRole("assistant"),
                    content=loop_conversation.ConversationContent(""),
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_arguments=loop_conversation.SerializedArguments(formatted_args),
                )
            )
            self._suppression_keys.append(None)

        effective_reminder = tool_response.reminder
        if tool_response.suppression_key is not None:
            for i in range(len(self._messages) - 1, -1, -1):
                if (
                    self._suppression_keys[i] == tool_response.suppression_key
                    and not self._messages[i].is_stub
                ):
                    old_msg = self._messages[i]
                    if effective_reminder is None:
                        effective_reminder = old_msg.reminder
                    self._messages[i] = loop_conversation.ConversationMessage(
                        role=old_msg.role,
                        content=loop_conversation.ConversationContent("[Superseded]"),
                        tool_call_id=old_msg.tool_call_id,
                        tool_name=old_msg.tool_name,
                        reminder=old_msg.reminder,
                        is_stub=True,
                    )
                    if old_msg.tool_call_id:
                        for j in range(i - 1, -1, -1):
                            if (
                                self._messages[j].role == loop_conversation.MessageRole("assistant")
                                and self._messages[j].tool_call_id == old_msg.tool_call_id
                            ):
                                asst_msg = self._messages[j]
                                try:
                                    agent_cfg = get_singleton(agent_config.AgentConfig)
                                    keep_n = int(agent_cfg.supersede_arg_keep)
                                except (KeyError, LookupError, AttributeError):  # pragma: no cover (assumption: SerializedArguments contains valid JSON)
                                    keep_n = 20

                                new_tool_args: Optional[loop_conversation.SerializedArguments] = asst_msg.tool_arguments
                                if asst_msg.tool_arguments:
                                    try:
                                        parsed = json.loads(str(asst_msg.tool_arguments))
                                        if isinstance(parsed, dict):
                                            elided: dict[str, Any] = {}
                                            for k, v in parsed.items():
                                                if isinstance(v, str):
                                                    if keep_n <= 0:
                                                        elided[k] = "[STUB]"
                                                    elif len(v) > keep_n:
                                                        elided[k] = f"[STUB]...{v[-keep_n:]}"
                                                    else:
                                                        elided[k] = v
                                                else:
                                                    elided[k] = v
                                            new_tool_args = loop_conversation.SerializedArguments(
                                                json.dumps(elided, sort_keys=True)
                                            )
                                        else:
                                            new_tool_args = loop_conversation.SerializedArguments("{}")  # pragma: no cover (assumption: SerializedArguments contains valid JSON)
                                    except (json.JSONDecodeError, TypeError):  # pragma: no cover (assumption: SerializedArguments contains valid JSON)
                                        new_tool_args = loop_conversation.SerializedArguments("{}")  # pragma: no cover (assumption: SerializedArguments contains valid JSON)
                                else:
                                    new_tool_args = loop_conversation.SerializedArguments("{}")  # pragma: no cover (assumption: SerializedArguments contains valid JSON)

                                self._messages[j] = loop_conversation.ConversationMessage(
                                    role=asst_msg.role,
                                    content=asst_msg.content,
                                    tool_call_id=asst_msg.tool_call_id,
                                    tool_name=asst_msg.tool_name,
                                    reminder=asst_msg.reminder,
                                    tool_arguments=new_tool_args,
                                    is_stub=True,
                                )
                                break
                    break

        self._messages.append(
            loop_conversation.ConversationMessage(
                role=loop_conversation.MessageRole("tool"),
                content=loop_conversation.ConversationContent(str(tool_response.content)),
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                reminder=effective_reminder,
            )
        )
        self._suppression_keys.append(tool_response.suppression_key)

    def get_model_request(self) -> loop_conversation.ModelRequest:
        formatted: List[loop_conversation.ConversationMessage] = []
        last_idx = len(self._messages) - 1
        for i, m in enumerate(self._messages):
            clean_content = str(m.content) if m.content else ""
            if i == last_idx and m.reminder:
                if clean_content:
                    clean_content = f"{clean_content}\n\nReminder: {m.reminder}"
                else:
                    clean_content = f"Reminder: {m.reminder}"
            formatted.append(
                loop_conversation.ConversationMessage(
                    role=m.role,
                    content=loop_conversation.ConversationContent(clean_content),
                    tool_call_id=m.tool_call_id,
                    tool_name=m.tool_name,
                    reminder=m.reminder,
                    tool_arguments=m.tool_arguments,
                    is_stub=m.is_stub,
                )
            )
        return loop_conversation.ModelRequest(messages=formatted)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        Conversation,
        keys=[Conversation, loop_conversation.Conversation],
        tier=agent_session,
    )
