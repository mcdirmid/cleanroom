"""Unit tests for openai_conversation_impl aligned with grounding specifications."""

import unittest
from update_with_ai.parts.loop.lib.loop_conversation import (
    Conversation,
    Message,
    ModelRequest,
)
from update_with_ai.parts.openai.lib.openai_conversation_impl import (
    Conversation as ConversationImpl,
    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.sandbox.lib.tool_provider import (
    Response,
    WireParameterBindings,
)


class OpenAIConversationImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_dataclasses(self) -> None:
        """CUJ: Instantiating Message and ModelRequest records."""
        msg = Message(
            role="user",
            content="hello",
            reminder="Remember this",
            tool_arguments='{"a": "b"}',
        )
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "hello")
        self.assertIsNone(msg.tool_call_id)
        self.assertIsNone(msg.tool_name)
        self.assertEqual(msg.reminder, "Remember this")
        self.assertEqual(msg.tool_arguments, '{"a": "b"}')
        self.assertFalse(msg.is_stub)

        stub_msg = Message(
            role="tool",
            content="[Superseded]",
            tool_call_id="c1",
            tool_name="view_file",
            reminder="Keep this",
            tool_arguments="{}",
            is_stub=True,
        )
        self.assertEqual(stub_msg.role, "tool")
        self.assertEqual(stub_msg.content, "[Superseded]")
        self.assertEqual(stub_msg.tool_call_id, "c1")
        self.assertEqual(stub_msg.tool_name, "view_file")
        self.assertEqual(stub_msg.reminder, "Keep this")
        self.assertEqual(stub_msg.tool_arguments, "{}")
        self.assertTrue(stub_msg.is_stub)

        req = ModelRequest(messages=[msg])
        self.assertEqual(len(req.messages), 1)

    def test_append_message_chronology(self) -> None:
        """CUJ: Appending messages preserves chronological insertion order."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            history = scope.get_singleton(Conversation)
            # Requirement: [Conversation] Initial messages can seed the conversation at session start.
            # Requirement: [Conversation] Appending messages and tool responses adds them in chronological order.
            history.append_message(Message(role="system", content="System instruction"))
            history.append_message(Message(role="user", content="User prompt"))
            history.append_message(Message(role="assistant", content="Assistant reply"))

            msgs = history.messages
            self.assertEqual(len(msgs), 3)
            self.assertEqual(msgs[0].role, "system")
            self.assertEqual(msgs[1].role, "user")
            self.assertEqual(msgs[2].role, "assistant")

    def test_append_unprompted_tool_response_inserts_synthetic_assistant_call(
        self,
    ) -> None:
        """CUJ: Appending unprompted tool response adds synthetic assistant invocation correlating with tool_call_id and sorted arguments."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            history = scope.get_singleton(Conversation)
            history.append_message(Message(role="user", content="Execute tool"))

            resp1 = Response(
                is_failed=False, is_terminated=False, content="tool output 1"
            )
            # Requirement: Each unprompted tool response presented at session start is preceded in the conversation by a synthetic assistant tool invocation message formatted according to OpenAI tool calling conventions, correlating with the response tool call identifier and ordering serialized argument parameters deterministically by parameter name, presenting the tool execution as if initiated by the model.
            bindings1 = WireParameterBindings(
                bindings={("z_param", "last"), ("a_param", "first")}
            )
            history.append_tool_response(
                resp1,
                tool_name="view_file",
                tool_call_id="call_1",
                wire_parameter_bindings=bindings1,
            )

            # A second unprompted tool response with the SAME tool name must also get its own synthetic assistant message paired by tool_call_id
            resp2 = Response(
                is_failed=False, is_terminated=False, content="tool output 2"
            )
            bindings2 = WireParameterBindings(bindings={("path", "second.py")})
            history.append_tool_response(
                resp2,
                tool_name="view_file",
                tool_call_id="call_2",
                wire_parameter_bindings=bindings2,
            )

            msgs = history.messages
            # Expect: user -> synthetic assistant 1 -> tool 1 -> synthetic assistant 2 -> tool 2
            self.assertEqual(len(msgs), 5)
            self.assertEqual(msgs[0].role, "user")

            self.assertEqual(msgs[1].role, "assistant")
            self.assertEqual(msgs[1].tool_call_id, "call_1")
            self.assertEqual(msgs[1].tool_name, "view_file")
            self.assertEqual(
                msgs[1].tool_arguments, '{"a_param": "first", "z_param": "last"}'
            )

            self.assertEqual(msgs[2].role, "tool")
            self.assertEqual(msgs[2].tool_call_id, "call_1")
            self.assertEqual(msgs[2].content, "tool output 1")

            self.assertEqual(msgs[3].role, "assistant")
            self.assertEqual(msgs[3].tool_call_id, "call_2")
            self.assertEqual(msgs[3].tool_name, "view_file")
            self.assertEqual(msgs[3].tool_arguments, '{"path": "second.py"}')

            self.assertEqual(msgs[4].role, "tool")
            self.assertEqual(msgs[4].tool_call_id, "call_2")
            self.assertEqual(msgs[4].content, "tool output 2")

    def test_append_tool_response_supersession_stubbing(self) -> None:
        """CUJ: Superseded tool results with matching suppression key are replaced with stubs, while unmatched keys are preserved."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            history = scope.get_singleton(Conversation)

            # 1. Responses without suppression key are never superseded
            ro_resp1 = Response(
                is_failed=False,
                is_terminated=False,
                content="spec v1",
                suppression_key=None,
            )
            history.append_tool_response(
                ro_resp1, tool_name="view_file", tool_call_id="call_ro1"
            )

            ro_resp2 = Response(
                is_failed=False,
                is_terminated=False,
                content="spec v2",
                suppression_key=None,
            )
            history.append_tool_response(
                ro_resp2, tool_name="view_file", tool_call_id="call_ro2"
            )

            # 2. Distinct suppression keys do not supersede each other
            rw_other = Response(
                is_failed=False,
                is_terminated=False,
                content="other code",
                suppression_key="other.py",
            )
            history.append_tool_response(
                rw_other, tool_name="view_file", tool_call_id="call_other"
            )

            # 3. Response with matching suppression key supersedes earlier response with that key
            rw_widget1 = Response(
                is_failed=False,
                is_terminated=False,
                content="widget v1",
                suppression_key="widget.py",
            )
            history.append_tool_response(
                rw_widget1, tool_name="view_file", tool_call_id="call_w1"
            )

            # Requirement: A tool response's suppression key identifies the latest preceding response with the same key in the conversation for replacement with a stub, while responses with unmatched keys are preserved intact.
            # Requirement: [Conversation] Stubs previous responses identified by a suppression key.
            rw_widget2 = Response(
                is_failed=False,
                is_terminated=False,
                content="widget v2",
                suppression_key="widget.py",
            )
            history.append_tool_response(
                rw_widget2, tool_name="view_file", tool_call_id="call_w2"
            )

            # 4. Responses sharing suppression key 'advance', retaining and inheriting reminder
            adv1 = Response(
                is_failed=True,
                is_terminated=False,
                content="advance step 1 failed",
                reminder="Only provide change summary when completing.",
                suppression_key="advance",
            )
            adv2 = Response(
                is_failed=False,
                is_terminated=False,
                content="advance step 2",
                suppression_key="advance",
            )
            history.append_tool_response(
                adv1, tool_name="advance", tool_call_id="call_adv1"
            )
            # Requirement: A stub retains the reminder from the superseded tool response, which the newly appended response inherits when omitted.
            history.append_tool_response(
                adv2, tool_name="advance", tool_call_id="call_adv2"
            )

            tool_msgs = [m for m in history.messages if m.role == "tool"]

            # Verify responses without suppression keys were NOT superseded
            self.assertFalse(tool_msgs[0].is_stub)
            self.assertEqual(tool_msgs[0].content, "spec v1")
            self.assertFalse(tool_msgs[1].is_stub)
            self.assertEqual(tool_msgs[1].content, "spec v2")

            # Verify distinct suppression key was NOT superseded
            self.assertFalse(tool_msgs[2].is_stub)
            self.assertEqual(tool_msgs[2].content, "other code")

            # Verify widget.py v1 WAS superseded, while widget.py v2 is intact
            self.assertTrue(tool_msgs[3].is_stub)
            self.assertEqual(tool_msgs[3].content, "[Superseded]")
            self.assertFalse(tool_msgs[4].is_stub)
            self.assertEqual(tool_msgs[4].content, "widget v2")

            # Verify advance v1 WAS superseded into a stub and retained its reminder
            self.assertTrue(tool_msgs[5].is_stub)
            self.assertEqual(tool_msgs[5].content, "[Superseded]")
            self.assertEqual(
                tool_msgs[5].reminder, "Only provide change summary when completing."
            )
            self.assertFalse(tool_msgs[6].is_stub)
            self.assertEqual(tool_msgs[6].content, "advance step 2")
            self.assertEqual(
                tool_msgs[6].reminder, "Only provide change summary when completing."
            )

    def test_get_model_request_formats_roles_and_reminders(self) -> None:
        """CUJ: Formatting messages into ModelRequest formats OpenAI conventions and active reminders."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            history = scope.get_singleton(Conversation)
            history.append_message(
                Message(
                    role="system",
                    content="System instruction",
                )
            )
            history.append_message(
                Message(
                    role="user",
                    content="Hello world",
                )
            )
            resp = Response(
                is_failed=False,
                is_terminated=False,
                content="line 1\nline 2",
                reminder="Remember to write tests.",
            )
            history.append_tool_response(resp, tool_name="advance", tool_call_id="c1")
            # Requirement: [Conversation] The conversation produces a model request prepared for transmission to a language model.
            # Requirement: The conversation formats messages in a model request according to OpenAI chat completion conventions for system, user, assistant, and tool messages.
            # Requirement: Tool execution response notes, content, and reminders from the tool provider are included in visible tool message content, formatting active reminders on messages and superseded stubs to remind the agent in the assembled model request.
            req = history.get_model_request()
            self.assertEqual(
                len(req.messages), 4
            )  # system, user, synthetic assistant, tool
            self.assertEqual(req.messages[0].role, "system")
            self.assertEqual(req.messages[0].content, "System instruction")
            self.assertEqual(req.messages[1].role, "user")
            self.assertEqual(req.messages[1].content, "Hello world")
            self.assertEqual(req.messages[2].role, "assistant")
            self.assertEqual(req.messages[2].tool_call_id, "c1")

            tool_msg = req.messages[3]
            self.assertEqual(tool_msg.role, "tool")
            self.assertEqual(tool_msg.tool_call_id, "c1")
            self.assertIn(
                "line 1\nline 2\n\nReminder: Remember to write tests.", tool_msg.content
            )

            # Response with empty content and non-empty reminder
            empty_resp = Response(
                is_failed=False,
                is_terminated=False,
                content="",
                reminder="Remember to finish.",
            )
            history.append_tool_response(
                empty_resp, tool_name="finish", tool_call_id="c2"
            )
            req2 = history.get_model_request()
            # Requirement: Tool execution response notes, content, and reminders from the tool provider are included in visible tool message content, formatting active reminders on messages and superseded stubs to remind the agent in the assembled model request.
            self.assertEqual(req2.messages[-1].content, "Reminder: Remember to finish.")


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
