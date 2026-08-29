"""
Tests for AgentNodeToolExecutorImpl.
"""

import unittest
from typing import Any, Dict, List, Optional

from lib.agent_node_tool_executor_impl import AgentNodeToolExecutorImpl
from lib.sandbox import Sandbox
from lib.tool_provider import (
    PresentedToolResult,
    ToolCallOutcome,
    ToolDefinition,
    ToolResult,
    ToolFailure,
)


class _MockSandbox(Sandbox):
    def __init__(self) -> None:
        self.calls: List[tuple] = []

    def get_tool_definitions(self) -> List[ToolDefinition]:
        return [{
            "type": "function",
            "function": {"name": "read_file", "description": "read", "parameters": {}},
        }]

    def get_session_start_reads(self) -> List[PresentedToolResult]:
        return [ToolResult(content="session start content", supersedes=False)]

    def read_file(self, file_path: str, line_numbers: bool = False) -> PresentedToolResult:
        self.calls.append(("read_file", file_path, line_numbers))
        return [ToolResult(content="file content", supersedes=False)]

    def read_symbol(self, file_path: str, symbol_name: str) -> PresentedToolResult:
        self.calls.append(("read_symbol", file_path, symbol_name))
        return [ToolResult(content="symbol content", supersedes=False)]

    def search_files(self, query: str) -> PresentedToolResult:
        self.calls.append(("search_files", query))
        return [ToolResult(content="search results", supersedes=False)]

    def replace_lines(self, file_path: str, old_str: str, new_str: str, expect_multiple: bool = False) -> ToolCallOutcome:
        self.calls.append(("replace_lines", file_path, old_str, new_str, expect_multiple))
        return ToolResult(content="replaced", supersedes=True)

    def update_lines(self, file_path: str, start_line: int, end_line: int, new_str: str) -> ToolCallOutcome:
        self.calls.append(("update_lines", file_path, start_line, end_line, new_str))
        return ToolResult(content="updated", supersedes=True)

    def advance(self, changes: Optional[List[Dict[str, str]]] = None) -> ToolCallOutcome:
        self.calls.append(("advance", changes))
        return ToolResult(content="advanced", supersedes=True)

    def fail(self, reason: str = "") -> ToolCallOutcome:
        self.calls.append(("fail", reason))
        return ToolResult(content="failed", supersedes=True)

    def blame(self, targets: Optional[List[Dict[str, str]]] = None) -> ToolCallOutcome:
        self.calls.append(("blame", targets))
        return ToolResult(content="blamed", supersedes=True)


class TestAgentNodeToolExecutorImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.sandbox = _MockSandbox()
        self.executor = AgentNodeToolExecutorImpl(sandbox=self.sandbox)

    def test_get_tool_definitions(self) -> None:
        defs = self.executor.get_tool_definitions()
        self.assertEqual(len(defs), 1)
        self.assertEqual(defs[0]["function"]["name"], "read_file")

    def test_get_session_start_reads(self) -> None:
        reads = self.executor.get_session_start_reads()
        self.assertEqual(len(reads), 1)

    def test_execute_read_file(self) -> None:
        res = self.executor.execute_tool("read_file", {"path": "a.txt", "line_numbers": True})
        self.assertEqual(self.sandbox.calls, [("read_file", "a.txt", True)])

    def test_execute_replace(self) -> None:
        res = self.executor.execute_tool("replace", {"path": "a.txt", "old": "foo", "new": "bar"})
        self.assertEqual(self.sandbox.calls, [("replace_lines", "a.txt", "foo", "bar", False)])

    def test_execute_update_lines(self) -> None:
        res = self.executor.execute_tool("update_lines", {"path": "a.txt", "start": 2, "end": 4, "new": "bar"})
        self.assertEqual(self.sandbox.calls, [("update_lines", "a.txt", 2, 4, "bar")])

    def test_execute_advance(self) -> None:
        res = self.executor.execute_tool("advance", {"changes": [{"file": "a.txt", "summary": "s"}]})
        self.assertEqual(self.sandbox.calls, [("advance", [{"file": "a.txt", "summary": "s"}])])

    def test_execute_fail(self) -> None:
        res = self.executor.execute_tool("fail", {"reason": "bug"})
        self.assertEqual(self.sandbox.calls, [("fail", "bug")])

    def test_execute_blame(self) -> None:
        res = self.executor.execute_tool("blame", {"targets": [{"target": "a.txt", "feedback": "f"}]})
        self.assertEqual(self.sandbox.calls, [("blame", [{"target": "a.txt", "feedback": "f"}])])

    def test_execute_unknown_tool(self) -> None:
        res = self.executor.execute_tool("unknown", {})
        self.assertIsInstance(res, ToolFailure)
        assert isinstance(res, ToolFailure)
        self.assertIn("Unknown tool: unknown", res.value)


if __name__ == "__main__":
    unittest.main()
