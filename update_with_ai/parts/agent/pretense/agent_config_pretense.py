"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for AgentConfig."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from update_with_ai.parts.agent.lib.agent_config import (
    AgentConfig,
    ConversationLimit,
    SupersedeArgKeepLimit,
)


@dataclass
class AgentConfigState:
    """Canonical model state for AgentConfig."""
    conversation_limit: int = 30
    inject_followups: bool = True
    is_step_mode: bool = False
    is_startup_reads: bool = True
    edit_delta_output: bool = True
    supersede_arg_keep: int = 50


class AgentConfigStateMachine(StateMachine[AgentConfigState]):
    """Unified Pretense State Machine for AgentConfig."""

    def __init__(
        self,
        state: Optional[AgentConfigState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or AgentConfigState(), singletons=singletons)

    @transition.seeding(name="seed_config")
    def seed_config(
        self,
        ctx: TransitionContext[Any, [int, bool, bool, bool, bool, int], None],
    ) -> None:
        ctx.arguments(
                    conversation_limit=Domain(strategy=lambda: 30),
                    inject_followups=Domain(strategy=lambda: True),
                    is_step_mode=Domain(strategy=lambda: False),
                    is_startup_reads=Domain(strategy=lambda: True),
                    edit_delta_output=Domain(strategy=lambda: True),
                    supersede_arg_keep=Domain(strategy=lambda: 50),
                )
        ctx.returns(lambda conversation_limit=30, inject_followups=True, is_step_mode=False, is_startup_reads=True, edit_delta_output=True, supersede_arg_keep=50: None)
        ctx.update(lambda res, conversation_limit=30, inject_followups=True, is_step_mode=False, is_startup_reads=True, edit_delta_output=True, supersede_arg_keep=50: (
            setattr(self.state, "conversation_limit", int(conversation_limit)),
            setattr(self.state, "inject_followups", bool(inject_followups)),
            setattr(self.state, "is_step_mode", bool(is_step_mode)),
            setattr(self.state, "is_startup_reads", bool(is_startup_reads)),
            setattr(self.state, "edit_delta_output", bool(edit_delta_output)),
            setattr(self.state, "supersede_arg_keep", int(supersede_arg_keep)),
        ))

    @transition(name="conversation_limit")
    def conversation_limit(
        self,
        ctx: TransitionContext[AgentConfig, [], ConversationLimit],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: ConversationLimit(self.state.conversation_limit))
        ctx.update(lambda res: None)

    @transition(name="inject_followups")
    def inject_followups(
        self,
        ctx: TransitionContext[AgentConfig, [], bool],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: self.state.inject_followups)
        ctx.update(lambda res: None)

    @transition(name="is_step_mode")
    def is_step_mode(
        self,
        ctx: TransitionContext[AgentConfig, [], bool],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: self.state.is_step_mode)
        ctx.update(lambda res: None)

    @transition(name="is_startup_reads")
    def is_startup_reads(
        self,
        ctx: TransitionContext[AgentConfig, [], bool],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: self.state.is_startup_reads)
        ctx.update(lambda res: None)

    @transition(name="edit_delta_output")
    def edit_delta_output(
        self,
        ctx: TransitionContext[AgentConfig, [], bool],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: self.state.edit_delta_output)
        ctx.update(lambda res: None)

    @transition(name="supersede_arg_keep")
    def supersede_arg_keep(
        self,
        ctx: TransitionContext[AgentConfig, [], SupersedeArgKeepLimit],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: SupersedeArgKeepLimit(self.state.supersede_arg_keep))
        ctx.update(lambda res: None)


proto = AgentConfigStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_agent_config_fake(state: Optional[AgentConfigState] = None) -> AgentConfig:
    """Instantiate a synthesized AgentConfig fake with Pretense."""
    st = state or AgentConfigState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(AgentConfig)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestAgentConfigUnit(unittest.TestCase):
    """Unit tests verifying AgentConfig fake synthesis and protocol access."""

    def test_default_config_properties(self) -> None:
        fake = make_agent_config_fake()
        self.assertEqual(fake.conversation_limit, 30)
        self.assertTrue(fake.inject_followups)
        self.assertFalse(fake.is_step_mode)
        self.assertTrue(fake.is_startup_reads)
        self.assertTrue(fake.edit_delta_output)
        self.assertEqual(fake.supersede_arg_keep, 50)

    def test_seeded_config_properties(self) -> None:
        state = AgentConfigState()
        sm = proto.make_state_machine(state)
        sm.seed_config(
            conversation_limit=15,
            inject_followups=False,
            is_step_mode=True,
            is_startup_reads=False,
            edit_delta_output=False,
            supersede_arg_keep=25,
        )
        fake = sm.as_fake(AgentConfig)
        self.assertEqual(fake.conversation_limit, 15)
        self.assertFalse(fake.inject_followups)
        self.assertTrue(fake.is_step_mode)
        self.assertFalse(fake.is_startup_reads)
        self.assertFalse(fake.edit_delta_output)
        self.assertEqual(fake.supersede_arg_keep, 25)


# ==============================================================================
# 5. Hypothesis Fuzzing
# ==============================================================================

class TestAgentConfigFuzz(unittest.TestCase):
    """Property fuzz tests verifying AgentConfig invariants across arbitrary seeds."""

    @settings(max_examples=30)
    @given(
        conversation_limit=st.integers(min_value=1, max_value=1000),
        inject_followups=st.booleans(),
        is_step_mode=st.booleans(),
        is_startup_reads=st.booleans(),
        edit_delta_output=st.booleans(),
        supersede_arg_keep=st.integers(min_value=0, max_value=500),
    )
    def test_config_invariants_under_fuzz(
        self,
        conversation_limit: int,
        inject_followups: bool,
        is_step_mode: bool,
        is_startup_reads: bool,
        edit_delta_output: bool,
        supersede_arg_keep: int,
    ) -> None:
        state = AgentConfigState(
            conversation_limit=conversation_limit,
            inject_followups=inject_followups,
            is_step_mode=is_step_mode,
            is_startup_reads=is_startup_reads,
            edit_delta_output=edit_delta_output,
            supersede_arg_keep=supersede_arg_keep,
        )
        fake = make_agent_config_fake(state)
        self.assertEqual(fake.conversation_limit, conversation_limit)
        self.assertEqual(fake.inject_followups, inject_followups)
        self.assertEqual(fake.is_step_mode, is_step_mode)
        self.assertEqual(fake.is_startup_reads, is_startup_reads)
        self.assertEqual(fake.edit_delta_output, edit_delta_output)
        self.assertEqual(fake.supersede_arg_keep, supersede_arg_keep)
