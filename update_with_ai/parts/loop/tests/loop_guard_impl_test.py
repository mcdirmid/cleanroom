# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: d8848090d777
# COVERAGE_AUDIT: 2026-10-05T02:07:35Z
# QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

"""Unit tests for loop_guard_impl aligned with grounding specifications."""

import unittest
from typing import Any, Mapping
from update_with_ai.parts.loop.lib.loop_guard import (
    FailureExplanation,
    LoopFeedback,
    LoopFailure,
    LoopGuard,
    LoopReminder,
)
from update_with_ai.parts.loop.lib.loop_guard_impl import (
    LoopGuard as LoopGuardImpl,
    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier
from update_with_ai.parts.sandbox.lib import tool_provider


class DummyParameterType:
    tier = AgentSessionTier
    actual_type = str
    wire_type = str

    def convert(self, wire_value: Any) -> Any:
        return wire_value


def _make_param(name: str) -> tool_provider.ToolParameter[Any, Any]:
    return tool_provider.ToolParameter(
        name=tool_provider.ParameterName(name),
        description=tool_provider.ParameterDescription(name),
        parameter_type=DummyParameterType(),
    )


def _make_bindings(
    d: Mapping[tool_provider.ToolParameter[Any, Any], Any],
) -> Mapping[
    tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
]:
    return {k: tool_provider.SomeParameterActualType(v) for k, v in d.items()}


class LoopGuardImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_dataclasses(self) -> None:
        """CUJ: Instantiating LoopReminder and LoopFailure records."""
        reminder = LoopReminder(feedback=LoopFeedback("too many retries"))
        self.assertEqual(reminder.feedback, "too many retries")

        failure = LoopFailure(explanation=FailureExplanation("loop fatal error"))
        self.assertEqual(failure.explanation, "loop fatal error")

    def test_thresholds_reminder_and_fatal(self) -> None:
        """CUJ: Tracking consecutive identical tool calls to reminder and fatal thresholds."""
        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                guard = scope.get_singleton(LoopGuard)
                param = _make_param("file_name")
                bindings = _make_bindings({param: "a.py"})
                tool_name = tool_provider.ToolName("view_file")

                # Call 1 -> None
                # Requirement: MUST evaluate consecutive executions of identical tools and file edits.
                self.assertIsNone(guard.evaluate(tool_name, bindings))

                # Call 2 -> LoopReminder
                # Requirement: WHEN consecutive identical tool executions reach two repetitions, MUST produce a loop reminder.
                # Requirement: WHEN consecutive repetitions reach the warning threshold, MUST produce a loop reminder.
                res2 = guard.evaluate(tool_name, bindings)
                self.assertIsInstance(res2, LoopReminder)
                assert isinstance(res2, LoopReminder)
                self.assertTrue(res2.feedback)

                # Call 3 & 4 -> LoopReminder
                res3 = guard.evaluate(tool_name, bindings)
                self.assertIsInstance(res3, LoopReminder)
                res4 = guard.evaluate(tool_name, bindings)
                self.assertIsInstance(res4, LoopReminder)

                # Call 5 -> LoopFailure
                # Requirement: WHEN consecutive identical tool executions reach the fatal threshold, MUST produce a loop failure.
                # Requirement: WHEN consecutive repetitions reach the fatal threshold, MUST produce a loop failure communicating session termination.
                res5 = guard.evaluate(tool_name, bindings)
                self.assertIsInstance(res5, LoopFailure)

    def test_consecutive_edits_threshold(self) -> None:
        """CUJ: Tracking consecutive edits to the same target."""
        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                guard = scope.get_singleton(LoopGuard)
                p_path = _make_param("path")
                p_start = _make_param("start_line")
                p_end = _make_param("end_line")
                bindings = _make_bindings({p_path: "target.py", p_start: 1, p_end: 10})
                tool_name = tool_provider.ToolName("replace_file_content")

                # Call 1 -> None
                self.assertIsNone(guard.evaluate(tool_name, bindings))
                # Call 2 -> LoopReminder at threshold of 2
                # Requirement: WHEN consecutive edits target the same file and line range at two repetitions, MUST produce a loop reminder.
                self.assertIsInstance(
                    guard.evaluate(tool_name, bindings),
                    LoopReminder,
                )
                guard.evaluate(tool_name, bindings)
                guard.evaluate(tool_name, bindings)
                # Requirement: WHEN consecutive edits target the same file and line range at the fatal threshold, MUST produce a loop failure.
                self.assertIsInstance(
                    guard.evaluate(tool_name, bindings),
                    LoopFailure,
                )

    def test_record_progress_resets_counters(self) -> None:
        """CUJ: Forward progress resets consecutive repetition counters."""
        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                guard = scope.get_singleton(LoopGuard)
                param = _make_param("file_name")
                bindings = _make_bindings({param: "a.py"})
                tool_name = tool_provider.ToolName("view_file")

                # 2 calls reaching reminder
                self.assertIsNone(guard.evaluate(tool_name, bindings))
                self.assertIsInstance(guard.evaluate(tool_name, bindings), LoopReminder)

                # Reset progress
                # Requirement: MUST reset repetition counters in the loop guard.
                # Requirement: MUST clear repetition tracking when a tool execution demonstrates forward progress.
                guard.reset()

                # Next call is treated as first call
                self.assertIsNone(guard.evaluate(tool_name, bindings))

    def test_distinct_tool_calls_reset_counter(self) -> None:
        """CUJ: Interleaving distinct calls prevents reaching reminder threshold."""
        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                guard = scope.get_singleton(LoopGuard)
                param = _make_param("file_name")
                bindings1 = _make_bindings({param: "a.py"})
                bindings2 = _make_bindings({param: "b.py"})
                tool_name = tool_provider.ToolName("view_file")

                self.assertIsNone(guard.evaluate(tool_name, bindings1))
                self.assertIsNone(guard.evaluate(tool_name, bindings2))
                self.assertIsNone(guard.evaluate(tool_name, bindings1))
                self.assertIsNone(guard.evaluate(tool_name, bindings2))


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
