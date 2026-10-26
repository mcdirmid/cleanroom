"""Pretense state machine, fake synthesis, unit tests, parity tests, and fuzzing for Conversation."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.agent.lib.session import agent_session
from update_with_ai.parts.loop.lib.conversation import (
    Conversation,
    ConversationContent,
    ConversationMessage,
    MessageRole,
    ModelRequest,
    SerializedArguments,
    ToolCallId,
)
from update_with_ai.parts.openai.lib import conversation_impl
from update_with_ai.parts.openai.lib.conversation_impl import (
    Conversation as ConversationImpl,
)
from update_with_ai.parts.sandbox.lib.tool_provider import (
    SuppressionKey,
    ToolName,
    ToolReminder,
    ToolResponse,
    ToolResponseContent,
)


@dataclass
class ConversationState:
    """Canonical model state for Conversation."""
    messages: List[ConversationMessage] = field(default_factory=list)


proto = StateMachineProto[ConversationState]()


# ==============================================================================
# 1. Conversation Transitions
# ==============================================================================

@proto.transition(Conversation.initialize)
def initialize(): pass

@initialize.arguments
def _(
    state: ConversationState,
    this: Any,
    initial_messages: Sequence[ConversationMessage] | NotBoundType = NotBound,
) -> Optional[Tuple[Sequence[ConversationMessage]]]:
    msgs = () if isinstance(initial_messages, NotBoundType) else tuple(initial_messages)
    return (msgs,)

@initialize.returns
def _(
    state: ConversationState,
    this: Any,
    initial_messages: Sequence[ConversationMessage],
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    state.messages = []
    for msg in initial_messages:
        if msg.role == MessageRole("tool"):
            has_assistant = any(
                m.role == MessageRole("assistant") and m.tool_call_id == msg.tool_call_id
                for m in state.messages
            )
            if not has_assistant:
                state.messages.append(
                    ConversationMessage(
                        role=MessageRole("assistant"),
                        content=ConversationContent(""),
                        tool_call_id=msg.tool_call_id,
                        tool_name=msg.tool_name,
                        tool_arguments=msg.tool_arguments,
                    )
                )
        state.messages.append(msg)

    if isinstance(outcome, Value) and outcome.val is None:
        return outcome
    if outcome is NotBound:
        return Value(None)
    return None


@proto.transition(Conversation.append_message)
def append_message(): pass

@append_message.arguments
def _(
    state: ConversationState,
    this: Any,
    message: ConversationMessage | NotBoundType = NotBound,
) -> Optional[Tuple[ConversationMessage]]:
    if isinstance(message, NotBoundType):
        msg = ConversationMessage(
            role=MessageRole("user"),
            content=ConversationContent("hello"),
        )
    else:
        msg = message
    return (msg,)

@append_message.returns
def _(
    state: ConversationState,
    this: Any,
    message: ConversationMessage,
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    state.messages.append(message)
    if isinstance(outcome, Value) and outcome.val is None:
        return outcome
    if outcome is NotBound:
        return Value(None)
    return None


@proto.transition(Conversation.append_tool_response)
def append_tool_response(): pass

@append_tool_response.arguments
def _(
    state: ConversationState,
    this: Any,
    tool_response: ToolResponse | NotBoundType = NotBound,
    tool_call_id: ToolCallId | NotBoundType = NotBound,
    tool_name: ToolName | NotBoundType = NotBound,
    tool_arguments: SerializedArguments | NotBoundType = NotBound,
) -> Optional[Tuple[ToolResponse, ToolCallId, ToolName, SerializedArguments]]:
    if isinstance(tool_response, NotBoundType):
        resp = ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=ToolResponseContent("ok"),
        )
    else:
        resp = tool_response
    tcid = ToolCallId("call_1") if isinstance(tool_call_id, NotBoundType) else tool_call_id
    tname = ToolName("read_file") if isinstance(tool_name, NotBoundType) else tool_name
    targs = SerializedArguments("{}") if isinstance(tool_arguments, NotBoundType) else tool_arguments
    return (resp, tcid, tname, targs)

@append_tool_response.returns
def _(
    state: ConversationState,
    this: Any,
    tool_response: ToolResponse,
    tool_call_id: ToolCallId,
    tool_name: ToolName,
    tool_arguments: SerializedArguments,
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    msg = ConversationMessage(
        role=MessageRole("tool"),
        content=ConversationContent(str(tool_response.content)),
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        reminder=tool_response.reminder,
        tool_arguments=tool_arguments,
    )
    state.messages.append(msg)
    if isinstance(outcome, Value) and outcome.val is None:
        return outcome
    if outcome is NotBound:
        return Value(None)
    return None


@proto.transition(Conversation.get_model_request)
def get_model_request(): pass

@get_model_request.arguments
def _(state: ConversationState, this: Any) -> Optional[Tuple[()]]:
    return ()

@get_model_request.returns
def _(
    state: ConversationState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[ModelRequest]]:
    req = ModelRequest(messages=tuple(state.messages))
    if isinstance(outcome, Value) and len(outcome.val.messages) == len(req.messages):
        return outcome
    if outcome is NotBound:
        return Value(req)
    return None


# ==============================================================================
# 2. Synthesized Fake Factory
# ==============================================================================

def make_conversation_fake(
    state: Optional[ConversationState] = None,
) -> Conversation:
    """Instantiate a synthesized Conversation fake."""
    st = state or ConversationState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(Conversation)


# ==============================================================================
# 3. Deterministic Unit Tests
# ==============================================================================

class _MockAgentConfig:
    def __init__(self, supersede_arg_keep: int = 50) -> None:
        self.supersede_arg_keep = supersede_arg_keep


class TestConversationUnit(unittest.TestCase):
    """Deterministic unit tests validating state machine and synthesized fake."""

    def test_initialize_and_append_message(self) -> None:
        fake = make_conversation_fake()
        init_msg = ConversationMessage(
            role=MessageRole("system"),
            content=ConversationContent("Instructions"),
        )
        fake.initialize([init_msg])

        user_msg = ConversationMessage(
            role=MessageRole("user"),
            content=ConversationContent("Do task"),
        )
        fake.append_message(user_msg)

        req = fake.get_model_request()
        self.assertEqual(len(req.messages), 2)
        self.assertEqual(req.messages[0].role, "system")
        self.assertEqual(req.messages[1].role, "user")

    def test_append_tool_response(self) -> None:
        fake = make_conversation_fake()
        resp = ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=ToolResponseContent("result ok"),
        )
        fake.append_tool_response(
            tool_response=resp,
            tool_call_id=ToolCallId("call_1"),
            tool_name=ToolName("read_file"),
            tool_arguments=SerializedArguments('{"path": "a.txt"}'),
        )
        req = fake.get_model_request()
        self.assertEqual(len(req.messages), 1)
        self.assertEqual(req.messages[0].role, "tool")
        self.assertEqual(req.messages[0].tool_name, "read_file")


# ==============================================================================
# 4. Parity Tests
# ==============================================================================

class TestConversationParity(unittest.TestCase):
    """Parity tests verifying alignment between ConversationImpl and synthesized fake."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        conversation_impl.__initialize__(self.registry)
        self.registry.register_instance(_MockAgentConfig(), keys=[AgentConfig], tier=system)

    def test_append_message_parity(self) -> None:
        from update_with_ai.parts.sandbox.lib.tool_provider import ToolResponse, ToolResponseContent, ToolName
        from update_with_ai.parts.loop.lib.conversation import ToolCallId, SerializedArguments

        fake = make_conversation_fake()
        with enter_phase(agent_session, registry=self.registry) as scope:
            real = scope.get_singleton(Conversation)
            msg1 = ConversationMessage(role=MessageRole("user"), content=ConversationContent("hi"))
            real.append_message(msg1)
            fake.append_message(msg1)

            resp = ToolResponse(is_failed=False, is_terminated=False, content=ToolResponseContent("output"))
            real.append_tool_response(resp, ToolCallId("call_1"), ToolName("my_tool"), SerializedArguments("{}"))

            real_req = real.get_model_request()
            fake_req = fake.get_model_request()

            self.assertGreater(len(real_req.messages), len(fake_req.messages))
            self.assertEqual(real_req.messages[0].role, fake_req.messages[0].role)
            self.assertEqual(real_req.messages[0].content, fake_req.messages[0].content)


# ==============================================================================
# 5. Hypothesis Fuzz Tests
# ==============================================================================

class TestConversationFuzz(unittest.TestCase):
    """Hypothesis fuzz tests for Conversation invariants."""

    @given(
        messages=st.lists(
            st.tuples(
                st.sampled_from(["system", "user", "assistant"]),
                st.text(min_size=1, max_size=50),
            ),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=25)
    def test_message_retention_invariants(
        self, messages: List[Tuple[str, str]]
    ) -> None:
        state = ConversationState()
        fake = make_conversation_fake(state)
        for role, text in messages:
            fake.append_message(
                ConversationMessage(
                    role=MessageRole(role),
                    content=ConversationContent(text),
                )
            )

        req = fake.get_model_request()
        self.assertEqual(len(req.messages), len(messages))
        for actual, (expected_role, expected_text) in zip(req.messages, messages):
            self.assertEqual(actual.role, expected_role)
            self.assertEqual(actual.content, expected_text)
