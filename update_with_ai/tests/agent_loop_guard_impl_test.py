"""Unit tests for agent_loop_guard_impl aligned with grounding specifications."""

import unittest
from lib.agent_loop_guard import (
    LoopFailure,
    LoopGuard,
    LoopReminder,
)
from lib.agent_loop_guard_impl import (
    LoopGuard as LoopGuardImpl,
    __initialize__,
)
from lib.lifecycle import LifecycleRegistry, enter_phase
from lib.tool_provider import ActualParameterBindings, Parameter, String, WireType


class DummyConverter:
    @property
    def actual_type(self) -> type:
        return str

    @property
    def wire_type(self) -> WireType:
        return String()

    def convert(self, wire_value: object) -> str:
        return str(wire_value)


class AgentLoopGuardImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.param = Parameter(
            name="file_name",
            description="file name",
            parameter_converter=DummyConverter(),
            is_required=True,
        )

    def test_dataclasses(self) -> None:
        """CUJ: Instantiating LoopReminder and LoopFailure records."""
        reminder = LoopReminder(feedback="too many retries")
        self.assertEqual(reminder.feedback, "too many retries")

        failure = LoopFailure(explanation="loop fatal error")
        self.assertEqual(failure.explanation, "loop fatal error")

    def test_thresholds_reminder_and_fatal(self) -> None:
        """CUJ: Tracking consecutive identical tool calls to reminder and fatal thresholds."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            guard = scope.get_singleton(LoopGuard)
            bindings = ActualParameterBindings(bindings={(self.param, "a.py")})

            # Call 1 & 2 -> None
            # Requirement: The loop guard tracks consecutive executions of identical tools with identical arguments.
            # Requirement: [LoopGuard] A loop guard evaluates consecutive executions of identical tools and edits.
            self.assertIsNone(guard.record_tool_execution("read_file", bindings))
            self.assertIsNone(guard.record_tool_execution("read_file", bindings))

            # Call 3 & 4 -> LoopReminder
            # Requirement: The loop guard produces a loop reminder when consecutive identical tool executions reach the reminder threshold.
            # Requirement: [LoopGuard] Consecutive repetitions reaching a warning threshold produce a loop reminder.
            res3 = guard.record_tool_execution("read_file", bindings)
            self.assertIsInstance(res3, LoopReminder)
            res4 = guard.record_tool_execution("read_file", bindings)
            self.assertIsInstance(res4, LoopReminder)

            # Call 5 -> LoopFailure
            # Requirement: The loop guard produces a loop failure communicating session failure when consecutive identical tool executions reach the fatal threshold.
            # Requirement: [LoopGuard] Consecutive repetitions reaching a fatal threshold produce a loop failure communicating session termination.
            res5 = guard.record_tool_execution("read_file", bindings)
            self.assertIsInstance(res5, LoopFailure)

    def test_consecutive_edits_threshold(self) -> None:
        """CUJ: Tracking consecutive edits to the same file and line range."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            guard = scope.get_singleton(LoopGuard)
            file_param = Parameter(name="target_file", description="", parameter_converter=DummyConverter(), is_required=True)
            start_param = Parameter(name="start_line", description="", parameter_converter=DummyConverter(), is_required=True)
            end_param = Parameter(name="end_line", description="", parameter_converter=DummyConverter(), is_required=True)
            bindings = ActualParameterBindings(bindings={(file_param, "a.py"), (start_param, "10"), (end_param, "20")})

            guard.record_tool_execution("replace_file_content", bindings)
            guard.record_tool_execution("replace_file_content", bindings)
            # Requirement: The loop guard tracks consecutive edits to the same file and line range, producing a reminder at the reminder threshold and a loop failure at the fatal threshold.
            self.assertIsInstance(guard.record_tool_execution("replace_file_content", bindings), LoopReminder)
            guard.record_tool_execution("replace_file_content", bindings)
            self.assertIsInstance(guard.record_tool_execution("replace_file_content", bindings), LoopFailure)

    def test_record_progress_resets_counters(self) -> None:
        """CUJ: Forward progress resets consecutive repetition counters."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            guard = scope.get_singleton(LoopGuard)
            bindings = ActualParameterBindings(bindings={(self.param, "a.py")})

            # 3 calls reaching reminder
            guard.record_tool_execution("read_file", bindings)
            guard.record_tool_execution("read_file", bindings)
            self.assertIsInstance(guard.record_tool_execution("read_file", bindings), LoopReminder)

            # Reset progress
            # Requirement: A tool execution demonstrating forward progress resets repetition counters in the loop guard.
            # Requirement: [LoopGuard] Executing a tool that demonstrates progress clears repetition tracking in the loop guard.
            guard.record_progress()

            # Next call is treated as first call
            self.assertIsNone(guard.record_tool_execution("read_file", bindings))

    def test_distinct_tool_calls_reset_counter(self) -> None:
        """CUJ: Interleaving distinct calls prevents reaching reminder threshold."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            guard = scope.get_singleton(LoopGuard)
            bindings1 = ActualParameterBindings(bindings={(self.param, "a.py")})
            bindings2 = ActualParameterBindings(bindings={(self.param, "b.py")})

            self.assertIsNone(guard.record_tool_execution("read_file", bindings1))
            self.assertIsNone(guard.record_tool_execution("read_file", bindings1))
            # Different arguments
            self.assertIsNone(guard.record_tool_execution("read_file", bindings2))
            # Again with bindings1
            self.assertIsNone(guard.record_tool_execution("read_file", bindings1))


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
