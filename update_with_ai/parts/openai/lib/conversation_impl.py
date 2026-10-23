# Requirements specified in conversation_impl.pyi
import json
from typing import Any, Dict, List, Optional, Sequence
from update_with_ai.parts.agent.lib.session import session as agent_session
from update_with_ai.parts.loop.lib import conversation
from update_with_ai.parts.sandbox.lib import tool_provider
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
)

# Contract: Buffer limit of up to three most recent responses sharing suppression keys.
_SUPPRESSION_BUFFER_LIMIT = 3


# Contract: Conversation realizes OpenAI provider role schema formatting, stubbing, and synthetic call injection in the agent session tier.
class Conversation(conversation.Conversation):
    tier = agent_session

    def __init__(self) -> None:
        self._messages: List[conversation.ConversationMessage] = []
        self._suppression_keys: List[Optional[tool_provider.SuppressionKey]] = []
        self._retained_reminders: Dict[
            tool_provider.SuppressionKey, tool_provider.ToolReminder
        ] = {}

    # Contract: Conversation.initialize - initializes conversation history, pairing unprompted responses with synthetic calls.
    def initialize(
        self, initial_messages: Sequence[conversation.ConversationMessage] = ()
    ) -> None:
        self._messages = []
        self._suppression_keys = []
        self._retained_reminders = {}
        for msg in initial_messages:
            if msg.role == conversation.MessageRole("tool"):
                has_assistant_call = any(
                    m.role == conversation.MessageRole("assistant")
                    and m.tool_call_id == msg.tool_call_id
                    for m in self._messages
                )
                if not has_assistant_call:
                    formatted_args = str(msg.tool_arguments or "")
                    if formatted_args:
                        try:
                            parsed = json.loads(formatted_args)
                            if isinstance(parsed, dict):
                                formatted_args = json.dumps(parsed, sort_keys=True)
                        except (
                            json.JSONDecodeError,
                            TypeError,
                        ):  # pragma: no cover (assumption: SerializedArguments contains valid JSON)
                            pass
                    # Contract: Precede unprompted tool responses with synthetic assistant tool invocations.
                    self._messages.append(
                        conversation.ConversationMessage(
                            role=conversation.MessageRole("assistant"),
                            content=conversation.ConversationContent(""),
                            tool_call_id=msg.tool_call_id,
                            tool_name=msg.tool_name,
                            tool_arguments=conversation.SerializedArguments(
                                formatted_args
                            ),
                        )
                    )
                    self._suppression_keys.append(None)
            self._messages.append(msg)
            self._suppression_keys.append(None)

    # Contract: Conversation.append_message - appends conversation message directly to in-memory history.
    def append_message(self, message: conversation.ConversationMessage) -> None:
        self._messages.append(message)
        self._suppression_keys.append(None)

    # Contract: Conversation.append_tool_response - appends tool response, deleting preceding suppressed responses and their tool calls beyond the buffer limit.
    def append_tool_response(
        self,
        tool_response: tool_provider.ToolResponse,
        tool_call_id: conversation.ToolCallId,
        tool_name: tool_provider.ToolName,
        tool_arguments: conversation.SerializedArguments,
    ) -> None:
        has_assistant_call = any(
            m.role == conversation.MessageRole("assistant")
            and m.tool_call_id == tool_call_id
            for m in self._messages
        )
        if not has_assistant_call:
            formatted_args = str(tool_arguments)
            if formatted_args:
                try:
                    parsed = json.loads(formatted_args)
                    if isinstance(parsed, dict):
                        formatted_args = json.dumps(parsed, sort_keys=True)
                except (
                    json.JSONDecodeError,
                    TypeError,
                ):  # pragma: no cover (assumption: SerializedArguments contains valid JSON)
                    pass
            # Contract: Precede unprompted tool responses with synthetic assistant tool invocations.
            self._messages.append(
                conversation.ConversationMessage(
                    role=conversation.MessageRole("assistant"),
                    content=conversation.ConversationContent(""),
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_arguments=conversation.SerializedArguments(
                        formatted_args
                    ),
                )
            )
            self._suppression_keys.append(None)

        # Contract: MUST retain reminders from deleted responses and inherit them when omitted.
        effective_reminder = tool_response.reminder
        if tool_response.suppression_key is not None:
            if effective_reminder is not None:
                self._retained_reminders[tool_response.suppression_key] = effective_reminder
            else:
                effective_reminder = self._retained_reminders.get(tool_response.suppression_key)

        # Contract: Append tool response with effective reminder; preserve responses with unmatched suppression keys intact.
        self._messages.append(
            conversation.ConversationMessage(
                role=conversation.MessageRole("tool"),
                content=conversation.ConversationContent(
                    str(tool_response.content)
                ),
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                reminder=effective_reminder,
            )
        )
        self._suppression_keys.append(tool_response.suppression_key)

        # Contract: MUST retain a buffer of up to three most recent responses sharing suppression keys.
        # Contract: MUST delete preceding responses and their correlating assistant tool calls beyond the buffer limit.
        if tool_response.suppression_key is not None:
            matching_tool_indices = [
                i
                for i in range(len(self._messages))
                if self._suppression_keys[i] == tool_response.suppression_key
            ]
            if len(matching_tool_indices) > _SUPPRESSION_BUFFER_LIMIT:
                num_to_delete = len(matching_tool_indices) - _SUPPRESSION_BUFFER_LIMIT
                tool_indices_to_delete = matching_tool_indices[:num_to_delete]
                indices_to_remove = set(tool_indices_to_delete)

                for tool_idx in tool_indices_to_delete:
                    old_msg = self._messages[tool_idx]
                    rem = old_msg.reminder
                    if rem is not None:
                        self._retained_reminders[tool_response.suppression_key] = rem
                    if old_msg.tool_call_id:
                        for j in range(tool_idx - 1, -1, -1):
                            if (
                                self._messages[j].role
                                == conversation.MessageRole("assistant")
                                and self._messages[j].tool_call_id == old_msg.tool_call_id
                            ):
                                indices_to_remove.add(j)
                                break

                self._messages = [
                    m
                    for i, m in enumerate(self._messages)
                    if i not in indices_to_remove
                ]
                self._suppression_keys = [
                    k
                    for i, k in enumerate(self._suppression_keys)
                    if i not in indices_to_remove
                ]

    # Contract: Conversation.get_model_request - assembles model request formatted according to OpenAI role schemas, including active reminders.
    def get_model_request(self) -> conversation.ModelRequest:
        formatted: List[conversation.ConversationMessage] = []
        last_idx = len(self._messages) - 1
        for i, m in enumerate(self._messages):
            clean_content = str(m.content) if m.content else ""
            if i == last_idx and m.reminder:
                if clean_content:
                    clean_content = f"{clean_content}\n\nReminder: {m.reminder}"
                else:
                    clean_content = f"Reminder: {m.reminder}"
            formatted.append(
                conversation.ConversationMessage(
                    role=m.role,
                    content=conversation.ConversationContent(clean_content),
                    tool_call_id=m.tool_call_id,
                    tool_name=m.tool_name,
                    reminder=m.reminder,
                    tool_arguments=m.tool_arguments,
                    is_stub=m.is_stub,
                )
            )
        return conversation.ModelRequest(messages=formatted)
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-21T12:45:00Z
# CHANGE: Delete superseded tool calls and responses beyond buffer limit instead of stubbing arguments
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        Conversation,
        keys=[Conversation, conversation.Conversation],
        tier=agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
