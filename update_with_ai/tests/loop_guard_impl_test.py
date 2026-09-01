"""Tests for loop_guard_impl derived from LLS."""

import unittest
from lib.loop_guard import LoopGuardConfig, LoopReminder, LoopFailure
from lib.loop_guard_impl import LoopGuardImpl


class LoopGuardImplTest(unittest.TestCase):
    def test_dataclass_defaults(self) -> None:
        """Tests Data Types: LoopGuardConfig dataclass instantiation."""
        cfg = LoopGuardConfig(reminder_threshold=3, fatal_threshold=6)
        self.assertEqual(cfg.reminder_threshold, 3)
        self.assertEqual(cfg.fatal_threshold, 6)

    def test_default_thresholds_behavior(self) -> None:
        """Tests Config: default constructor uses reminder threshold 3 and fatal threshold 6."""
        guard = LoopGuardImpl()
        # 1 and 2 calls -> None
        self.assertIsNone(guard.record_tool_call("read_file", {"file_name": "a.py"}))
        self.assertIsNone(guard.record_tool_call("read_file", {"file_name": "a.py"}))
        # 3 calls -> LoopReminder
        self.assertIsInstance(
            guard.record_tool_call("read_file", {"file_name": "a.py"}),
            LoopReminder,
        )
        # 4 and 5 calls -> LoopReminder
        self.assertIsInstance(
            guard.record_tool_call("read_file", {"file_name": "a.py"}),
            LoopReminder,
        )
        self.assertIsInstance(
            guard.record_tool_call("read_file", {"file_name": "a.py"}),
            LoopReminder,
        )
        # 6 calls -> LoopFailure
        self.assertIsInstance(
            guard.record_tool_call("read_file", {"file_name": "a.py"}),
            LoopFailure,
        )

    def test_identical_tool_call_thresholds_all_sides(self) -> None:
        """Tests all sides of identical tool call thresholds:
        1. Below reminder threshold -> returns None.
        2. Exactly at reminder threshold -> returns LoopReminder.
        3. Above reminder but below fatal -> returns LoopReminder.
        4. At fatal threshold -> returns LoopFailure.
        5. Forward progress resets repetition counts back to zero.
        """
        cfg = LoopGuardConfig(reminder_threshold=2, fatal_threshold=4)
        guard = LoopGuardImpl(cfg)

        # Call 1 (below reminder)
        res1 = guard.record_tool_call("read_file", {"file_name": "a.py"})
        self.assertIsNone(res1)

        # Call 2 (at reminder threshold)
        res2 = guard.record_tool_call("read_file", {"file_name": "a.py"})
        self.assertIsInstance(res2, LoopReminder)

        # Call 3 (above reminder, below fatal)
        res3 = guard.record_tool_call("read_file", {"file_name": "a.py"})
        self.assertIsInstance(res3, LoopReminder)

        # Call 4 (at fatal threshold)
        res4 = guard.record_tool_call("read_file", {"file_name": "a.py"})
        self.assertIsInstance(res4, LoopFailure)

        # Progress reset
        guard.reset_progress()
        res_reset = guard.record_tool_call("read_file", {"file_name": "a.py"})
        self.assertIsNone(res_reset)

    def test_distinct_tool_calls_do_not_increment_repetition(self) -> None:
        """Tests Invariants: distinct tool calls or arguments do not increment repetition counter."""
        cfg = LoopGuardConfig(reminder_threshold=2, fatal_threshold=4)
        guard = LoopGuardImpl(cfg)

        # Call with different arguments
        self.assertIsNone(guard.record_tool_call("read_file", {"file_name": "a.py"}))
        self.assertIsNone(guard.record_tool_call("read_file", {"file_name": "b.py"}))
        self.assertIsNone(guard.record_tool_call("read_file", {"file_name": "a.py"}))

        # Call with different tool names
        self.assertIsNone(guard.record_tool_call("search_files", {"query": "test"}))
        self.assertIsNone(guard.record_tool_call("read_file", {"file_name": "a.py"}))

    def test_line_range_edit_repetition(self) -> None:
        """Tests identical line-range edit repetition detection and boundary conditions."""
        cfg = LoopGuardConfig(reminder_threshold=2, fatal_threshold=3)
        guard = LoopGuardImpl(cfg)

        guard.record_file_edit("a.py", (1, 10))
        res_remind = guard.record_file_edit("a.py", (1, 10))
        self.assertIsInstance(res_remind, LoopReminder)

        # Different line range resets repetition
        res_diff = guard.record_file_edit("a.py", (11, 20))
        self.assertIsNone(res_diff)

        # Consecutive edits to new range
        res_remind2 = guard.record_file_edit("a.py", (11, 20))
        self.assertIsInstance(res_remind2, LoopReminder)
        res_fatal = guard.record_file_edit("a.py", (11, 20))
        self.assertIsInstance(res_fatal, LoopFailure)


if __name__ == "__main__":
    unittest.main()
