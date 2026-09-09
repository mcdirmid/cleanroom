"""Unit tests for agent_conversation_history_impl aligned with grounding specifications."""

import unittest
from lib.agent_conversation_history import (
    ConversationHistory,
    Message,
    ModelRequest,
    Stub,
)
from lib.agent_conversation_history_impl import (
    ConversationHistory as ConversationHistoryImpl,
    __initialize__,
)
from lib.lifecycle import LifecycleRegistry, enter_phase
from lib.tool_provider import Response


class AgentConversationHistoryImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_dataclasses(self) -> None:
        """CUJ: Instantiating Message, Stub, and ModelRequest records."""
        msg = Message(role="user", content="hello")
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "hello")
        self.assertIsNone(msg.tool_call_id)
        self.assertIsNone(msg.tool_name)

        stub = Stub(role="tool", content="[Superseded]", tool_call_id="c1", tool_name="read_file")
        self.assertEqual(stub.role, "tool")
        self.assertEqual(stub.content, "[Superseded]")
        self.assertEqual(stub.tool_call_id, "c1")
        self.assertEqual(stub.tool_name, "read_file")

        req = ModelRequest(messages=[msg])
        self.assertEqual(len(req.messages), 1)

    def test_append_message_chronology(self) -> None:
        """CUJ: Appending messages preserves chronological insertion order."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            history = scope.get_singleton(ConversationHistory)
            # Requirement: [ConversationHistory] Initial messages can seed the conversation history at session start.
            # Requirement: [ConversationHistory] Appending messages and tool responses adds them in chronological order.
            history.append_message(Message(role="system", content="System instruction"))
            history.append_message(Message(role="user", content="User prompt"))
            history.append_message(Message(role="assistant", content="Assistant reply"))

            msgs = history.messages
            self.assertEqual(len(msgs), 3)
            self.assertEqual(msgs[0].role, "system")
            self.assertEqual(msgs[1].role, "user")
            self.assertEqual(msgs[2].role, "assistant")

    def test_append_unprompted_tool_response_inserts_synthetic_assistant_call(self) -> None:
        """CUJ: Appending unprompted tool response adds synthetic assistant invocation."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            history = scope.get_singleton(ConversationHistory)
            history.append_message(Message(role="user", content="Execute tool"))

            resp = Response(is_failed=False, is_terminated=False, content="tool output")
            # Requirement: An unprompted tool response presented at session start is preceded in the conversation history by a synthetic assistant tool invocation message addressing the corresponding tool name.
            # Requirement: Tool execution response notes and content from the tool provider are included in visible tool message content.
            history.append_tool_response(resp, tool_name="read_file", tool_call_id="call_1")

            msgs = history.messages
            # Expect: user -> synthetic assistant -> tool
            self.assertEqual(len(msgs), 3)
            self.assertEqual(msgs[0].role, "user")
            self.assertEqual(msgs[1].role, "assistant")
            self.assertEqual(msgs[1].tool_call_id, "call_1")
            self.assertEqual(msgs[1].tool_name, "read_file")
            self.assertEqual(msgs[2].role, "tool")
            self.assertEqual(msgs[2].content, "tool output")

    def test_append_tool_response_supersession_stubbing(self) -> None:
        """CUJ: Superseded tool results for the same resource are replaced in place with stubs."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            history = scope.get_singleton(ConversationHistory)
            resp1 = Response(is_failed=False, is_terminated=False, content="first output")
            resp2 = Response(is_failed=False, is_terminated=False, content="second output")

            history.append_tool_response(resp1, tool_name="read_file", tool_call_id="call_1")
            # Requirement: [ConversationHistory] When an appended tool result supersedes an earlier result for the same resource, the earlier result is replaced in place with a stub.
            history.append_tool_response(resp2, tool_name="read_file", tool_call_id="call_2")

            msgs = history.messages
            tool_msgs = [m for m in msgs if m.role == "tool"]
            self.assertEqual(len(tool_msgs), 2)
            self.assertIsInstance(tool_msgs[0], Stub)
            self.assertEqual(tool_msgs[0].content, "[Superseded]")
            self.assertEqual(tool_msgs[1].content, "second output")

    def test_get_model_request_strips_internal_metadata(self) -> None:
        """CUJ: Formatting messages into ModelRequest strips lines starting with underscore."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            history = scope.get_singleton(ConversationHistory)
            history.append_message(
                Message(
                    role="user",
                    content="Hello world\n_internal_metadata_id: 12345\nSecond line",
                )
            )
            # Requirement: [ConversationHistory] The conversation history produces a model request prepared for transmission to a language model.
            # Requirement: Messages in a model request are formatted according to model provider roles for system, user, assistant, and tool messages.
            # Requirement: Messages in a model request omit internal metadata fields starting with an underscore.
            req = history.get_model_request()
            self.assertEqual(len(req.messages), 1)
            self.assertNotIn("_internal_metadata_id", req.messages[0].content)
            self.assertIn("Hello world", req.messages[0].content)
            self.assertIn("Second line", req.messages[0].content)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
