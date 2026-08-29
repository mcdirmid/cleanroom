"""
tests/agent_loop_impl_test.py

Unit tests for AgentLoopImpl against its low-level spec.
Exercises OpenAI completions lifecycle, tool dispatch, token accounting,
and delegation to ConversationHistory and LoopGuard protocols via mocks.
"""

import json
import unittest
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

from lib.agent_loop import HistoryEntry, LogEvent, LoggerCallback, ToolCall, ToolDefinition
from lib.agent_loop_config import AgentLoopConfig
from lib.agent_loop_impl import AgentLoopImpl
from lib.conversation_history import ConversationHistory, RenderedMessage
from lib.dag_clean_logic import NoChangeResult
from lib.loop_guard import LoopDecision, LoopGuard
from lib.tool_provider import (
    Continue,
    PresentedToolResult,
    TerminateAgentWithFailure,
    TerminateAgentWithSuccess,
    ToolExecutor,
    ToolFailure,
    ToolResult,
)


class MockConversationHistory:
    def __init__(self) -> None:
        self.history: List[HistoryEntry] = []
        self.rendered: List[RenderedMessage] = []
        self.initialize_called_with: Optional[Tuple[str, Optional[List[PresentedToolResult]]]] = None
        self.reset_called = False

    def reset(self) -> None:
        self.reset_called = True
        self.history = []
        self.rendered = []

    def initialize(
        self,
        prompt: str,
        session_start_results: Optional[List[PresentedToolResult]] = None,
        logger: Optional[LoggerCallback] = None,
    ) -> None:
        self.initialize_called_with = (prompt, session_start_results)
        if prompt:
            self.history.append({"role": "user", "content": prompt})
        if session_start_results:
            for r in session_start_results:
                self.history.append({"role": "tool", "content": r.result.content})

    def append_message(
        self, message: HistoryEntry, logger: Optional[LoggerCallback] = None
    ) -> None:
        self.history.append(message)
        if logger:
            try:
                logger("message_added", {"message": message})
            except Exception:
                pass

    def add_tool_result(
        self,
        tool_call: Optional[ToolCall],
        result: ToolResult | PresentedToolResult,
        logger: Optional[LoggerCallback] = None,
    ) -> None:
        res = result.result if isinstance(result, PresentedToolResult) else result
        self.history.append({"role": "tool", "content": res.content})

    def get_history(self) -> List[HistoryEntry]:
        return self.history

    def get_rendered_messages(
        self, system_prompt: Optional[str] = None
    ) -> List[RenderedMessage]:
        msgs: List[RenderedMessage] = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.extend({"role": m.get("role", "user"), "content": m.get("content", "")} for m in self.history)
        return msgs


class MockLoopGuard:
    def __init__(self) -> None:
        self.reset_called = False
        self.decisions_queue: List[LoopDecision] = []
        self.default_decision: LoopDecision = (False, None, None)
        self.is_degenerate = False
        self.termination_reminder = "You must call advance(), fail(), or blame()."

    def reset(self) -> None:
        self.reset_called = True

    def record_tool_call(self, tool_call: ToolCall) -> LoopDecision:
        if self.decisions_queue:
            return self.decisions_queue.pop(0)
        return self.default_decision

    def check_degenerate_response(self, content: Optional[str]) -> bool:
        return self.is_degenerate

    def get_termination_reminder(self) -> str:
        return self.termination_reminder


def make_config(**overrides: Any) -> AgentLoopConfig:
    params: Dict[str, Any] = {
        "base_url": "http://localhost:8000/v1",
        "api_key": "test-key",
        "model": "test-model",
        "max_iterations": 3,
    }
    params.update(overrides)
    return AgentLoopConfig(**params)


def make_mock_tool_call(call_id: str, name: str, arguments: Dict[str, Any] | str = "{}") -> Any:
    tc = MagicMock()
    tc.id = call_id
    tc.type = "function"
    fn = MagicMock()
    fn.name = name
    fn.arguments = json.dumps(arguments) if isinstance(arguments, dict) else arguments
    tc.function = fn
    return tc


def make_response(
    content: Optional[str] = None,
    tool_calls: Optional[List[Any]] = None,
    finish_reason: str = "stop",
    usage: Optional[Dict[str, Any]] = None,
) -> Any:
    if usage is None:
        usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    mock_choice = MagicMock()
    mock_choice.finish_reason = finish_reason
    mock_message = MagicMock()
    mock_message.content = content
    mock_message.tool_calls = tool_calls
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = usage.get("prompt_tokens", 10)
    mock_usage.completion_tokens = usage.get("completion_tokens", 20)
    mock_usage.total_tokens = usage.get("total_tokens", 30)
    mock_usage.prompt_tokens_details = MagicMock(cached_tokens=0)
    mock_response.usage = mock_usage
    return mock_response


class TestToolExecutor:
    def __init__(self, fn: Any, tools: Optional[List[ToolDefinition]] = None) -> None:
        self._fn = fn
        self._tools = list(tools) if tools is not None else []

    def __call__(self, name: str, arguments: Dict[str, Any]) -> Any:
        return self._fn(name, arguments)

    def get_tool_definitions(self) -> List[ToolDefinition]:
        return self._tools


class TestAgentLoopImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.openai_patcher = patch("lib.agent_loop_impl.OpenAI")
        self.mock_openai_class = self.openai_patcher.start()
        self.addCleanup(self.openai_patcher.stop)
        self.mock_client = self.mock_openai_class.return_value
        self.history = MockConversationHistory()
        self.guard = MockLoopGuard()
        self.agent = AgentLoopImpl(
            config=make_config(),
            conversation_history=self.history,
            loop_guard=self.guard,
        )
        self.events: List[Tuple[LogEvent, Dict[str, Any]]] = []

    def logger(self, event: LogEvent, data: Dict[str, Any]) -> None:
        self.events.append((event, data))

    def test_initialization_and_startup(self) -> None:
        self.mock_client.chat.completions.create.return_value = make_response(
            content=None,
            tool_calls=[make_mock_tool_call("c1", "advance", {})],
            finish_reason="tool_calls",
        )
        executor = TestToolExecutor(lambda name, args: TerminateAgentWithSuccess(NoChangeResult()))
        res = self.agent.run_agent("Hello", [], executor, "System instruction", None, self.logger)

        self.assertEqual(self.history.initialize_called_with, ("Hello", None))
        self.assertTrue(self.guard.reset_called)
        self.assertIsInstance(res[0], TerminateAgentWithSuccess)

    def test_api_call_failure_returns_error(self) -> None:
        self.mock_client.chat.completions.create.side_effect = RuntimeError("Network down")
        executor = TestToolExecutor(lambda name, args: Continue())
        err, hist = self.agent.run_agent("Hello", [], executor, logger=self.logger)
        self.assertIn("API call failed: Network down", str(err))

    def test_finish_reason_stop_with_content_injects_reminder(self) -> None:
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content="Here is text", finish_reason="stop"),
            make_response(
                content=None,
                tool_calls=[make_mock_tool_call("c1", "advance", {})],
                finish_reason="tool_calls",
            ),
        ]
        executor = TestToolExecutor(lambda name, args: TerminateAgentWithSuccess(NoChangeResult()))
        res = self.agent.run_agent("Hello", [], executor, logger=self.logger)
        self.assertIsInstance(res[0], TerminateAgentWithSuccess)
        reminder_events = [e for e in self.events if e[0] == "reminder_injected"]
        self.assertEqual(len(reminder_events), 1)

    def test_finish_reason_length_appends_continuation(self) -> None:
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content="Cut off text", finish_reason="length"),
            make_response(
                content=None,
                tool_calls=[make_mock_tool_call("c1", "advance", {})],
                finish_reason="tool_calls",
            ),
        ]
        executor = TestToolExecutor(lambda name, args: TerminateAgentWithSuccess(NoChangeResult()))
        res = self.agent.run_agent("Hello", [], executor, logger=self.logger)
        self.assertIsInstance(res[0], TerminateAgentWithSuccess)
        truncated_events = [e for e in self.events if e[0] == "response_truncated"]
        self.assertEqual(len(truncated_events), 1)

    def test_finish_reason_length_degenerate_fails_run(self) -> None:
        self.guard.is_degenerate = True
        self.mock_client.chat.completions.create.return_value = make_response(content="aaaa", finish_reason="length")
        executor = TestToolExecutor(lambda name, args: Continue())
        err, _ = self.agent.run_agent("Hello", [], executor, logger=self.logger)
        self.assertIn("Degenerate truncated response", str(err))

    def test_guard_stop_terminates_loop(self) -> None:
        self.guard.default_decision = (True, None, "Repeated 8 times")
        self.mock_client.chat.completions.create.return_value = make_response(
            content=None,
            tool_calls=[make_mock_tool_call("c1", "read", {})],
            finish_reason="tool_calls",
        )
        executor = TestToolExecutor(lambda name, args: Continue())
        err, _ = self.agent.run_agent("Hello", [], executor, logger=self.logger)
        self.assertIn("Repeated 8 times", str(err))

    def test_guard_reminder_injected(self) -> None:
        self.guard.decisions_queue = [(False, "Review your progress", None), (False, None, None)]
        self.mock_client.chat.completions.create.side_effect = [
            make_response(
                content=None,
                tool_calls=[make_mock_tool_call("c1", "read", {})],
                finish_reason="tool_calls",
            ),
            make_response(
                content=None,
                tool_calls=[make_mock_tool_call("c2", "advance", {})],
                finish_reason="tool_calls",
            ),
        ]
        executor = TestToolExecutor(
            lambda name, args: TerminateAgentWithSuccess(NoChangeResult()) if name == "advance" else [ToolResult(content="ok", supersedes=False)]
        )
        res = self.agent.run_agent("Hello", [], executor, logger=self.logger)
        self.assertIsInstance(res[0], TerminateAgentWithSuccess)
        reminder_events = [e for e in self.events if e[0] == "reminder_injected"]
        self.assertEqual(len(reminder_events), 1)

    def test_tool_failure_appended_and_continues(self) -> None:
        self.mock_client.chat.completions.create.side_effect = [
            make_response(
                content=None,
                tool_calls=[make_mock_tool_call("c1", "read", {})],
                finish_reason="tool_calls",
            ),
            make_response(
                content=None,
                tool_calls=[make_mock_tool_call("c2", "advance", {})],
                finish_reason="tool_calls",
            ),
        ]
        executor = TestToolExecutor(
            lambda name, args: TerminateAgentWithSuccess(NoChangeResult()) if name == "advance" else ToolFailure("failed read")
        )
        res = self.agent.run_agent("Hello", [], executor, logger=self.logger)
        self.assertIsInstance(res[0], TerminateAgentWithSuccess)

    def test_max_iterations_exceeded(self) -> None:
        self.mock_client.chat.completions.create.return_value = make_response(
            content=None,
            tool_calls=[make_mock_tool_call("c1", "read", {})],
            finish_reason="tool_calls",
        )
        executor = TestToolExecutor(lambda name, args: [ToolResult(content="ok", supersedes=False)])
        err, _ = self.agent.run_agent("Hello", [], executor, logger=self.logger)
        self.assertIn("Maximum iterations (3) exceeded", str(err))


if __name__ == "__main__":
    unittest.main()
