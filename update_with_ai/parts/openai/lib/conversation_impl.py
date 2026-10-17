# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T04:56:35Z
# CHANGE: Prune the uncontracted public 'messages' property so the implementation exposes only the conversation operations declared by the grounding specification
# CODE_HASH: 43acfa91915e
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

# Requirements specified in conversation_impl.pyi
import json
from typing import Any, List, Optional, Sequence
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

# Contract: File path parameter names preserved in superseded tool calls.
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


# Contract: Identifies file path parameters to preserve in superseded tool calls.
def _is_path_param(name: str) -> bool:
    normalized = name.lower().replace("-", "_")
    return (
        normalized in _PATH_PARAM_NAMES
        or normalized.endswith("_path")
        or normalized.endswith("_file")
    )


# Contract: Conversation realizes OpenAI provider role schema formatting, stubbing, and synthetic call injection in the agent session tier.
class Conversation(conversation.Conversation, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._messages: List[conversation.ConversationMessage] = []
        self._suppression_keys: List[Optional[tool_provider.SuppressionKey]] = []

    # Contract: Conversation.initialize - initializes conversation history, pairing unprompted responses with synthetic calls.
    def initialize(
        self, initial_messages: Sequence[conversation.ConversationMessage] = ()
    ) -> None:
        self._messages = []
        self._suppression_keys = []
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

    # Contract: Conversation.append_tool_response - appends tool response, replacing preceding suppressed responses with stubs beyond buffer limit.
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


        # Contract: MUST retain reminders on stubs and inherit them when omitted.
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

            # Contract: MUST retain a buffer of up to three most recent responses sharing suppression keys.
            matching_indices = [
                i
                for i in range(len(self._messages))
                if self._suppression_keys[i] == tool_response.suppression_key
                and not self._messages[i].is_stub
            ]

            keep_preceding = _SUPPRESSION_BUFFER_LIMIT - 1
            num_to_stub = max(0, len(matching_indices) - keep_preceding)
            indices_to_stub = matching_indices[:num_to_stub]

            # Contract: MUST replace preceding responses beyond the buffer limit with stubs.
            for old_idx in indices_to_stub:
                old_msg = self._messages[old_idx]
                self._messages[old_idx] = conversation.ConversationMessage(
                    role=old_msg.role,
                    content=conversation.ConversationContent("[Superseded]"),
                    tool_call_id=old_msg.tool_call_id,
                    tool_name=old_msg.tool_name,
                    reminder=old_msg.reminder,
                    is_stub=True,
                )
                if old_msg.tool_call_id:
                    for j in range(old_idx - 1, -1, -1):
                        if (
                            self._messages[j].role
                            == conversation.MessageRole("assistant")
                            and self._messages[j].tool_call_id == old_msg.tool_call_id
                        ):
                            asst_msg = self._messages[j]
                            new_tool_args: Optional[
                                conversation.SerializedArguments
                            ] = asst_msg.tool_arguments
                            if asst_msg.tool_arguments:
                                try:
                                    parsed = json.loads(str(asst_msg.tool_arguments))
                                    if isinstance(parsed, dict):
                                        elided: dict[str, Any] = {}
                                        for k, v in parsed.items():
                                            # Contract: MUST preserve file path parameters and non-string arguments in superseded tool calls.
                                            if _is_path_param(k) or not isinstance(
                                                v, str
                                            ):
                                                elided[k] = v
                                            else:
                                                # Contract: MUST replace other string arguments with a stub marker in superseded tool calls.
                                                elided[k] = "[STUB]"
                                        new_tool_args = (
                                            conversation.SerializedArguments(
                                                json.dumps(elided, sort_keys=True)
                                            )
                                        )
                                    else:
                                        new_tool_args = conversation.SerializedArguments(
                                            "{}"
                                        )  # pragma: no cover (assumption: SerializedArguments contains valid JSON)
                                except (
                                    json.JSONDecodeError,
                                    TypeError,
                                ):  # pragma: no cover (assumption: SerializedArguments contains valid JSON)
                                    new_tool_args = conversation.SerializedArguments(
                                        "{}"
                                    )  # pragma: no cover (assumption: SerializedArguments contains valid JSON)
                            else:
                                new_tool_args = conversation.SerializedArguments(
                                    "{}"
                                )  # pragma: no cover (assumption: SerializedArguments contains valid JSON)

                            self._messages[j] = conversation.ConversationMessage(
                                role=asst_msg.role,
                                content=asst_msg.content,
                                tool_call_id=asst_msg.tool_call_id,
                                tool_name=asst_msg.tool_name,
                                reminder=asst_msg.reminder,
                                tool_arguments=new_tool_args,
                                is_stub=True,
                            )
                            break

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
