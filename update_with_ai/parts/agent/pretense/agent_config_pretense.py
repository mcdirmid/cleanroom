"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for AgentConfig."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
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


proto = StateMachineProto[AgentConfigState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_config(): pass

@seed_config.arguments
def _(
    state: AgentConfigState,
    this: Any,
    conversation_limit: int | NotBoundType = NotBound,
    inject_followups: bool | NotBoundType = NotBound,
    is_step_mode: bool | NotBoundType = NotBound,
    is_startup_reads: bool | NotBoundType = NotBound,
    edit_delta_output: bool | NotBoundType = NotBound,
    supersede_arg_keep: int | NotBoundType = NotBound,
) -> Optional[Tuple[int, bool, bool, bool, bool, int]]:
    lim = 30 if isinstance(conversation_limit, NotBoundType) else conversation_limit
    inj = True if isinstance(inject_followups, NotBoundType) else inject_followups
    step = False if isinstance(is_step_mode, NotBoundType) else is_step_mode
    start = True if isinstance(is_startup_reads, NotBoundType) else is_startup_reads
    delta = True if isinstance(edit_delta_output, NotBoundType) else edit_delta_output
    keep = 50 if isinstance(supersede_arg_keep, NotBoundType) else supersede_arg_keep
    return (lim, inj, step, start, delta, keep)

@seed_config.provide
def _(
    state: AgentConfigState,
    this: Any,
    conversation_limit: int,
    inject_followups: bool,
    is_step_mode: bool,
    is_startup_reads: bool,
    edit_delta_output: bool,
    supersede_arg_keep: int,
    result: None = None,
) -> None:
    state.conversation_limit = conversation_limit
    state.inject_followups = inject_followups
    state.is_step_mode = is_step_mode
    state.is_startup_reads = is_startup_reads
    state.edit_delta_output = edit_delta_output
    state.supersede_arg_keep = supersede_arg_keep


# ==============================================================================
# 2. AgentConfig Interface Property Transitions
# ==============================================================================

@proto.transition(name="conversation_limit")
def conversation_limit(): pass

@conversation_limit.returns
def _(state: AgentConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[ConversationLimit]]:
    expected = ConversationLimit(state.conversation_limit)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(name="inject_followups")
def inject_followups(): pass

@inject_followups.returns
def _(state: AgentConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[bool]]:
    expected = state.inject_followups
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(name="is_step_mode")
def is_step_mode(): pass

@is_step_mode.returns
def _(state: AgentConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[bool]]:
    expected = state.is_step_mode
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(name="is_startup_reads")
def is_startup_reads(): pass

@is_startup_reads.returns
def _(state: AgentConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[bool]]:
    expected = state.is_startup_reads
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(name="edit_delta_output")
def edit_delta_output(): pass

@edit_delta_output.returns
def _(state: AgentConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[bool]]:
    expected = state.edit_delta_output
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(name="supersede_arg_keep")
def supersede_arg_keep(): pass

@supersede_arg_keep.returns
def _(state: AgentConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[SupersedeArgKeepLimit]]:
    expected = SupersedeArgKeepLimit(state.supersede_arg_keep)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


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
