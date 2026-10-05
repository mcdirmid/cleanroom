# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 269b1a2d24d1
# COVERAGE_AUDIT: 2026-10-05T04:28:01Z
# QA_AUDIT: 2026-10-05T04:28:01Z
# --- END CLEANROOM METADATA ---

# Requirements specified in openai_conversation_impl.pyi
import json
from typing import Any, List, Optional, Sequence
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.loop.lib import loop_conversation
from update_with_ai.parts.sandbox.lib import tool_provider
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
)

_SUPPRESSION_BUFFER_LIMIT = 3

_PATH_PARAM_NAMES = frozenset(
    {
        "path",
        "target_file",
        "targetfile",
        "file",
        "file_alias",
        "file_path",
        "filepath",
        "file_name",
        "filename",
    }
)


def _is_path_param(name: str) -> bool:
    normalized = name.lower().replace("-", "_")
    return (
        normalized in _PATH_PARAM_NAMES
        or normalized.endswith("_path")
        or normalized.endswith("_file")
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
                    m.role == loop_conversation.MessageRole("assistant")
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
                    self._messages.append(
                        loop_conversation.ConversationMessage(
                            role=loop_conversation.MessageRole("assistant"),
                            content=loop_conversation.ConversationContent(""),
                            tool_call_id=msg.tool_call_id,
                            tool_name=msg.tool_name,
                            tool_arguments=loop_conversation.SerializedArguments(
                                formatted_args
                            ),
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
            m.role == loop_conversation.MessageRole("assistant")
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
            self._messages.append(
                loop_conversation.ConversationMessage(
                    role=loop_conversation.MessageRole("assistant"),
                    content=loop_conversation.ConversationContent(""),
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_arguments=loop_conversation.SerializedArguments(
                        formatted_args
                    ),
                )
            )
            self._suppression_keys.append(None)

        effective_reminder = tool_response.reminder
        if tool_response.suppression_key is not None:
            if effective_reminder is None:
                for i in range(len(self._messages) - 1, -1, -1):
                    if (
                        self._suppression_keys[i] == tool_response.suppression_key
                        and self._messages[i].reminder is not None
                    ):
                        effective_reminder = self._messages[i].reminder
                        break

            matching_indices = [
                i
                for i in range(len(self._messages))
                if self._suppression_keys[i] == tool_response.suppression_key
                and not self._messages[i].is_stub
            ]

            keep_preceding = _SUPPRESSION_BUFFER_LIMIT - 1
            num_to_stub = max(0, len(matching_indices) - keep_preceding)
            indices_to_stub = matching_indices[:num_to_stub]

            for old_idx in indices_to_stub:
                old_msg = self._messages[old_idx]
                self._messages[old_idx] = loop_conversation.ConversationMessage(
                    role=old_msg.role,
                    content=loop_conversation.ConversationContent("[Superseded]"),
                    tool_call_id=old_msg.tool_call_id,
                    tool_name=old_msg.tool_name,
                    reminder=old_msg.reminder,
                    is_stub=True,
                )
                if old_msg.tool_call_id:
                    for j in range(old_idx - 1, -1, -1):
                        if (
                            self._messages[j].role
                            == loop_conversation.MessageRole("assistant")
                            and self._messages[j].tool_call_id == old_msg.tool_call_id
                        ):
                            asst_msg = self._messages[j]
                            new_tool_args: Optional[
                                loop_conversation.SerializedArguments
                            ] = asst_msg.tool_arguments
                            if asst_msg.tool_arguments:
                                try:
                                    parsed = json.loads(str(asst_msg.tool_arguments))
                                    if isinstance(parsed, dict):
                                        elided: dict[str, Any] = {}
                                        for k, v in parsed.items():
                                            if _is_path_param(k) or not isinstance(
                                                v, str
                                            ):
                                                elided[k] = v
                                            else:
                                                elided[k] = "[STUB]"
                                        new_tool_args = (
                                            loop_conversation.SerializedArguments(
                                                json.dumps(elided, sort_keys=True)
                                            )
                                        )
                                    else:
                                        new_tool_args = loop_conversation.SerializedArguments(
                                            "{}"
                                        )  # pragma: no cover (assumption: SerializedArguments contains valid JSON)
                                except (
                                    json.JSONDecodeError,
                                    TypeError,
                                ):  # pragma: no cover (assumption: SerializedArguments contains valid JSON)
                                    new_tool_args = loop_conversation.SerializedArguments(
                                        "{}"
                                    )  # pragma: no cover (assumption: SerializedArguments contains valid JSON)
                            else:
                                new_tool_args = loop_conversation.SerializedArguments(
                                    "{}"
                                )  # pragma: no cover (assumption: SerializedArguments contains valid JSON)

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

        self._messages.append(
            loop_conversation.ConversationMessage(
                role=loop_conversation.MessageRole("tool"),
                content=loop_conversation.ConversationContent(
                    str(tool_response.content)
                ),
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
