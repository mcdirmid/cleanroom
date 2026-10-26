"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for LoopGuard."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple, Union, cast
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.loop.lib import guard, guard_impl
from update_with_ai.parts.loop.lib.guard import (
    FailureExplanation,
    LoopFailure,
    LoopFeedback,
    LoopGuard,
    LoopReminder,
)
from update_with_ai.parts.sandbox.lib import tool_provider
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.session import agent_session


@dataclass
class LoopGuardState:
    """Canonical model state for LoopGuard."""
    consecutive_count: int = 0
    last_signature: str = ""
    reminder_threshold: int = 2
    failure_threshold: int = 4


proto = StateMachineProto[LoopGuardState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_guard_thresholds(): pass

@seed_guard_thresholds.arguments
def _(
    state: LoopGuardState,
    this: Any,
    reminder_threshold: int | NotBoundType = NotBound,
    failure_threshold: int | NotBoundType = NotBound,
) -> Optional[Tuple[int, int]]:
    r = 2 if isinstance(reminder_threshold, NotBoundType) else int(reminder_threshold)
    f = 4 if isinstance(failure_threshold, NotBoundType) else int(failure_threshold)
    return (r, f)

@seed_guard_thresholds.provide
def _(
    state: LoopGuardState,
    this: Any,
    reminder_threshold: int,
    failure_threshold: int,
    result: None = None,
) -> None:
    state.reminder_threshold = reminder_threshold
    state.failure_threshold = failure_threshold


# ==============================================================================
# 2. LoopGuard Transitions
# ==============================================================================

@proto.transition(LoopGuard.evaluate)
def evaluate(): pass

@evaluate.arguments
def _(
    state: LoopGuardState,
    this: Any,
    tool_name: tool_provider.ToolName | str | NotBoundType = NotBound,
    arguments: Optional[Mapping[Any, Any]] | NotBoundType = NotBound,
) -> Optional[Tuple[tool_provider.ToolName, Mapping[Any, Any]]]:
    tn = tool_provider.ToolName("read_file") if isinstance(tool_name, NotBoundType) else tool_provider.ToolName(str(tool_name))
    args: Mapping[Any, Any] = {} if isinstance(arguments, NotBoundType) or arguments is None else arguments
    return (tn, args)

@evaluate.returns
def _(
    state: LoopGuardState,
    this: Any,
    tool_name: tool_provider.ToolName,
    arguments: Mapping[Any, Any],
    outcome: object = NotBound,
) -> Optional[Outcome[Optional[Union[LoopReminder, LoopFailure]]]]:
    sig = f"{tool_name}:{sorted(str(k) + '=' + str(v) for k, v in arguments.items())}"
    if sig == state.last_signature:
        new_count = state.consecutive_count + 1
    else:
        new_count = 1

    if new_count >= state.failure_threshold:
        expected: Optional[Union[LoopReminder, LoopFailure]] = LoopFailure(
            explanation=FailureExplanation(f"Tool {tool_name} repeated {new_count} times without forward progress.")
        )
    elif new_count >= state.reminder_threshold:
        expected = LoopReminder(
            feedback=LoopFeedback(f"Warning: Tool {tool_name} repeated {new_count} times.")
        )
    else:
        expected = None

    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None

@evaluate.provide
def _(
    state: LoopGuardState,
    this: Any,
    tool_name: tool_provider.ToolName,
    arguments: Mapping[Any, Any],
    result: Optional[Union[LoopReminder, LoopFailure]],
) -> None:
    sig = f"{tool_name}:{sorted(str(k) + '=' + str(v) for k, v in arguments.items())}"
    if sig == state.last_signature:
        state.consecutive_count += 1
    else:
        state.last_signature = sig
        state.consecutive_count = 1


@proto.transition(LoopGuard.reset)
def reset(): pass

@reset.arguments
def _(state: LoopGuardState, this: Any) -> Optional[Tuple[()]]:
    return ()

@reset.provide
def _(state: LoopGuardState, this: Any, result: None = None) -> None:
    state.consecutive_count = 0
    state.last_signature = ""


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_loop_guard_fake(state: Optional[LoopGuardState] = None) -> LoopGuard:
    """Instantiate a synthesized LoopGuard fake."""
    st = state or LoopGuardState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(LoopGuard)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestLoopGuardUnit(unittest.TestCase):
    """Unit tests for synthesized LoopGuard fake."""

    def setUp(self) -> None:
        self.state = LoopGuardState(reminder_threshold=2, failure_threshold=4)
        self.fake = make_loop_guard_fake(self.state)

    def test_progressive_repetition_warning_and_failure(self) -> None:
        tool = tool_provider.ToolName("read_file")
        args = cast(Any, {"path": "demo.py"})

        # Attempt 1: Normal
        res1 = self.fake.evaluate(tool, args)
        self.assertIsNone(res1)

        # Attempt 2: Reminder threshold met
        res2 = self.fake.evaluate(tool, args)
        self.assertIsInstance(res2, LoopReminder)

        # Attempt 3: Reminder persists
        res3 = self.fake.evaluate(tool, args)
        self.assertIsInstance(res3, LoopReminder)

        # Attempt 4: Failure threshold met
        res4 = self.fake.evaluate(tool, args)
        self.assertIsInstance(res4, LoopFailure)

    def test_reset_clears_consecutive_repetition(self) -> None:
        tool = tool_provider.ToolName("check_files")
        self.fake.evaluate(tool, cast(Any, {}))
        self.fake.evaluate(tool, cast(Any, {}))
        self.assertEqual(self.state.consecutive_count, 2)

        self.fake.reset()
        self.assertEqual(self.state.consecutive_count, 0)
        self.assertEqual(self.state.last_signature, "")


class _MockEditingTool:
    tier = agent_session
    name = tool_provider.ToolName("custom_editor")
    path_parameter = "file_path"
    start_line_parameter = "start_line"
    end_line_parameter = "end_line"


class TestLoopGuardReal(unittest.TestCase):
    """Direct verification of the real LoopGuard implementation covering repetition tracking."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        guard_impl.__initialize__(self.registry)
        try:
            from update_with_ai.parts.sandbox.lib import file_editor
            self.registry.register_instance(
                _MockEditingTool(),
                keys=[file_editor.EditingTool],
                tier=agent_session,
            )
        except Exception:
            pass

    def test_thresholds_reminder_and_fatal(self) -> None:
        with enter_phase("system", registry=self.registry):
            with enter_phase(agent_session, registry=self.registry) as scope:
                real_guard = scope.get_singleton(LoopGuard)
                tool_name = tool_provider.ToolName("view_file")
                bindings = cast(Any, {"file_name": "a.py"})

                # Call 1 -> None
                # Edit call without target file hits line 84
                self.assertIsNone(real_guard.evaluate(tool_name, cast(Any, {})))

                self.assertIsNone(real_guard.evaluate(tool_name, bindings))

                # Call 2 -> LoopReminder
                res2 = real_guard.evaluate(tool_name, bindings)
                self.assertIsInstance(res2, LoopReminder)

                # Call 3 & 4 -> LoopFailure
                real_guard.evaluate(tool_name, bindings)
                res4 = real_guard.evaluate(tool_name, bindings)
                self.assertIsInstance(res4, LoopFailure)

    def test_consecutive_edits_tracking(self) -> None:
        with enter_phase("system", registry=self.registry):
            with enter_phase(agent_session, registry=self.registry) as scope:
                real_guard = scope.get_singleton(LoopGuard)
                tool_name = tool_provider.ToolName("custom_editor")
                bindings = cast(Any, {"file_path": "a.py", "start_line": 1, "end_line": 10})

                # Edit call without target file hits line 84
                self.assertIsNone(real_guard.evaluate(tool_name, cast(Any, {})))

                self.assertIsNone(real_guard.evaluate(tool_name, bindings))
                res2 = real_guard.evaluate(tool_name, bindings)
                self.assertIsInstance(res2, LoopReminder)

                real_guard.evaluate(tool_name, bindings)
                res4 = real_guard.evaluate(tool_name, bindings)
                self.assertIsInstance(res4, LoopFailure)

    def test_reset_progress_resets_counter(self) -> None:
        with enter_phase("system", registry=self.registry):
            with enter_phase(agent_session, registry=self.registry) as scope:
                real_guard = scope.get_singleton(LoopGuard)
                tool_name = tool_provider.ToolName("view_file")
                bindings = cast(Any, {"file_name": "a.py"})

                # Edit call without target file hits line 84
                self.assertIsNone(real_guard.evaluate(tool_name, cast(Any, {})))

                self.assertIsNone(real_guard.evaluate(tool_name, bindings))
                self.assertIsInstance(real_guard.evaluate(tool_name, bindings), LoopReminder)

                real_guard.reset()
                # Edit call without target file hits line 84
                self.assertIsNone(real_guard.evaluate(tool_name, cast(Any, {})))

                self.assertIsNone(real_guard.evaluate(tool_name, bindings))


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestLoopGuardFuzz(unittest.TestCase):
    """Property fuzz testing for LoopGuard."""

    @settings(max_examples=30)
    @given(
        repeats=st.integers(min_value=1, max_value=8),
        reminder=st.integers(min_value=2, max_value=3),
        failure=st.integers(min_value=4, max_value=6),
    )
    def test_threshold_monotonicity(self, repeats: int, reminder: int, failure: int) -> None:
        state = LoopGuardState(reminder_threshold=reminder, failure_threshold=failure)
        fake = make_loop_guard_fake(state)
        tool = tool_provider.ToolName("test_tool")
        args = cast(Any, {"arg": "val"})

        for i in range(1, repeats + 1):
            out = fake.evaluate(tool, args)
            if i >= failure:
                self.assertIsInstance(out, LoopFailure)
            elif i >= reminder:
                self.assertIsInstance(out, LoopReminder)
            else:
                self.assertIsNone(out)
