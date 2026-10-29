"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for LoopGuard."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple, Union, cast
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
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


class LoopGuardStateMachine(StateMachine[LoopGuardState]):
    """Unified Pretense State Machine for LoopGuard."""

    def __init__(
        self,
        state: Optional[LoopGuardState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or LoopGuardState(), singletons=singletons)

    @transition.seeding(name="seed_guard_thresholds")
    def seed_guard_thresholds(
        self,
        ctx: TransitionContext[Any, [int, int], None],
    ) -> None:
        ctx.arguments(
                    reminder_threshold=Domain(strategy=lambda: 2),
                    failure_threshold=Domain(strategy=lambda: 4),
                )
        ctx.returns(lambda reminder_threshold=2, failure_threshold=4: None)
        ctx.update(lambda res, reminder_threshold=2, failure_threshold=4: (
            setattr(self.state, "reminder_threshold", int(reminder_threshold)),
            setattr(self.state, "failure_threshold", int(failure_threshold)),
        ))

    @transition(LoopGuard.evaluate)
    def evaluate(
        self,
        ctx: TransitionContext[LoopGuard, [tool_provider.ToolName | str, Optional[Mapping[Any, Any]]], Optional[Union[LoopReminder, LoopFailure]]],
    ) -> None:
        ctx.arguments(
                    tool_name=Domain(strategy=lambda: tool_provider.ToolName('read_file')),
                    arguments=Domain(strategy=lambda: {}),
                )
        def returns(tool_name: tool_provider.ToolName | str = "read_file", arguments: Optional[Mapping[Any, Any]] = None) -> Optional[Union[LoopReminder, LoopFailure]]:
            args = arguments or {}
            sig = f"{tool_name}:{sorted(str(k) + '=' + str(v) for k, v in args.items())}"
            new_count = self.state.consecutive_count + 1 if sig == self.state.last_signature else 1

            if new_count >= self.state.failure_threshold:
                return LoopFailure(
                    explanation=FailureExplanation(f"Tool {tool_name} repeated {new_count} times without forward progress.")
                )
            elif new_count >= self.state.reminder_threshold:
                return LoopReminder(
                    feedback=LoopFeedback(f"Warning: Tool {tool_name} repeated {new_count} times.")
                )
            return None

        ctx.returns(returns)

        def provide(res: Optional[Union[LoopReminder, LoopFailure]], tool_name: tool_provider.ToolName | str = "read_file", arguments: Optional[Mapping[Any, Any]] = None) -> None:
            args = arguments or {}
            sig = f"{tool_name}:{sorted(str(k) + '=' + str(v) for k, v in args.items())}"
            if sig == self.state.last_signature:
                self.state.consecutive_count += 1
            else:
                self.state.last_signature = sig
                self.state.consecutive_count = 1
        ctx.update(provide)

    @transition(LoopGuard.reset)
    def reset(
        self,
        ctx: TransitionContext[LoopGuard, [], None],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: None)
        ctx.update(lambda res: (
            setattr(self.state, "consecutive_count", 0),
            setattr(self.state, "last_signature", ""),
        ))


proto = LoopGuardStateMachine()


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
