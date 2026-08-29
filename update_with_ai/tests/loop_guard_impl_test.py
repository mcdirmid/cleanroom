"""
tests/loop_guard_impl_test.py

Comprehensive unit tests for LoopGuardImpl against its low-level spec
and the LoopGuard Protocol.
"""

import unittest
from lib.tool_provider import ToolCall
from lib.agent_loop_config import AgentLoopConfig
from lib.loop_guard_impl import LoopGuardImpl


class TestLoopGuardImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.config = AgentLoopConfig(
            base_url="http://localhost",
            api_key="key",
            model="model",
            termination_reminder_generator=lambda: "Custom termination reminder.",
        )
        self.guard = LoopGuardImpl(config=self.config)

    def test_identical_tool_call_repetition_thresholds(self) -> None:
        call: ToolCall = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"file_path": "a.py"}'},
        }
        for _ in range(3):
            stop, reminder, err = self.guard.record_tool_call(call)
            self.assertFalse(stop)
            self.assertIsNone(reminder)
            self.assertIsNone(err)

        # 4th call injects reminder
        stop, reminder, err = self.guard.record_tool_call(call)
        self.assertFalse(stop)
        self.assertIsNotNone(reminder)
        self.assertIn("read_file", reminder or "")
        self.assertIsNone(err)

        # 5th to 7th calls do not re-inject reminder
        for _ in range(3):
            stop, reminder, err = self.guard.record_tool_call(call)
            self.assertFalse(stop)
            self.assertIsNone(reminder)
            self.assertIsNone(err)

        # 8th call triggers degenerate failure
        stop, reminder, err = self.guard.record_tool_call(call)
        self.assertTrue(stop)
        self.assertIsNone(reminder)
        self.assertIn("Degenerate loop: same tool call repeated 8 consecutive times", err or "")

    def test_distinct_tool_calls_do_not_trigger_reminder(self) -> None:
        for i in range(10):
            call: ToolCall = {
                "id": f"call_{i}",
                "type": "function",
                "function": {"name": "read_file", "arguments": f'{{"file_path": "a{i}.py"}}'},
            }
            stop, reminder, err = self.guard.record_tool_call(call)
            self.assertFalse(stop)
            self.assertIsNone(reminder)
            self.assertIsNone(err)

    def test_same_range_update_lines_repetition_thresholds(self) -> None:
        call: ToolCall = {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "update_lines",
                "arguments": '{"file_path": "a.py", "start_line": 10, "end_line": 20, "new_str": "v1"}',
            },
        }
        for i in range(3):
            call["function"]["arguments"] = f'{{"file_path": "a.py", "start_line": 10, "end_line": 20, "new_str": "v{i}"}}'
            stop, reminder, err = self.guard.record_tool_call(call)
            self.assertFalse(stop)
            self.assertIsNone(reminder)

        call["function"]["arguments"] = '{"file_path": "a.py", "start_line": 10, "end_line": 20, "new_str": "v4"}'
        stop, reminder, err = self.guard.record_tool_call(call)
        self.assertFalse(stop)
        self.assertIsNotNone(reminder)
        self.assertIn("edited lines 10-20 of 'a.py'", reminder or "")

        # Up to 7th: no repeat reminder
        for i in range(5, 8):
            call["function"]["arguments"] = f'{{"file_path": "a.py", "start_line": 10, "end_line": 20, "new_str": "v{i}"}}'
            stop, reminder, err = self.guard.record_tool_call(call)
            self.assertFalse(stop)
            self.assertIsNone(reminder)

        # 8th edit on same range fails
        call["function"]["arguments"] = '{"file_path": "a.py", "start_line": 10, "end_line": 20, "new_str": "v8"}'
        stop, reminder, err = self.guard.record_tool_call(call)
        self.assertTrue(stop)
        self.assertIn("targeted the same file and line range 8 consecutive times", err or "")

    def test_advance_resets_tracking(self) -> None:
        call: ToolCall = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"file_path": "a.py"}'},
        }
        for _ in range(3):
            self.guard.record_tool_call(call)

        advance_call: ToolCall = {
            "id": "call_adv",
            "type": "function",
            "function": {"name": "advance", "arguments": "{}"},
        }
        self.guard.record_tool_call(advance_call)

        # After advance, counter is reset: 3 more calls do not trigger 4-count reminder
        for _ in range(3):
            stop, reminder, _ = self.guard.record_tool_call(call)
            self.assertFalse(stop)
            self.assertIsNone(reminder)

    def test_check_degenerate_response(self) -> None:
        self.assertTrue(self.guard.check_degenerate_response("aaaa"))
        self.assertTrue(self.guard.check_degenerate_response("\n\n\n"))
        self.assertFalse(self.guard.check_degenerate_response("abcd"))
        self.assertFalse(self.guard.check_degenerate_response(""))
        self.assertFalse(self.guard.check_degenerate_response(None))

    def test_get_termination_reminder(self) -> None:
        self.assertEqual(self.guard.get_termination_reminder(), "Custom termination reminder.")
        default_guard = LoopGuardImpl()
        self.assertIn("advance(), fail(), or blame()", default_guard.get_termination_reminder())


if __name__ == "__main__":
    unittest.main()
