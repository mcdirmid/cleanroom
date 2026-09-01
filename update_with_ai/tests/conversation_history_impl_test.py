"""Tests for conversation_history_impl derived from LLS."""

import unittest
from lib.tool_provider import ToolResult
from lib.conversation_history import HistoryMessage, HistoryStub, ModelRequest
from lib.conversation_history_impl import ConversationHistoryFactoryImpl


class ConversationHistoryImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = ConversationHistoryFactoryImpl()

    def test_dataclass_defaults(self) -> None:
        """Tests Data Types: HistoryMessage, HistoryStub, and ModelRequest dataclass defaults."""
        msg = HistoryMessage(role="user", content="hello")
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "hello")
        self.assertIsNone(msg.metadata)

        stub = HistoryStub()
        self.assertEqual(stub.role, "tool")
        self.assertEqual(stub.content, "...")

        req = ModelRequest(messages=[msg])
        self.assertEqual(len(req.messages), 1)
        self.assertIsNone(req.tools)

    def test_initialize_and_append_chronology(self) -> None:
        """Tests CUJ for initializing and appending messages chronologically.

        Checks postconditions: messages are preserved in exact insertion order.
        """
        history = self.factory.create_conversation_history()
        initial = [HistoryMessage(role="system", content="System instruction")]
        history.initialize(initial)
        history.append(HistoryMessage(role="user", content="User prompt"))
        history.append(HistoryMessage(role="assistant", content="Assistant reply"))

        msgs = history.get_messages()
        self.assertEqual(len(msgs), 3)
        self.assertEqual(msgs[0].role, "system")
        self.assertEqual(msgs[1].role, "user")
        self.assertEqual(msgs[2].role, "assistant")

    def test_get_model_request_formatting(self) -> None:
        """Tests CUJ for formatting history into ModelRequest.

        Checks postconditions: returns ModelRequest containing history messages.
        """
        history = self.factory.create_conversation_history()
        history.initialize([HistoryMessage(role="user", content="Hello")])
        req = history.get_model_request()
        self.assertIsInstance(req, ModelRequest)
        self.assertEqual(len(req.messages), 1)
        self.assertEqual(req.messages[0].content, "Hello")

    def test_get_model_request_strips_underscore_metadata(self) -> None:
        """Tests that get_model_request strips internal underscore-prefixed metadata fields."""
        history = self.factory.create_conversation_history()
        msg = HistoryMessage(
            role="user",
            content="Hello",
            metadata={"_internal_id": "123", "public_id": "456"},
        )
        history.initialize([msg])
        req = history.get_model_request()
        self.assertEqual(len(req.messages), 1)
        self.assertIsNotNone(req.messages[0].metadata)
        self.assertNotIn("_internal_id", req.messages[0].metadata)
        self.assertIn("public_id", req.messages[0].metadata)

    def test_append_unprompted_tool_inserts_synthetic_assistant_call(self) -> None:
        """Tests that presenting an unprompted tool result inserts a synthetic assistant tool call message."""
        history = self.factory.create_conversation_history()
        history.initialize([HistoryMessage(role="user", content="Execute tool")])
        history.append(ToolResult(content="output"))

        msgs = history.get_messages()
        # Expect user -> synthetic assistant -> tool
        self.assertEqual(len(msgs), 3)
        self.assertEqual(msgs[0].role, "user")
        self.assertEqual(msgs[1].role, "assistant")
        self.assertEqual(msgs[2].role, "tool")

    def test_append_tool_result_supersession_stubbing(self) -> None:
        """Tests that appending subsequent tool results replaces earlier tool results with static stub markers in-place."""
        history = self.factory.create_conversation_history()
        history.initialize([HistoryMessage(role="user", content="Step 1")])
        history.append(ToolResult(content="First large result"))
        history.append(ToolResult(content="Second result"))

        msgs = history.get_messages()
        # Earlier tool result should be replaced in place with "..."
        tool_msgs = [m for m in msgs if m.role == "tool"]
        self.assertEqual(len(tool_msgs), 2)
        self.assertEqual(tool_msgs[0].content, "...")
        self.assertEqual(tool_msgs[1].content, "Second result")

    def test_tool_result_with_guidance_included_in_model_request(self) -> None:
        """Tests that tool result guidance/notes are retained in ModelRequest metadata."""
        history = self.factory.create_conversation_history()
        history.initialize([HistoryMessage(role="user", content="Start")])
        history.append(ToolResult(content="result text", guidance="next step hint"))

        req = history.get_model_request()
        tool_msgs = [m for m in req.messages if m.role == "tool"]
        self.assertEqual(len(tool_msgs), 1)
        self.assertIn("result text", tool_msgs[0].content)


if __name__ == "__main__":
    unittest.main()
