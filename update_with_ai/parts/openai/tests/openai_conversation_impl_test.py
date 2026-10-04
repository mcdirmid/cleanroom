"""Unit tests for openai_conversation_impl aligned with grounding specifications."""

import json
from typing import Any, cast, Optional
import unittest
from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.loop.lib.loop_conversation import (
    Conversation,
    ConversationContent,
    ConversationMessage,
    MessageRole,
    ModelRequest,
    SerializedArguments,
    ToolCallId,
)
from update_with_ai.parts.openai.lib.openai_conversation_impl import (
    Conversation as ConversationImpl,
    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.sandbox.lib.tool_provider import (
    SuppressionKey,
    ToolName,
    ToolReminder,
    ToolResponse,
    ToolResponseContent,
)


def _make_msg(
    role: str,
    content: str,
    tool_call_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    reminder: Optional[str] = None,
    tool_arguments: Optional[str] = None,
    is_stub: bool = False,
) -> ConversationMessage:
    return ConversationMessage(
        role=MessageRole(role),
        content=ConversationContent(content),
        tool_call_id=ToolCallId(tool_call_id) if tool_call_id is not None else None,
        tool_name=ToolName(tool_name) if tool_name is not None else None,
        reminder=ToolReminder(reminder) if reminder is not None else None,
        tool_arguments=SerializedArguments(tool_arguments) if tool_arguments is not None else None,
        is_stub=is_stub,
    )


def _make_response(
    content: str,
    is_failed: bool = False,
    is_terminated: bool = False,
    reminder: Optional[str] = None,
    suppression_key: Optional[str] = None,
) -> ToolResponse:
    return ToolResponse(
        is_failed=is_failed,
        is_terminated=is_terminated,
        content=ToolResponseContent(content),
        reminder=ToolReminder(reminder) if reminder is not None else None,
        suppression_key=SuppressionKey(suppression_key) if suppression_key is not None else None,
    )


class MockAgentConfig:
    def __init__(self, supersede_arg_keep: int = 20) -> None:
        self.supersede_arg_keep = supersede_arg_keep


class OpenAIConversationImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.agent_cfg = MockAgentConfig()
        self.registry.register_instance(
            self.agent_cfg, keys=[AgentConfig], tier=system
        )

    def test_dataclasses(self) -> None:
        """CUJ: Instantiating ConversationMessage and ModelRequest records."""
        msg = ConversationMessage(
            role=MessageRole("user"),
            content=ConversationContent("hello"),
            reminder=ToolReminder("Remember this"),
            tool_arguments=SerializedArguments('{"a": "b"}'),
        )
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "hello")
        self.assertIsNone(msg.tool_call_id)
        self.assertIsNone(msg.tool_name)
        self.assertEqual(msg.reminder, "Remember this")
        self.assertEqual(msg.tool_arguments, '{"a": "b"}')
        self.assertFalse(msg.is_stub)

        stub_msg = ConversationMessage(
            role=MessageRole("tool"),
            content=ConversationContent("[Superseded]"),
            tool_call_id=ToolCallId("c1"),
            tool_name=ToolName("view_file"),
            reminder=ToolReminder("Keep this"),
            tool_arguments=SerializedArguments("{}"),
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
        with enter_phase(agent_session, registry=self.registry) as scope:
            history = scope.get_singleton(Conversation)
            # Requirement: [Conversation] Initial messages can seed the conversation at session start.
            # Requirement: [Conversation] Appending messages and tool responses adds them in chronological order.
            history.append_message(_make_msg("system", "System instruction"))
            history.append_message(_make_msg("user", "User prompt"))
            history.append_message(_make_msg("assistant", "Assistant reply"))

            msgs = history.get_model_request().messages
            self.assertEqual(len(msgs), 3)
            self.assertEqual(msgs[0].role, "system")
            self.assertEqual(msgs[1].role, "user")
            self.assertEqual(msgs[2].role, "assistant")
            # Verify conversation messages history accessor
            self.assertEqual(len(cast(Any, history).messages), 3)

    def test_append_unprompted_tool_response_inserts_synthetic_assistant_call(
        self,
    ) -> None:
        """CUJ: Appending unprompted tool response adds synthetic assistant invocation correlating with tool_call_id and sorted arguments."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            history = scope.get_singleton(Conversation)
            history.append_message(_make_msg("user", "Execute tool"))

            resp1 = _make_response("tool output 1")
            # Requirement: Each unprompted tool response presented at session start is preceded in the conversation by a synthetic assistant tool invocation message formatted according to OpenAI tool calling conventions, correlating with the response tool call identifier and ordering serialized argument parameters deterministically by parameter name, presenting the tool execution as if initiated by the model.
            history.append_tool_response(
                resp1,
                tool_call_id=ToolCallId("call_1"),
                tool_name=ToolName("view_file"),
                tool_arguments=SerializedArguments('{"a_param": "first", "z_param": "last"}'),
            )

            # A second unprompted tool response with the SAME tool name must also get its own synthetic assistant message paired by tool_call_id
            resp2 = _make_response("tool output 2")
            history.append_tool_response(
                resp2,
                tool_call_id=ToolCallId("call_2"),
                tool_name=ToolName("view_file"),
                tool_arguments=SerializedArguments('{"path": "second.py"}'),
            )

            msgs = history.get_model_request().messages
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
        with enter_phase(agent_session, registry=self.registry) as scope:
            history = scope.get_singleton(Conversation)

            # 1. Responses without suppression key are never superseded
            ro_resp1 = _make_response("spec v1", suppression_key=None)
            history.append_tool_response(
                ro_resp1,
                tool_name=ToolName("view_file"),
                tool_call_id=ToolCallId("call_ro1"),
                tool_arguments=SerializedArguments("{}"),
            )

            ro_resp2 = _make_response("spec v2", suppression_key=None)
            history.append_tool_response(
                ro_resp2,
                tool_name=ToolName("view_file"),
                tool_call_id=ToolCallId("call_ro2"),
                tool_arguments=SerializedArguments("{}"),
            )

            # 2. Distinct suppression keys do not supersede each other
            rw_other = _make_response("other code", suppression_key="other.py")
            history.append_tool_response(
                rw_other,
                tool_name=ToolName("view_file"),
                tool_call_id=ToolCallId("call_other"),
                tool_arguments=SerializedArguments("{}"),
            )

            # 3. ToolResponse with matching suppression key: retains rolling buffer of 3, superseding older ones
            rw_widget1 = _make_response("widget v1", suppression_key="widget.py")
            history.append_tool_response(
                rw_widget1,
                tool_name=ToolName("view_file"),
                tool_call_id=ToolCallId("call_w1"),
                tool_arguments=SerializedArguments("{}"),
            )
            rw_widget2 = _make_response("widget v2", suppression_key="widget.py")
            history.append_tool_response(
                rw_widget2,
                tool_name=ToolName("view_file"),
                tool_call_id=ToolCallId("call_w2"),
                tool_arguments=SerializedArguments("{}"),
            )
            rw_widget3 = _make_response("widget v3", suppression_key="widget.py")
            history.append_tool_response(
                rw_widget3,
                tool_name=ToolName("view_file"),
                tool_call_id=ToolCallId("call_w3"),
                tool_arguments=SerializedArguments("{}"),
            )

            # At 3 responses with the same key, none are superseded yet (all 3 in buffer)
            req_3 = history.get_model_request()
            w_tools_3 = [m for m in req_3.messages if m.tool_call_id in ("call_w1", "call_w2", "call_w3") and m.role == "tool"]
            self.assertEqual(len(w_tools_3), 3)
            self.assertTrue(all(not m.is_stub for m in w_tools_3))

            # Requirement: A tool response's suppression key retains a buffer of up to three most recent responses sharing that key in the conversation, replacing older preceding responses beyond the buffer limit with stubs, while responses with unmatched keys are preserved intact.
            rw_widget4 = _make_response("widget v4", suppression_key="widget.py")
            history.append_tool_response(
                rw_widget4,
                tool_name=ToolName("view_file"),
                tool_call_id=ToolCallId("call_w4"),
                tool_arguments=SerializedArguments("{}"),
            )

            # 4. Responses sharing suppression key 'advance', retaining and inheriting reminder across buffer
            adv1 = _make_response(
                "advance step 1 failed",
                is_failed=True,
                reminder="Only provide change summary when completing.",
                suppression_key="advance",
            )
            adv2 = _make_response(
                "advance step 2",
                is_failed=False,
                suppression_key="advance",
            )
            adv3 = _make_response(
                "advance step 3",
                is_failed=False,
                suppression_key="advance",
            )
            history.append_tool_response(
                adv1,
                tool_name=ToolName("advance"),
                tool_call_id=ToolCallId("call_adv1"),
                tool_arguments=SerializedArguments("{}"),
            )
            # Requirement: A stub retains the reminder from the superseded tool response, which newly appended responses inherit when omitted.
            history.append_tool_response(
                adv2,
                tool_name=ToolName("advance"),
                tool_call_id=ToolCallId("call_adv2"),
                tool_arguments=SerializedArguments("{}"),
            )
            history.append_tool_response(
                adv3,
                tool_name=ToolName("advance"),
                tool_call_id=ToolCallId("call_adv3"),
                tool_arguments=SerializedArguments("{}"),
            )
            adv4 = _make_response(
                "advance step 4",
                is_failed=False,
                suppression_key="advance",
            )
            history.append_tool_response(
                adv4,
                tool_name=ToolName("advance"),
                tool_call_id=ToolCallId("call_adv4"),
                tool_arguments=SerializedArguments("{}"),
            )

            # 5. replace_file_content calls: buffer of 3 retains latest 3, superseding older ones
            history.append_message(
                _make_msg(
                    role="assistant",
                    content="",
                    tool_call_id="call_edit1",
                    tool_name="replace_file_content",
                    tool_arguments=json.dumps({
                        "path": "file_a.py",
                        "count": 42,
                        "target_content": "old_a",
                        "replacement_content": "prefix_01234567890123456789",
                    }),
                )
            )
            edit1_resp = _make_response(
                "diff a",
                suppression_key="replace_file_content",
            )
            history.append_tool_response(
                edit1_resp,
                tool_name=ToolName("replace_file_content"),
                tool_call_id=ToolCallId("call_edit1"),
                tool_arguments=SerializedArguments(
                    json.dumps({
                        "path": "file_a.py",
                        "count": 42,
                        "target_content": "old_a",
                        "replacement_content": "prefix_01234567890123456789",
                    })
                ),
            )

            history.append_message(
                _make_msg(
                    role="assistant",
                    content="",
                    tool_call_id="call_edit2",
                    tool_name="replace_file_content",
                    tool_arguments='{"path": "file_b.py", "target_content": "old_b", "replacement_content": "new_b"}',
                )
            )
            edit2_resp = _make_response(
                "diff b",
                suppression_key="replace_file_content",
            )
            history.append_tool_response(
                edit2_resp,
                tool_name=ToolName("replace_file_content"),
                tool_call_id=ToolCallId("call_edit2"),
                tool_arguments=SerializedArguments(
                    '{"path": "file_b.py", "target_content": "old_b", "replacement_content": "new_b"}'
                ),
            )

            history.append_message(
                _make_msg(
                    role="assistant",
                    content="",
                    tool_call_id="call_edit3",
                    tool_name="replace_file_content",
                    tool_arguments='{"path": "file_c.py", "target_content": "old_c", "replacement_content": "new_c"}',
                )
            )
            edit3_resp = _make_response(
                "diff c",
                suppression_key="replace_file_content",
            )
            history.append_tool_response(
                edit3_resp,
                tool_name=ToolName("replace_file_content"),
                tool_call_id=ToolCallId("call_edit3"),
                tool_arguments=SerializedArguments(
                    '{"path": "file_c.py", "target_content": "old_c", "replacement_content": "new_c"}'
                ),
            )

            # At this point, Edit 1, 2, 3 are all intact in the buffer
            edit1_asst = next(
                m for m in history.get_model_request().messages if m.tool_call_id == "call_edit1" and m.role == "assistant"
            )
            self.assertFalse(edit1_asst.is_stub)

            # Now Edit 4 pushes Edit 1 out of the 3-item buffer
            history.append_message(
                _make_msg(
                    role="assistant",
                    content="",
                    tool_call_id="call_edit4",
                    tool_name="replace_file_content",
                    tool_arguments='{"path": "file_d.py", "target_content": "old_d", "replacement_content": "new_d"}',
                )
            )
            edit4_resp = _make_response(
                "Error: target_content not found in file_d.py.",
                is_failed=True,
                suppression_key="replace_file_content",
            )
            history.append_tool_response(
                edit4_resp,
                tool_name=ToolName("replace_file_content"),
                tool_call_id=ToolCallId("call_edit4"),
                tool_arguments=SerializedArguments(
                    '{"path": "file_d.py", "target_content": "old_d", "replacement_content": "new_d"}'
                ),
            )

            tool_msgs = [m for m in history.get_model_request().messages if m.role == "tool"]

            # Verify responses without suppression keys were NOT superseded
            self.assertFalse(tool_msgs[0].is_stub)
            self.assertEqual(tool_msgs[0].content, "spec v1")
            self.assertFalse(tool_msgs[1].is_stub)
            self.assertEqual(tool_msgs[1].content, "spec v2")

            # Verify distinct suppression key was NOT superseded
            self.assertFalse(tool_msgs[2].is_stub)
            self.assertEqual(tool_msgs[2].content, "other code")

            # Verify widget.py v1 WAS superseded (pushed past buffer limit 3), while widget.py v2, v3, v4 are intact
            self.assertTrue(tool_msgs[3].is_stub)
            self.assertEqual(tool_msgs[3].content, "[Superseded]")
            self.assertFalse(tool_msgs[4].is_stub)
            self.assertEqual(tool_msgs[4].content, "widget v2")
            self.assertFalse(tool_msgs[5].is_stub)
            self.assertEqual(tool_msgs[5].content, "widget v3")
            self.assertFalse(tool_msgs[6].is_stub)
            self.assertEqual(tool_msgs[6].content, "widget v4")

            # Requirement: When a response is replaced with a stub, tool arguments in the correlating assistant invocation message retain their parameter keys, preserving file path parameters, preserving non-string values, and replacing other string values with a stub marker.
            w1_asst = next(
                m for m in history.get_model_request().messages if m.tool_call_id == "call_w1" and m.role == "assistant"
            )
            self.assertTrue(w1_asst.is_stub)
            self.assertEqual(w1_asst.tool_arguments, "{}")

            w2_asst = next(
                m for m in history.get_model_request().messages if m.tool_call_id == "call_w2" and m.role == "assistant"
            )
            self.assertFalse(w2_asst.is_stub)

            # Verify advance v1 WAS superseded into a stub and retained its reminder, while v2, v3, v4 are intact
            self.assertTrue(tool_msgs[7].is_stub)
            self.assertEqual(tool_msgs[7].content, "[Superseded]")
            self.assertEqual(
                tool_msgs[7].reminder, "Only provide change summary when completing."
            )
            self.assertFalse(tool_msgs[8].is_stub)
            self.assertEqual(tool_msgs[8].content, "advance step 2")
            self.assertEqual(
                tool_msgs[8].reminder, "Only provide change summary when completing."
            )
            self.assertFalse(tool_msgs[9].is_stub)
            self.assertEqual(tool_msgs[9].content, "advance step 3")
            self.assertFalse(tool_msgs[10].is_stub)
            self.assertEqual(tool_msgs[10].content, "advance step 4")

            # Verify Edit 1 was superseded: response is stubbed AND assistant arguments are stubbed all-or-nothing (preserving path and non-string count, replacing other strings with [STUB])
            # Requirement: When a response is replaced with a stub, tool arguments in the correlating assistant invocation message retain their parameter keys, preserving file path parameters, preserving non-string values, and replacing other string values with a stub marker.
            edit1_asst_after = next(
                m for m in history.get_model_request().messages if m.tool_call_id == "call_edit1" and m.role == "assistant"
            )
            self.assertTrue(edit1_asst_after.is_stub)
            parsed_args = json.loads(edit1_asst_after.tool_arguments or "{}")
            self.assertEqual(parsed_args["path"], "file_a.py")
            self.assertEqual(parsed_args["count"], 42)
            self.assertEqual(parsed_args["target_content"], "[STUB]")
            self.assertEqual(parsed_args["replacement_content"], "[STUB]")
            self.assertTrue(tool_msgs[11].is_stub)
            self.assertEqual(tool_msgs[11].content, "[Superseded]")

            # Verify Edit 2, 3, 4 are intact in the buffer
            edit2_asst = next(
                m for m in history.get_model_request().messages if m.tool_call_id == "call_edit2" and m.role == "assistant"
            )
            self.assertFalse(edit2_asst.is_stub)
            self.assertIn("file_b.py", edit2_asst.tool_arguments or "")
            self.assertFalse(tool_msgs[12].is_stub)
            self.assertEqual(tool_msgs[12].content, "diff b")

            edit3_asst = next(
                m for m in history.get_model_request().messages if m.tool_call_id == "call_edit3" and m.role == "assistant"
            )
            self.assertFalse(edit3_asst.is_stub)
            self.assertIn("file_c.py", edit3_asst.tool_arguments or "")
            self.assertFalse(tool_msgs[13].is_stub)
            self.assertEqual(tool_msgs[13].content, "diff c")

            edit4_asst = next(
                m for m in history.get_model_request().messages if m.tool_call_id == "call_edit4" and m.role == "assistant"
            )
            self.assertFalse(edit4_asst.is_stub)
            self.assertIn("file_d.py", edit4_asst.tool_arguments or "")
            self.assertFalse(tool_msgs[14].is_stub)
            self.assertEqual(tool_msgs[14].content, "Error: target_content not found in file_d.py.")

    def test_get_model_request_formats_roles_and_reminders(self) -> None:
        """CUJ: Formatting messages into ModelRequest formats OpenAI conventions and active reminders."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            history = scope.get_singleton(Conversation)
            history.append_message(_make_msg("system", "System instruction"))
            history.append_message(_make_msg("user", "Hello world"))
            resp = _make_response(
                "line 1\nline 2",
                reminder="Remember to write tests.",
            )
            history.append_tool_response(
                resp,
                tool_name=ToolName("advance"),
                tool_call_id=ToolCallId("c1"),
                tool_arguments=SerializedArguments("{}"),
            )
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
            self.assertIn("line 1\nline 2", tool_msg.content)
            self.assertIn("Remember to write tests.", tool_msg.content)

            # ToolResponse with empty content and non-empty reminder
            empty_resp = _make_response(
                "",
                reminder="Remember to finish.",
            )
            history.append_tool_response(
                empty_resp,
                tool_name=ToolName("finish"),
                tool_call_id=ToolCallId("c2"),
                tool_arguments=SerializedArguments("{}"),
            )
            req2 = history.get_model_request()
            # Requirement: Tool execution response notes, content, and reminders from the tool provider are included in visible tool message content, formatting active reminders on messages and superseded stubs to remind the agent in the assembled model request.
            self.assertIn("Remember to finish.", req2.messages[-1].content)

    def test_supersede_arg_keep_edge_cases(self) -> None:
        """CUJ: Exercising all-or-nothing field stubbing, preserving path parameters and non-strings while stubbing other strings."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            history = scope.get_singleton(Conversation)
            history.append_message(
                _make_msg(
                    role="assistant",
                    content="",
                    tool_call_id="call_stub_1",
                    tool_name="edit_file",
                    tool_arguments=json.dumps({
                        "path": "parts/sandbox/lib/foo.py",
                        "target_file": "parts/sandbox/lib/bar.py",
                        "active": True,
                        "count": 100,
                        "description": "Short desc",
                        "replacement_content": "A very long replacement string that previously got sliced to 20 chars",
                    }),
                )
            )
            history.append_tool_response(
                _make_response("result 1", suppression_key="key_stub"),
                tool_name=ToolName("edit_file"),
                tool_call_id=ToolCallId("call_stub_1"),
                tool_arguments=SerializedArguments(
                    json.dumps({
                        "path": "parts/sandbox/lib/foo.py",
                        "target_file": "parts/sandbox/lib/bar.py",
                        "active": True,
                        "count": 100,
                        "description": "Short desc",
                        "replacement_content": "A very long replacement string that previously got sliced to 20 chars",
                    })
                ),
            )
            # Add responses 2 and 3: still within the 3-response buffer
            history.append_tool_response(
                _make_response("result 2", suppression_key="key_stub"),
                tool_name=ToolName("edit_file"),
                tool_call_id=ToolCallId("call_stub_2"),
                tool_arguments=SerializedArguments("{}"),
            )
            history.append_tool_response(
                _make_response("result 3", suppression_key="key_stub"),
                tool_name=ToolName("edit_file"),
                tool_call_id=ToolCallId("call_stub_3"),
                tool_arguments=SerializedArguments("{}"),
            )
            # Response 4 pushes response 1 out of the 3-response buffer
            # Requirement: When a response is replaced with a stub, tool arguments in the correlating assistant invocation message retain their parameter keys, preserving file path parameters, preserving non-string values, and replacing other string values with a stub marker.
            history.append_tool_response(
                _make_response("result 4", suppression_key="key_stub"),
                tool_name=ToolName("edit_file"),
                tool_call_id=ToolCallId("call_stub_4"),
                tool_arguments=SerializedArguments("{}"),
            )

            asst_stub = next(
                m for m in history.get_model_request().messages if m.tool_call_id == "call_stub_1" and m.role == "assistant"
            )
            parsed = json.loads(asst_stub.tool_arguments or "{}")
            # Path parameters preserved intact (no truncation or 20-char slice)
            self.assertEqual(parsed["path"], "parts/sandbox/lib/foo.py")
            self.assertEqual(parsed["target_file"], "parts/sandbox/lib/bar.py")
            # Non-strings preserved intact
            self.assertEqual(parsed["active"], True)
            self.assertEqual(parsed["count"], 100)
            # Other strings replaced with [STUB] (all or nothing, no 20-char slice)
            self.assertEqual(parsed["description"], "[STUB]")
            self.assertEqual(parsed["replacement_content"], "[STUB]")

    def test_initialize_unprompted_tool_response_inserts_synthetic_assistant_call(
        self,
    ) -> None:
        """CUJ: Initializing conversation with unprompted tool responses precedes them with synthetic assistant invocations."""
        tool_msg = _make_msg(
            role="tool",
            content="Unprompted tool output",
            tool_call_id="init_call_1",
            tool_name="view_file",
            tool_arguments='{"path": "foo.py"}',
        )
        already_paired_asst = _make_msg(
            role="assistant",
            content="",
            tool_call_id="paired_call",
            tool_name="check_files",
            tool_arguments="{}",
        )
        already_paired_tool = _make_msg(
            role="tool",
            content="Check passed",
            tool_call_id="paired_call",
            tool_name="check_files",
        )

        with enter_phase(agent_session, registry=self.registry) as scope:
            history = scope.get_singleton(Conversation)
            # Requirement: MUST precede unprompted tool responses with synthetic assistant tool invocations.
            history.initialize([tool_msg, already_paired_asst, already_paired_tool])

            msgs = history.get_model_request().messages
            # Expect synthetic assistant inserted before tool_msg, while already paired calls remain single
            self.assertEqual(len(msgs), 4)
            self.assertEqual(msgs[0].role, "assistant")
            self.assertEqual(msgs[0].tool_call_id, "init_call_1")
            self.assertEqual(msgs[1].role, "tool")
            self.assertEqual(msgs[1].tool_call_id, "init_call_1")
            self.assertEqual(msgs[2].role, "assistant")
            self.assertEqual(msgs[2].tool_call_id, "paired_call")
            self.assertEqual(msgs[3].role, "tool")
            self.assertEqual(msgs[3].tool_call_id, "paired_call")

    def test_append_tool_response_superseded_invalid_json_fallback(self) -> None:
        """CUJ: Superseding a tool response when preceding assistant message has non-JSON arguments falls back gracefully."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            history = scope.get_singleton(Conversation)
            history.append_message(
                _make_msg(
                    role="assistant",
                    content="",
                    tool_call_id="call_bad_json",
                    tool_name="some_tool",
                    tool_arguments="{invalid json: not parsed",
                )
            )
            history.append_tool_response(
                _make_response("out 1", suppression_key="bad_json_key"),
                tool_name=ToolName("some_tool"),
                tool_call_id=ToolCallId("call_bad_json"),
                tool_arguments=SerializedArguments("{invalid json: not parsed"),
            )
            history.append_tool_response(
                _make_response("out 2", suppression_key="bad_json_key"),
                tool_name=ToolName("some_tool"),
                tool_call_id=ToolCallId("call_bad_json_2"),
                tool_arguments=SerializedArguments("{}"),
            )
            history.append_tool_response(
                _make_response("out 3", suppression_key="bad_json_key"),
                tool_name=ToolName("some_tool"),
                tool_call_id=ToolCallId("call_bad_json_3"),
                tool_arguments=SerializedArguments("{}"),
            )
            history.append_tool_response(
                _make_response("out 4", suppression_key="bad_json_key"),
                tool_name=ToolName("some_tool"),
                tool_call_id=ToolCallId("call_bad_json_4"),
                tool_arguments=SerializedArguments("{}"),
            )
            asst_stub = next(
                m for m in history.get_model_request().messages if m.tool_call_id == "call_bad_json" and m.role == "assistant"
            )
            self.assertTrue(asst_stub.is_stub)


if __name__ == "__main__":
    unittest.main()
