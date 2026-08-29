"""
Tests for RunnerLoggerImpl.
"""

import os
import shutil
import tempfile
import unittest
from typing import Any, Dict

from lib.runner_logger_impl import (
    RunnerLoggerImpl,
    _format_compact_log,
    _format_full_log,
)
from lib.tool_provider import ToolResult


class TestLogFormatters(unittest.TestCase):
    def test_compact_log_tool_called(self) -> None:
        data = {
            "node_id": "//pkg:target",
            "tool_calls": [{"function": {"name": "read_file"}}, {"function": {"name": "replace"}}],
        }
        res = _format_compact_log("tool_called", data)
        self.assertEqual(res, "[agent //pkg:target] tool calls: read_file, replace")

    def test_compact_log_api_response_is_none(self) -> None:
        res = _format_compact_log("api_response", {"node_id": "//pkg:target"})
        self.assertIsNone(res)

    def test_compact_log_run_terminated(self) -> None:
        data = {
            "node_id": "//pkg:target",
            "termination_value": "success",
            "cumulative_usage": {
                "input_tokens": 100,
                "cached_input_tokens": 50,
                "output_tokens": 20,
                "request_count": 2,
                "total_duration_seconds": 1.5,
            },
        }
        res = _format_compact_log("run_terminated", data)
        self.assertIsNotNone(res)
        self.assertIn("terminated (success)", res)
        self.assertIn("50% cached", res)

    def test_compact_log_error(self) -> None:
        data = {"node_id": "//pkg:target", "error": "Something went wrong"}
        res = _format_compact_log("error", data)
        self.assertEqual(res, "[agent //pkg:target] ERROR: Something went wrong")

    def test_full_log_message_added(self) -> None:
        data = {
            "node_id": "//pkg:target",
            "message": {"role": "user", "content": "Hello agent"},
        }
        res = _format_full_log("message_added", data)
        self.assertEqual(res, "[//pkg:target] message_added (user): Hello agent")

    def test_full_log_tool_result(self) -> None:
        data = {
            "node_id": "//pkg:target",
            "results": [ToolResult(content="File content", supersedes=True)],
        }
        res = _format_full_log("tool_result", data)
        self.assertIn("tool_result (1)", res)
        self.assertIn("supersedes=True", res)

    def test_create_agent_logger_lifecycle(self) -> None:
        tmp_dir = tempfile.mkdtemp()
        try:
            log_path = os.path.join(tmp_dir, "test.log")
            logger_impl = RunnerLoggerImpl()
            agent_logger, closer = logger_impl.create_agent_logger(log_path)

            agent_logger("tool_called", {
                "node_id": "//pkg:target",
                "tool_calls": [{"function": {"name": "read_file"}}],
            })
            closer()

            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("read_file", content)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)



class TestSigintHandling(unittest.TestCase):
    def test_sigint_handler_raises_keyboard_interrupt(self) -> None:
        import signal
        from lib.runner_logger_impl import _sigint_handler
        with self.assertRaises(KeyboardInterrupt):
            _sigint_handler(signal.SIGINT, None)

if __name__ == "__main__":
    unittest.main()
