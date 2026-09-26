# Requirements specified in openai_conversation_impl.pyi
import json
from typing import Any, List, Optional
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
        self._suppression_keys: List[Optional[str]] = []

    @property
    def messages(self) -> List[loop_conversation.ConversationMessage]:
        # Invariant: Presents current sequence of conversation messages in session
        return list(self._messages)

    def append_message(self, message: loop_conversation.ConversationMessage) -> None:
        # Requirement: [Conversation] Appending messages and tool responses adds them in chronological order.
        self._messages.append(message)
        self._suppression_keys.append(None)

    def append_tool_response(
        self,
        response: tool_provider.ToolResponse,
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
            args_dict = (
                dict(wire_parameter_bindings.bindings)
                if wire_parameter_bindings is not None
                else {}
            )
            self._messages.append(
                loop_conversation.ConversationMessage(
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
                if (
                    self._suppression_keys[i] == response.suppression_key
                    and not self._messages[i].is_stub
                ):
                    old_msg = self._messages[i]
                    if effective_reminder is None:
                        # Requirement: A stub retains the reminder from the superseded tool response, which the newly appended response inherits when omitted.
                        effective_reminder = old_msg.reminder
                    self._messages[i] = loop_conversation.ConversationMessage(
                        role=old_msg.role,
                        content="[Superseded]",
                        tool_call_id=old_msg.tool_call_id,
                        tool_name=old_msg.tool_name,
                        reminder=old_msg.reminder,
                        is_stub=True,
                    )
                    # Requirement: When a response is replaced with a stub, tool arguments in the correlating assistant invocation message retain their parameter keys, preserving non-string values and eliding string values longer than the supersede arg keep limit configured by the agent config to their trailing characters prefixed with a stub marker and ellipsis.
                    if old_msg.tool_call_id:
                        for j in range(i - 1, -1, -1):
                            if (
                                self._messages[j].role == "assistant"
                                and self._messages[j].tool_call_id == old_msg.tool_call_id
                            ):
                                asst_msg = self._messages[j]
                                try:
                                    agent_cfg = get_singleton(agent_config.AgentConfig)
                                    keep_n = agent_cfg.supersede_arg_keep
                                except Exception:
                                    keep_n = 20

                                new_tool_args: Optional[str] = asst_msg.tool_arguments
                                if asst_msg.tool_arguments:
                                    try:
                                        parsed = json.loads(asst_msg.tool_arguments)
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
                                            new_tool_args = json.dumps(elided, sort_keys=True)
                                        else:
                                            new_tool_args = "{}"
                                    except Exception:
                                        new_tool_args = "{}"
                                else:
                                    new_tool_args = "{}"

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
                role="tool",
                content=response.content,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                reminder=effective_reminder,
            )
        )
        self._suppression_keys.append(response.suppression_key)

    def get_model_request(self) -> loop_conversation.ModelRequest:
        # Requirement: The conversation formats messages in a model request according to OpenAI chat completion conventions for system, user, assistant, and tool messages.
        formatted: List[loop_conversation.ConversationMessage] = []
        for m in self._messages:
            clean_content = m.content if m.content else ""
            # Requirement: Tool execution response notes, content, and reminders from the tool provider are included in visible tool message content, formatting active reminders on messages and superseded stubs to remind the agent in the assembled model request.
            if m.reminder:
                if clean_content:
                    clean_content = f"{clean_content}\n\nReminder: {m.reminder}"
                else:
                    clean_content = f"Reminder: {m.reminder}"
            formatted.append(
                loop_conversation.ConversationMessage(
                    role=m.role,
                    content=clean_content,
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
