"""
tests/conversation_history_impl_test.py

Comprehensive unit tests for ConversationHistoryImpl against its low-level spec
and the ConversationHistory Protocol.
"""

import unittest
from typing import Any, Dict, List

from lib.conversation_history import HistoryEntry, LogEvent, LoggerCallback
from lib.conversation_history_impl import ConversationHistoryImpl, STUB_TEXT
from lib.tool_provider import PresentedToolResult, ToolCall, ToolResult


class TestConversationHistoryImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.history = ConversationHistoryImpl()
        self.events: List[tuple[LogEvent, Dict[str, Any]]] = []

    def logger(self, event: LogEvent, data: Dict[str, Any]) -> None:
        self.events.append((event, data))

    def test_initialize_with_prompt_and_session_start(self) -> None:
        presented = PresentedToolResult(
            name="read_file",
            arguments={"file_path": "foo.py"},
            result=ToolResult(content="file content", supersedes=False),
        )
        self.history.initialize("Hello agent", [presented], self.logger)
        entries = self.history.get_history()
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["role"], "user")
        self.assertEqual(entries[0]["content"], "Hello agent")
        self.assertEqual(entries[1]["role"], "assistant")
        self.assertEqual(entries[1]["tool_calls"][0]["function"]["name"], "read_file")
        self.assertEqual(entries[2]["role"], "tool")
        self.assertEqual(entries[2]["content"], "file content")

    def test_empty_prompt_initialization(self) -> None:
        self.history.initialize("", None, self.logger)
        self.assertEqual(len(self.history.get_history()), 0)

    def test_append_message(self) -> None:
        msg: HistoryEntry = {"role": "assistant", "content": "Thinking..."}
        self.history.append_message(msg, self.logger)
        self.assertEqual(len(self.history.get_history()), 1)
        self.assertEqual(self.history.get_history()[0]["content"], "Thinking...")
        self.assertEqual(self.events[0][0], "message_added")

    def test_in_place_stubbing_superseding_result(self) -> None:
        call1: ToolCall = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"file_path": "a.py"}'},
        }
        self.history.add_tool_result(call1, ToolResult(content="v1", supersedes=True, note="note1"), self.logger)

        call2: ToolCall = {
            "id": "call_2",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"file_path": "a.py"}'},
        }
        self.history.add_tool_result(call2, ToolResult(content="v2", supersedes=True, note="note2"), self.logger)

        entries = self.history.get_history()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["content"], STUB_TEXT)
        self.assertTrue(entries[0].get("_stubbed"))
        self.assertNotIn("_note", entries[0])
        self.assertEqual(entries[1]["content"], "v2")
        self.assertEqual(entries[1]["_note"], "note2")

        # Check message_stubbed event was emitted
        stubbed_events = [e for e in self.events if e[0] == "message_stubbed"]
        self.assertEqual(len(stubbed_events), 1)

    def test_non_superseding_result_not_stubbed(self) -> None:
        call1: ToolCall = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "run_cmd", "arguments": '{"cmd": "ls"}'},
        }
        self.history.add_tool_result(call1, ToolResult(content="out1", supersedes=False), self.logger)
        self.history.add_tool_result(call1, ToolResult(content="out2", supersedes=False), self.logger)

        entries = self.history.get_history()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["content"], "out1")
        self.assertEqual(entries[1]["content"], "out2")

    def test_different_files_do_not_stub_each_other(self) -> None:
        call1: ToolCall = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"file_path": "a.py"}'},
        }
        call2: ToolCall = {
            "id": "call_2",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"file_path": "b.py"}'},
        }
        self.history.add_tool_result(call1, ToolResult(content="a_content", supersedes=True), self.logger)
        self.history.add_tool_result(call2, ToolResult(content="b_content", supersedes=True), self.logger)

        entries = self.history.get_history()
        self.assertEqual(entries[0]["content"], "a_content")
        self.assertEqual(entries[1]["content"], "b_content")

    def test_get_rendered_messages_strips_metadata_and_renders_note(self) -> None:
        call: ToolCall = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "verify", "arguments": "{}"},
        }
        self.history.add_tool_result(
            call,
            ToolResult(content="passed", supersedes=False, note="Remaining: 1 step"),
            self.logger,
        )
        rendered = self.history.get_rendered_messages(system_prompt="System instruction")
        self.assertEqual(len(rendered), 2)
        self.assertEqual(rendered[0]["role"], "system")
        self.assertEqual(rendered[0]["content"], "System instruction")
        self.assertEqual(rendered[1]["role"], "tool")
        self.assertIn("passed", str(rendered[1]["content"]))
        self.assertIn("Remaining: 1 step", str(rendered[1]["content"]))
        self.assertNotIn("_note", rendered[1])
        self.assertNotIn("_tool_name", rendered[1])
        self.assertNotIn("_arguments", rendered[1])

    def test_reset_clears_all_state(self) -> None:
        call: ToolCall = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"file_path": "a.py"}'},
        }
        self.history.add_tool_result(call, ToolResult(content="v1", supersedes=True), self.logger)
        self.history.reset()
        self.assertEqual(len(self.history.get_history()), 0)
        self.assertEqual(len(self.history.get_rendered_messages()), 0)


if __name__ == "__main__":
    unittest.main()
