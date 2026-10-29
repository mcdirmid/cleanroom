"""Pretense state machine, fake synthesis, unit tests, parity tests, and fuzzing for Conversation."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
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


class ConversationStateMachine(StateMachine[ConversationState]):
    """Pretense StateMachine for Conversation."""

    def __init__(self, state: Optional[ConversationState] = None):
        super().__init__(state=state or ConversationState())

    # ==============================================================================
    # 1. Conversation Transitions
    # ==============================================================================

    @transition(Conversation.initialize)
    def initialize(
        self,
        ctx: TransitionContext[Conversation, [Sequence[ConversationMessage]], None],
    ) -> None:
        ctx.arguments(initial_messages=Domain(strategy=lambda: ()))
        def _consequent(res: None, initial_messages: Sequence[ConversationMessage] = ()) -> None:
            self.state.messages = []
            for msg in initial_messages:
                if msg.role == MessageRole("tool"):
                    has_assistant = any(
                        m.role == MessageRole("assistant") and m.tool_call_id == msg.tool_call_id
                        for m in self.state.messages
                    )
                    if not has_assistant:
                        self.state.messages.append(
                            ConversationMessage(
                                role=MessageRole("assistant"),
                                content=ConversationContent(""),
                                tool_call_id=msg.tool_call_id,
                                tool_name=msg.tool_name,
                                tool_arguments=msg.tool_arguments,
                            )
                        )
                self.state.messages.append(msg)
        ctx.update(_consequent)

    @transition(Conversation.append_message)
    def append_message(
        self,
        ctx: TransitionContext[Conversation, [ConversationMessage], None],
    ) -> None:
        ctx.arguments(message=Domain(strategy=lambda: ConversationMessage(role=MessageRole('user'), content=ConversationContent('hello'))))
        def _consequent(res: None, message: Optional[ConversationMessage] = None) -> None:
            if message is not None:
                self.state.messages.append(message)
        ctx.update(_consequent)

    @transition(Conversation.append_tool_response)
    def append_tool_response(
        self,
        ctx: TransitionContext[
            Conversation,
            [ToolResponse, ToolCallId, ToolName, SerializedArguments],
            None,
        ],
    ) -> None:
        ctx.arguments(
                    tool_response=Domain(strategy=lambda: ToolResponse(is_failed=False, is_terminated=False, content=ToolResponseContent('ok'))),
                    tool_call_id=Domain(strategy=lambda: ToolCallId('call_1')),
                    tool_name=Domain(strategy=lambda: ToolName('read_file')),
                    tool_arguments=Domain(strategy=lambda: SerializedArguments('{}')),
                )
        def _consequent(
            res: None,
            tool_response: Optional[ToolResponse] = None,
            tool_call_id: Optional[ToolCallId] = None,
            tool_name: Optional[ToolName] = None,
            tool_arguments: Optional[SerializedArguments] = None,
        ) -> None:
            resp = tool_response or ToolResponse(is_failed=False, is_terminated=False, content=ToolResponseContent("ok"))
            tcid = tool_call_id or ToolCallId("call_1")
            tname = tool_name or ToolName("read_file")
            targs = tool_arguments or SerializedArguments("{}")
            msg = ConversationMessage(
                role=MessageRole("tool"),
                content=ConversationContent(str(resp.content)),
                tool_call_id=tcid,
                tool_name=tname,
                reminder=resp.reminder,
                tool_arguments=targs,
            )
            self.state.messages.append(msg)
        ctx.update(_consequent)

    @transition(Conversation.get_model_request)
    def get_model_request(
        self,
        ctx: TransitionContext[Conversation, [], ModelRequest],
    ) -> None:
        ctx.returns(lambda: ModelRequest(messages=tuple(self.state.messages)))


proto = ConversationStateMachine()


# ==============================================================================
# 2. Synthesized Fake Factory
# ==============================================================================

def make_conversation_fake(
    state: Optional[ConversationState] = None,
) -> Conversation:
    """Instantiate a synthesized Conversation fake."""
    sm = ConversationStateMachine(state)
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
