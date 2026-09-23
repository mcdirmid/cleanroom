"""Unit tests for loop_guard_impl aligned with grounding specifications."""

import unittest
from update_with_ai.parts.loop.lib.loop_guard import (
    LoopFailure,
    LoopGuard,
    LoopReminder,
)
from update_with_ai.parts.loop.lib.loop_guard_impl import (
    LoopGuard as LoopGuardImpl,
    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.sandbox.lib.tool_provider import (
    STRING_PARAMETER_TYPE,
    ActualParameterBindings,
    Parameter,
)


class LoopGuardImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.param = Parameter(
            name="file_name",
            description="file name",
            parameter_converter=STRING_PARAMETER_TYPE,
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
        with enter_phase(agent_session, registry=self.registry) as scope:
            guard = scope.get_singleton(LoopGuard)
            bindings = ActualParameterBindings(bindings={(self.param, "a.py")})

            # Call 1 -> None
            # Requirement: [LoopGuard] A loop guard evaluates consecutive executions of identical tools and edits.
            self.assertIsNone(guard.record_tool_execution("view_file", bindings))

            # Call 2 -> LoopReminder
            # Requirement: Produces a loop reminder advising the agent that no new information will be revealed by repeated tool execution until session read-write files are updated and that repeating the tool call without modifying files will trigger fatal loop termination when consecutive identical tool executions reach the reminder threshold of two repetitions.
            # Requirement: [LoopGuard] Consecutive repetitions reaching a warning threshold produce a loop reminder.
            res2 = guard.record_tool_execution("view_file", bindings)
            self.assertIsInstance(res2, LoopReminder)
            assert isinstance(res2, LoopReminder)
            self.assertTrue(res2.feedback)
            self.assertIn(
                "no new information", res2.feedback.lower()
            )

            # Call 3 & 4 -> LoopReminder
            res3 = guard.record_tool_execution("view_file", bindings)
            self.assertIsInstance(res3, LoopReminder)
            res4 = guard.record_tool_execution("view_file", bindings)
            self.assertIsInstance(res4, LoopReminder)

            # Call 5 -> LoopFailure
            # Requirement: Produces a loop failure communicating session failure when consecutive identical tool executions reach the fatal threshold.
            # Requirement: [LoopGuard] Consecutive repetitions reaching a fatal threshold produce a loop failure communicating session termination.
            res5 = guard.record_tool_execution("view_file", bindings)
            self.assertIsInstance(res5, LoopFailure)

    def test_consecutive_edits_threshold(self) -> None:
        """CUJ: Tracking consecutive edits to the same target."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            guard = scope.get_singleton(LoopGuard)
            bindings = ActualParameterBindings(bindings={(self.param, "target.py")})

            # Call 1 -> None
            self.assertIsNone(
                guard.record_tool_execution("replace_file_content", bindings)
            )
            # Call 2 -> LoopReminder at threshold of 2
            # Requirement: Produces a loop reminder at the reminder threshold of two repetitions when consecutive edits target the same file and line range.
            self.assertIsInstance(
                guard.record_tool_execution("replace_file_content", bindings),
                LoopReminder,
            )
            guard.record_tool_execution("replace_file_content", bindings)
            guard.record_tool_execution("replace_file_content", bindings)
            # Requirement: Produces a loop failure at the fatal threshold when consecutive edits target the same file and line range.
            self.assertIsInstance(
                guard.record_tool_execution("replace_file_content", bindings),
                LoopFailure,
            )

    def test_consecutive_edits_same_line_range_different_content(self) -> None:
        """CUJ: Consecutive edits to the same file and line range with different content trigger loop guard."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            guard = scope.get_singleton(LoopGuard)
            path_param = Parameter(
                name="path",
                description="path",
                parameter_converter=STRING_PARAMETER_TYPE,
                is_required=True,
            )
            start_param = Parameter(
                name="start_line",
                description="start",
                parameter_converter=STRING_PARAMETER_TYPE,
                is_required=True,
            )
            end_param = Parameter(
                name="end_line",
                description="end",
                parameter_converter=STRING_PARAMETER_TYPE,
                is_required=True,
            )
            content_param = Parameter(
                name="target_content",
                description="content",
                parameter_converter=STRING_PARAMETER_TYPE,
                is_required=True,
            )

            bindings1 = ActualParameterBindings(
                bindings={
                    (path_param, "foo.py"),
                    (start_param, 10),
                    (end_param, 20),
                    (content_param, "content A"),
                }
            )
            bindings2 = ActualParameterBindings(
                bindings={
                    (path_param, "foo.py"),
                    (start_param, 10),
                    (end_param, 20),
                    (content_param, "content B"),
                }
            )

            # Call 1 -> None
            self.assertIsNone(
                guard.record_tool_execution("replace_file_content", bindings1)
            )

            # Call 2 with different content but same file & range -> LoopReminder
            # Requirement: Produces a loop reminder at the reminder threshold of two repetitions when consecutive edits target the same file and line range.
            res = guard.record_tool_execution("replace_file_content", bindings2)
            self.assertIsInstance(res, LoopReminder)

            guard.record_tool_execution("replace_file_content", bindings1)
            guard.record_tool_execution("replace_file_content", bindings2)

            # Call 5 -> LoopFailure
            # Requirement: Produces a loop failure at the fatal threshold when consecutive edits target the same file and line range.
            fatal = guard.record_tool_execution("replace_file_content", bindings1)
            self.assertIsInstance(fatal, LoopFailure)

    def test_record_progress_resets_counters(self) -> None:
        """CUJ: Forward progress resets consecutive repetition counters."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            guard = scope.get_singleton(LoopGuard)
            bindings = ActualParameterBindings(bindings={(self.param, "a.py")})

            # 2 calls reaching reminder
            self.assertIsNone(guard.record_tool_execution("view_file", bindings))
            self.assertIsInstance(
                guard.record_tool_execution("view_file", bindings), LoopReminder
            )

            # Reset progress
            # Requirement: A tool execution demonstrating forward progress resets repetition counters in the loop guard.
            # Requirement: [LoopGuard] Executing a tool that demonstrates progress clears repetition tracking in the loop guard.
            guard.record_progress()

            # Next call is treated as first call
            self.assertIsNone(guard.record_tool_execution("view_file", bindings))

    def test_distinct_tool_calls_reset_counter(self) -> None:
        """CUJ: Interleaving distinct calls prevents reaching reminder threshold."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            guard = scope.get_singleton(LoopGuard)
            bindings1 = ActualParameterBindings(bindings={(self.param, "a.py")})
            bindings2 = ActualParameterBindings(bindings={(self.param, "b.py")})

            self.assertIsNone(guard.record_tool_execution("view_file", bindings1))
            # Different arguments prevents reaching threshold of 2
            self.assertIsNone(guard.record_tool_execution("view_file", bindings2))
            # Again with bindings1
            self.assertIsNone(guard.record_tool_execution("view_file", bindings1))
            # Again with bindings2
            self.assertIsNone(guard.record_tool_execution("view_file", bindings2))

    def test_edit_tool_without_file_name(self) -> None:
        """CUJ: Edit tool execution with omitted file parameter falls back to general parameter tracking."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            guard = scope.get_singleton(LoopGuard)
            empty_bindings = ActualParameterBindings(bindings=set())
            # Requirement: [LoopGuard] A loop guard evaluates consecutive executions of identical tools and edits.
            self.assertIsNone(
                guard.record_tool_execution("replace_file_content", empty_bindings)
            )
            res = guard.record_tool_execution("replace_file_content", empty_bindings)
            self.assertIsInstance(res, LoopReminder)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
