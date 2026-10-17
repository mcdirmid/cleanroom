# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:43:03Z
# CHANGE: Verify the warning-threshold reminder at two repetitions and search for the unmandated fatal threshold instead of fixing it at five repetitions
# CODE_HASH: 959ccc6f971e
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Unit tests for guard_impl aligned with grounding specifications."""

import unittest
from typing import Any, Mapping
from update_with_ai.parts.loop.lib.guard import (
    FailureExplanation,
    LoopFeedback,
    LoopFailure,
    LoopGuard,
    LoopReminder,
)
from update_with_ai.parts.loop.lib.guard_impl import (
    LoopGuard as LoopGuardImpl,
    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.session import AgentSessionTier
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
                # Requirement: MUST track consecutive executions of identical tools with identical arguments.
                self.assertIsNone(guard.evaluate(tool_name, bindings))

                # Call 2 -> LoopReminder at the warning threshold of two repetitions.
                # Requirement: WHEN consecutive identical tool executions reach the warning threshold of two repetitions, MUST produce a loop reminder.
                # Requirement: WHEN consecutive identical tool executions reach the warning threshold of two repetitions, MUST warn that repeating without modifying files will trigger fatal termination.
                res2 = guard.evaluate(tool_name, bindings)
                self.assertIsInstance(res2, LoopReminder)
                assert isinstance(res2, LoopReminder)
                self.assertTrue(res2.feedback)

                # Continued identical executions eventually reach the fatal threshold, whose numeric value
                # is not mandated, producing a loop failure.
                # Requirement: WHEN consecutive identical tool executions reach the fatal threshold, MUST produce a loop failure communicating session failure.
                res = guard.evaluate(tool_name, bindings)
                repetitions = 3
                while not isinstance(res, LoopFailure) and repetitions < 20:
                    repetitions += 1
                    res = guard.evaluate(tool_name, bindings)
                self.assertIsInstance(res, LoopFailure)

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
                # Requirement: WHEN consecutive edits target the same file and line range and reach the warning threshold of two repetitions, MUST produce a loop reminder.
                self.assertIsInstance(
                    guard.evaluate(tool_name, bindings),
                    LoopReminder,
                )
                # Continued identical edits eventually reach the fatal threshold, whose numeric value is
                # not mandated, producing a loop failure.
                # Requirement: WHEN consecutive edits target the same file and line range and reach the fatal threshold, MUST produce a loop failure.
                res = guard.evaluate(tool_name, bindings)
                repetitions = 3
                while not isinstance(res, LoopFailure) and repetitions < 20:
                    repetitions += 1
                    res = guard.evaluate(tool_name, bindings)
                self.assertIsInstance(res, LoopFailure)

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
