"""
tests/agent_loop_impl_test.py

Tests for the AgentLoopImpl implementation (lib/agent_loop_impl.py) against
its low-level spec (specs/agent_loop_impl-low.md) and the agent_loop /
tool_provider interfaces it depends on.

The OpenAI client is mocked: no network calls are made. The tool executor
is exercised exactly as the spec's ToolExecutor contract describes - invoked
once per tool call with (name, arguments) and returning a single outcome.
"""

import json
import unittest
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
    Function,
)

from update_with_ai.lib.agent_loop import (
    AgentLoopConfig,
    HistoryEntry,
    LogEvent,
    LoggerCallback,
    ToolDefinition,
)
from update_with_ai.lib.agent_loop_impl import AgentLoopImpl
from update_with_ai.lib.dag_clean_logic import NoChangeResult
from update_with_ai.lib.tool_provider import (
    Continue,
    TerminateAgentWithFailure,
    TerminateAgentWithSuccess,
    ToolFailure,
    ToolResult,
)

# Pinned default continuation prompt (specs/agent_loop_impl-low.md,
# Non-Concerns): appended as a user message when a response is truncated at
# the generation limit and no continuation_prompt is configured.
DEFAULT_CONTINUATION_PROMPT = (
    "Your previous response was cut off because it exceeded the output limit. "
    "Continue from where you left off."
)

# Pinned stub text (specs/agent_loop_impl-low.md, Non-Concerns): the content
# replacing a superseded tool result in place; a stub is static once set.
STUB_TEXT = "Content removed because newer version is available."


def make_config(**overrides: Any) -> AgentLoopConfig:
    """Default AgentLoopConfig for tests; per-test overrides via kwargs."""
    params: Dict[str, Any] = {
        "base_url": "http://localhost:8000/v1",
        "api_key": "test-key",
        "model": "test-model",
        "max_iterations": 3,
    }
    params.update(overrides)
    return AgentLoopConfig(**params)


def make_tool_definitions() -> List[ToolDefinition]:
    """A single tool definition (tool_provider ToolDefinition format)."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            },
        }
    ]


def make_tool_call(
    name: str, call_id: str, args: Dict[str, Any]
) -> ChatCompletionMessageFunctionToolCall:
    """A real OpenAI function tool call object (LLS ToolCall dict shape)."""
    return ChatCompletionMessageFunctionToolCall(
        id=call_id,
        type="function",
        function=Function(name=name, arguments=json.dumps(args)),
    )


def make_response(
    content: Optional[str] = None,
    tool_calls: Optional[List[ChatCompletionMessageFunctionToolCall]] = None,
    finish_reason: str = "stop",
    usage: Optional[Dict[str, int]] = None,
    choices: Optional[List[Any]] = None,
) -> Any:
    """A fake OpenAI chat completion response."""
    if usage is None:
        usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    mock_choice = MagicMock()
    mock_choice.finish_reason = finish_reason
    mock_message = MagicMock()
    mock_message.content = content
    mock_message.tool_calls = tool_calls
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice] if choices is None else choices
    mock_response.usage = MagicMock(
        prompt_tokens=usage["prompt_tokens"],
        completion_tokens=usage["completion_tokens"],
        total_tokens=usage["total_tokens"],
    )
    return mock_response


def make_succeed_response() -> Any:
    """A response whose tool call terminates the run via succeed()."""
    return make_response(
        content=None,
        tool_calls=[make_tool_call("succeed", "call_finish", {"summary": "done"})],
        finish_reason="tool_calls",
    )


class TestAgentLoopImpl(unittest.TestCase):
    """AgentLoopImpl behavior against the agent_loop_impl LLS."""

    def setUp(self) -> None:
        self.openai_patcher = patch("update_with_ai.lib.agent_loop_impl.OpenAI")
        self.mock_openai_class = self.openai_patcher.start()
        self.addCleanup(self.openai_patcher.stop)
        self.mock_client = self.mock_openai_class.return_value
        self.agent = AgentLoopImpl(make_config())

    def inline_result(self, content: Any, note: str = "") -> ToolResult:
        """A result that never supersedes an earlier result."""
        return ToolResult(content=content, supersedes=False, note=note)

    def assert_success(self, result: Any) -> List[HistoryEntry]:
        """Assert a successful termination result (the loop's only completion)."""
        assert isinstance(result, tuple)
        signal, history = result
        assert isinstance(signal, TerminateAgentWithSuccess)
        return history

    def succeed_branch(self) -> None:
        """Insert a succeed branch into the calling test's executor."""
        raise AssertionError("unused")

    def stub_result(self, content: Any, note: str = "") -> ToolResult:
        """A result that supersedes the earlier result for the same file or
        tool command (the agent loop stubs it)."""
        return ToolResult(content=content, supersedes=True, note=note)

    # ---------------------------------------------------------------
    # Normal outcomes
    # ---------------------------------------------------------------

    def test_repeated_identical_tool_call_injects_reminder(self) -> None:
        """
        LLS: when the same tool call (name and arguments) repeats 4
        consecutive times, a reminder is injected once per run and the loop
        continues to a FinalAnswer.
        """
        tool_call = make_tool_call("verify", "call_loop", {})
        responses = [
            make_response(content=None, tool_calls=[tool_call], finish_reason="tool_calls")
        ] * 5
        responses.append(make_succeed_response())
        self.mock_client.chat.completions.create.side_effect = responses

        events: List[Tuple[str, Dict[str, Any]]] = []

        def logger(event: str, data: Dict[str, Any]) -> None:
            events.append((event, data))

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            return self.inline_result("no files changed")

        agent = AgentLoopImpl(make_config(max_iterations=10))
        result = agent.run_agent(
            prompt="update the spec",
            tools=make_tool_definitions(),
            tool_executor=executor,
            logger=logger,
        )
        history = self.assert_success(result)
        reminders = [d for e, d in events if e == "reminder_injected"]
        self.assertEqual(len(reminders), 1)
        self.assertIn("verify", reminders[0]["message"])
        # The reminder text is present in the conversation history.
        history_text = " ".join(str(m.get("content", "")) for m in history)
        self.assertIn("times in a row", history_text)

    def test_same_range_replace_lines_injects_reminder(self) -> None:
        """
        LLS: replace_lines targeting the same file and line range 4
        consecutive times (even with different new_str) injects a
        range-specific reminder once per run; the loop continues.
        """
        # Each call differs (different new_str), so the identical-call
        # detector does not fire; the same-range detector must.
        calls = [
            make_tool_call("replace_lines", f"call_{i}", {
                "file_path": "dag_storage-low.md",
                "start_line": 96,
                "end_line": 100,
                "new_str": "content version %d" % i,
            })
            for i in range(4)
        ]
        responses = [
            make_response(content=None, tool_calls=[calls[i]], finish_reason="tool_calls")
            for i in range(4)
        ]
        responses.append(make_succeed_response())
        self.mock_client.chat.completions.create.side_effect = responses

        events: List[Tuple[str, Dict[str, Any]]] = []

        def logger(event: str, data: Dict[str, Any]) -> None:
            events.append((event, data))

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            return self.stub_result("updated")

        agent = AgentLoopImpl(make_config(max_iterations=10))
        result = agent.run_agent(
            prompt="update the spec",
            tools=make_tool_definitions(),
            tool_executor=executor,
            logger=logger,
        )
        history = self.assert_success(result)
        reminders = [d for e, d in events if e == "reminder_injected"]
        self.assertEqual(len(reminders), 1)
        self.assertIn("96-100", reminders[0]["message"])
        self.assertIn("dag_storage-low.md", reminders[0]["message"])
        self.assertIn("include_line_numbers=True", reminders[0]["message"])
        history_text = " ".join(str(m.get("content", "")) for m in history)
        self.assertIn("edited lines 96-100", history_text)

    def test_repeated_identical_tool_call_fails_run(self) -> None:
        """
        LLS: when the same tool call (name and arguments) repeats 8
        consecutive times, the run signals failure (a degenerate loop) with
        the pinned error text, instead of spinning to the iteration limit.
        """
        tool_call = make_tool_call("verify", "call_loop", {})
        responses = [
            make_response(content=None, tool_calls=[tool_call], finish_reason="tool_calls")
        ] * 8
        self.mock_client.chat.completions.create.side_effect = responses

        events: List[Tuple[str, Dict[str, Any]]] = []

        def logger(event: str, data: Dict[str, Any]) -> None:
            events.append((event, data))

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            return self.inline_result("no files changed")

        agent = AgentLoopImpl(make_config(max_iterations=20))
        result = agent.run_agent(
            prompt="update the spec",
            tools=make_tool_definitions(),
            tool_executor=executor,
            logger=logger,
        )

        assert isinstance(result, tuple)
        error, history = result
        assert isinstance(error, str)
        self.assertEqual(
            error, "Degenerate loop: same tool call repeated 8 consecutive times"
        )
        assert isinstance(history, list)
        # The reminder fired once at 4 repetitions; the run failed at 8.
        reminders = [d for e, d in events if e == "reminder_injected"]
        self.assertEqual(len(reminders), 1)
        self.assertIn("verify", reminders[0]["message"])
        # The run ended at the 8th identical call.
        self.assertEqual(self.mock_client.chat.completions.create.call_count, 8)
        # The failure is logged as an error event.
        error_events = [d for e, d in events if e == "error"]
        self.assertEqual(len(error_events), 1)
        self.assertIn("Degenerate loop", error_events[0]["error"])

    def test_same_range_replace_lines_fails_run(self) -> None:
        """
        LLS: replace_lines targeting the same file and line range 8
        consecutive times (even with different new_str) fails the run with
        the pinned error text.
        """
        calls = [
            make_tool_call("replace_lines", f"call_{i}", {
                "file_path": "dag_storage-low.md",
                "start_line": 96,
                "end_line": 100,
                "new_str": "content version %d" % i,
            })
            for i in range(8)
        ]
        responses = [
            make_response(content=None, tool_calls=[calls[i]], finish_reason="tool_calls")
            for i in range(8)
        ]
        self.mock_client.chat.completions.create.side_effect = responses

        events: List[Tuple[str, Dict[str, Any]]] = []

        def logger(event: str, data: Dict[str, Any]) -> None:
            events.append((event, data))

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            return self.stub_result("updated")

        agent = AgentLoopImpl(make_config(max_iterations=20))
        result = agent.run_agent(
            prompt="update the spec",
            tools=make_tool_definitions(),
            tool_executor=executor,
            logger=logger,
        )

        assert isinstance(result, tuple)
        error, history = result
        assert isinstance(error, str)
        self.assertEqual(
            error,
            "Degenerate loop: replace_lines targeted the same file and line range 8 consecutive times",
        )
        assert isinstance(history, list)
        # The range-specific reminder fired once at 4; the run failed at 8.
        reminders = [d for e, d in events if e == "reminder_injected"]
        self.assertEqual(len(reminders), 1)
        self.assertIn("96-100", reminders[0]["message"])
        self.assertEqual(self.mock_client.chat.completions.create.call_count, 8)

    def test_loop_reminder_not_injected_for_distinct_calls(self) -> None:
        """
        LLS: a reminder is injected only for repeated identical calls;
        distinct calls reset the repetition counter.
        """
        call_a = make_tool_call("read_file", "call_a", {"file_path": "f"})
        call_b = make_tool_call("read_file", "call_b", {"file_path": "g"})
        responses = [
            make_response(content=None, tool_calls=[call_a], finish_reason="tool_calls"),
            make_response(content=None, tool_calls=[call_b], finish_reason="tool_calls"),
            make_response(content=None, tool_calls=[call_a], finish_reason="tool_calls"),
            make_succeed_response(),
        ]
        self.mock_client.chat.completions.create.side_effect = responses

        events: List[Tuple[str, Dict[str, Any]]] = []

        def logger(event: str, data: Dict[str, Any]) -> None:
            events.append((event, data))

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            return self.inline_result("ok")

        agent = AgentLoopImpl(make_config(max_iterations=10))
        result = agent.run_agent(
            prompt="do it",
            tools=make_tool_definitions(),
            tool_executor=executor,
            logger=logger,
        )
        history = self.assert_success(result)
        reminders = [d for e, d in events if e == "reminder_injected"]
        self.assertEqual(reminders, [])

    def test_stop_with_content_injects_termination_reminder(self) -> None:
        """
        LLS: there is no free-text final answer. A model response that stops
        with content (no tool calls) injects the termination reminder (the
        pinned default) and continues; the run fails via the iteration limit
        if the model never signals termination.
        """
        events: List[Tuple[str, Dict[str, Any]]] = []

        def logger(event: LogEvent, data: Dict[str, Any]) -> None:
            events.append((event, data))

        self.mock_client.chat.completions.create.return_value = make_response(
            content="The capital of France is Paris.", finish_reason="stop"
        )

        result = self.agent.run_agent(
            prompt="What is the capital of France?",
            tools=[],
            tool_executor=lambda name, arguments: self.inline_result("unused"),
            logger=logger,
        )

        assert isinstance(result, tuple)
        error, history = result
        assert isinstance(error, str)  # max iterations exceeded: never terminated
        # Every stop injects the reminder: 3 stops under max_iterations=3.
        reminders = [d for e, d in events if e == "reminder_injected"]
        assert len(reminders) == 3
        assert (
            "You must signal termination by calling succeed(), fail(), or "
            "blame() to end the run." == reminders[0]["message"]
        )
        assert any(
            str(m.get("content", "")) == "The capital of France is Paris."
            for m in history
        )
        assert history[0] == {
            "role": "user",
            "content": "What is the capital of France?",
        }

        kwargs = self.mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "test-model"
        assert kwargs["temperature"] == 0.0
        assert "tools" not in kwargs  # no tools advertised to the model

    def test_tool_result_then_final_answer(self) -> None:
        """
        LLS: tool calls are delegated to tool_executor once per tool call
        with (name, arguments); the inline ToolResult is appended and the
        loop continues to a FinalAnswer.
        """
        tool_call = make_tool_call("get_weather", "call_123", {"location": "San Francisco"})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=[tool_call], finish_reason="tool_calls"),
            make_response(content="It is sunny in San Francisco.", finish_reason="stop"),
            make_succeed_response(),
        ]

        calls: List[Tuple[str, Dict[str, Any]]] = []

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            calls.append((name, arguments))
            return self.inline_result('{"weather": "Sunny"}')

        result = self.agent.run_agent(
            prompt="What's the weather in San Francisco?",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        history = self.assert_success(result)
        assert any(str(m.get("content", "")) == "It is sunny in San Francisco." for m in history)
        # Once per tool call, with the parsed arguments and the tool name.
        assert calls == [("get_weather", {"location": "San Francisco"})]

        # Tool result immediately follows the tool call in chronological order.
        history = history
        tool_messages = [m for m in history if m.get("role") == "tool"]
        assert len(tool_messages) == 1
        assert tool_messages[0]["tool_call_id"] == "call_123"
        assert tool_messages[0]["content"] == '{"weather": "Sunny"}'
        assistant_index = next(
            i for i, m in enumerate(history) if m.get("role") == "assistant"
        )
        assert history.index(tool_messages[0]) > assistant_index
        assert self.mock_client.chat.completions.create.call_count == 3

    def test_terminate_agent_with_success_stops_loop(self) -> None:
        """
        LLS: (TerminateAgentWithSuccess, history) when tool_executor returns
        TerminateAgentWithSuccess; termination values pass through unchanged
        and termination is terminal (no further API calls).
        """
        tool_call = make_tool_call("finish", "call_1", {})
        self.mock_client.chat.completions.create.return_value = make_response(
            content=None, tool_calls=[tool_call], finish_reason="tool_calls"
        )

        term_value: Any = {"status": "done"}
        term_signal = TerminateAgentWithSuccess(value=term_value)

        def executor(name: str, arguments: Dict[str, Any]) -> TerminateAgentWithSuccess:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            return term_signal

        result = self.agent.run_agent(
            prompt="Finish the task",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        assert isinstance(result, tuple)
        signal, history = result
        assert isinstance(signal, TerminateAgentWithSuccess)
        assert signal.value is term_value  # passes through unchanged
        # user prompt + assistant tool call only; no tool result, no follow-up call.
        assert [m["role"] for m in history] == ["user", "assistant"]
        assert self.mock_client.chat.completions.create.call_count == 1

    def test_terminate_agent_with_failure_stops_loop(self) -> None:
        """
        LLS: (TerminateAgentWithFailure[T_tool], history) when tool_executor
        returns TerminateAgentWithFailure[T_tool]; T_tool = str.
        """
        tool_call = make_tool_call("finish", "call_1", {})
        self.mock_client.chat.completions.create.return_value = make_response(
            content=None, tool_calls=[tool_call], finish_reason="tool_calls"
        )

        def executor(name: str, arguments: Dict[str, Any]) -> TerminateAgentWithFailure[str]:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            return TerminateAgentWithFailure(value="agent cannot complete this task")

        result = self.agent.run_agent(
            prompt="Finish the task",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        assert isinstance(result, tuple)
        signal, history = result
        assert isinstance(signal, TerminateAgentWithFailure)
        assert signal.value == "agent cannot complete this task"  # passes through
        assert [m["role"] for m in history] == ["user", "assistant"]
        assert self.mock_client.chat.completions.create.call_count == 1

    # ---------------------------------------------------------------
    # Error outcomes: (error, history)
    # ---------------------------------------------------------------

    def test_api_call_failure_returns_error(self) -> None:
        """
        LLS: returns (error, history) when the API call fails.
        """
        self.mock_client.chat.completions.create.side_effect = Exception("connection refused")

        result = self.agent.run_agent(
            prompt="Hello",
            tools=[],
            tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
        )

        assert isinstance(result, tuple)
        error, history = result
        assert isinstance(error, str)
        # LLS: an API failure returns (error, history); the wording is unspecified.
        assert [m["role"] for m in history] == ["user"]

    def test_malformed_responses_return_error(self) -> None:
        """
        LLS: returns (error, history) when the API returns a malformed
        response: empty choices, stop-without-content, tool_calls-without-calls,
        content_filter truncation, and unknown finish_reason. A truncated
        response (finish_reason 'length') is not malformed: it resumes
        generation (see the truncation tests).
        """
        cases: List[Tuple[Any, str]] = [
            (make_response(choices=[]), "API returned empty response"),
            (
                make_response(content=None, finish_reason="stop"),
                "API returned stop but no content",
            ),
            (
                make_response(content=None, tool_calls=None, finish_reason="tool_calls"),
                "API indicated tool_calls but no tool_calls present",
            ),
            (
                make_response(content="x", finish_reason="content_filter"),
                "Incomplete response: content_filter",
            ),
            (
                make_response(content="x", finish_reason="bogus"),
                "Unknown finish_reason: bogus",
            ),
        ]
        for response, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                self.mock_client.chat.completions.create.return_value = response
                result = self.agent.run_agent(
                    prompt="Hello",
                    tools=[],
                    tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
                )
                assert isinstance(result, tuple)
                error, history = result
                assert isinstance(error, str)
                assert error == expected_error
                assert isinstance(history, list)

    # ---------------------------------------------------------------
    # Truncated responses (finish_reason 'length')
    # ---------------------------------------------------------------

    def test_truncated_response_continues_to_final_answer(self) -> None:
        """
        LLS: a response truncated at the generation limit is not treated as
        complete; the default continuation prompt is appended and the loop
        resumes with a follow-up API call.
        """
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content="Let me think...", finish_reason="length"),
            make_succeed_response(),
        ]

        result = self.agent.run_agent(
            prompt="Solve it",
            tools=[],
            tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
        )

        history = self.assert_success(result)
        assert any(
            m.get("content") == "Let me think..." for m in history
        )
        assert any(m.get("content") == DEFAULT_CONTINUATION_PROMPT for m in history)
        assert self.mock_client.chat.completions.create.call_count == 2
        # The truncated assistant content is present, followed by the default
        # continuation prompt (pinned in the impl LLS).
        truncated = [
            m
            for m in history
            if m.get("role") == "assistant" and m.get("content") == "Let me think..."
        ]
        assert len(truncated) == 1
        continuation = [
            m
            for m in history
            if m.get("role") == "user" and m.get("content") == DEFAULT_CONTINUATION_PROMPT
        ]
        assert len(continuation) == 1
        assert history.index(truncated[0]) < history.index(continuation[0])

        # The continuation prompt is included in the follow-up API call.
        second_messages = self.mock_client.chat.completions.create.call_args_list[1].kwargs[
            "messages"
        ]
        assert any(
            m.get("role") == "user" and m.get("content") == DEFAULT_CONTINUATION_PROMPT
            for m in second_messages
        )

    def test_truncated_response_tool_calls_never_executed(self) -> None:
        """
        LLS: tool calls present in a truncated response are not executed and
        not retried; the assistant message appended from the truncated
        response omits them.
        """
        tool_call = make_tool_call("get_weather", "call_1", {"location": "SF"})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(
                content="Let me check the weather...",
                tool_calls=[tool_call],
                finish_reason="length",
            ),
            make_succeed_response(),
        ]

        invocations: List[Tuple[str, Dict[str, Any]]] = []

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            invocations.append((name, arguments))
            return self.inline_result("x")

        result = self.agent.run_agent(
            prompt="Weather?",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        history = self.assert_success(result)
        # The truncated tool call is never executed and never retried.
        assert invocations == []

        # The appended assistant message omits the tool calls.
        truncated_assistant = [
            m
            for m in history
            if m.get("role") == "assistant"
            and m.get("content") == "Let me check the weather..."
        ]
        assert len(truncated_assistant) == 1
        assert "tool_calls" not in truncated_assistant[0]

        # No tool calls from the truncated response reach any API request.
        for call in self.mock_client.chat.completions.create.call_args_list:
            for msg in call.kwargs["messages"]:
                assert not msg.get("tool_calls")

    def test_truncated_response_without_content_appends_only_continuation(self) -> None:
        """
        LLS: a truncated response with neither content nor tool calls is not
        appended; only the continuation prompt follows.
        """
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=None, finish_reason="length"),
            make_succeed_response(),
        ]

        result = self.agent.run_agent(
            prompt="Go",
            tools=[],
            tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
        )

        history = self.assert_success(result)
        assistant_messages = [m for m in history if m.get("role") == "assistant"]
        # Only the succeed tool-call assistant message: the empty truncated
        # response was not appended.
        assert len(assistant_messages) == 1
        assert assistant_messages[0]["content"] is None
        assert any(
            m.get("role") == "user" and m.get("content") == DEFAULT_CONTINUATION_PROMPT
            for m in history
        )

    def test_degenerate_truncated_response_signals_failure(self) -> None:
        """
        LLS: a truncated response whose content is a single character
        repeated (all characters identical) is not resumed; the run returns
        (error, history) with the pinned error text, and neither the
        truncated response nor the continuation prompt is appended.
        """
        self.mock_client.chat.completions.create.return_value = make_response(
            content="!" * 4096, finish_reason="length"
        )

        result = self.agent.run_agent(
            prompt="Go",
            tools=[],
            tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
        )

        assert isinstance(result, tuple)
        error, history = result
        assert isinstance(error, str)
        # Pinned in the impl LLS (Error Handling).
        assert error == "Degenerate truncated response: single character repeated"
        # Nothing appended for the degenerate turn: only the user prompt.
        assert [m["role"] for m in history] == ["user"]
        assert not any(
            m.get("content") == DEFAULT_CONTINUATION_PROMPT for m in history
        )
        # No continuation, no follow-up request.
        assert self.mock_client.chat.completions.create.call_count == 1

    def test_single_character_truncated_response_signals_failure(self) -> None:
        """
        LLS: a truncated response of a single character is degenerate (all
        characters identical) and signals failure.
        """
        self.mock_client.chat.completions.create.return_value = make_response(
            content="!", finish_reason="length"
        )

        result = self.agent.run_agent(
            prompt="Go",
            tools=[],
            tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
        )

        assert isinstance(result, tuple)
        error, history = result
        assert isinstance(error, str)
        assert error == "Degenerate truncated response: single character repeated"
        assert [m["role"] for m in history] == ["user"]

    def test_truncated_response_uses_custom_continuation_prompt(self) -> None:
        """
        LLS: when continuation_prompt is configured, it is appended instead
        of the default.
        """
        agent = AgentLoopImpl(make_config(continuation_prompt="Keep going!"))
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content="Partial.", finish_reason="length"),
            make_response(content="Done.", finish_reason="stop"),
            make_succeed_response(),
        ]

        result = agent.run_agent(
            prompt="Go",
            tools=[],
            tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
        )

        history = self.assert_success(result)
        assert any(str(m.get("content", "")) == "Done." for m in history)
        assert any(
            m.get("role") == "user" and m.get("content") == "Keep going!"
            for m in history
        )
        assert not any(
            m.get("role") == "user" and m.get("content") == DEFAULT_CONTINUATION_PROMPT
            for m in history
        )

    def test_truncation_until_max_iterations_fails(self) -> None:
        """
        LLS: each follow-up request counts toward the iteration limit; a run
        that truncates until the limit is exceeded signals failure.
        """
        agent = AgentLoopImpl(make_config(max_iterations=2))
        self.mock_client.chat.completions.create.return_value = make_response(
            content="Still going...", finish_reason="length"
        )

        result = agent.run_agent(
            prompt="Go",
            tools=[],
            tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
        )

        assert isinstance(result, tuple)
        error, history = result
        assert isinstance(error, str)
        assert "Maximum iterations" in error
        assert self.mock_client.chat.completions.create.call_count == 2
        # Each truncated response contributed an assistant message and a
        # continuation prompt.
        assert len([m for m in history if m.get("role") == "assistant"]) == 2
        assert (
            len([m for m in history if m.get("content") == DEFAULT_CONTINUATION_PROMPT])
            == 2
        )

    def test_response_truncated_logger_event(self) -> None:
        """
        LLS: a response_truncated event is emitted when the model response
        stops at the generation limit, with the truncated message and usage.
        """
        events: List[Tuple[str, Dict[str, Any]]] = []

        def logger(event: LogEvent, data: Dict[str, Any]) -> None:
            events.append((event, data))

        self.mock_client.chat.completions.create.side_effect = [
            make_response(content="Partial.", finish_reason="length"),
            make_succeed_response(),
        ]

        result = self.agent.run_agent(
            prompt="Go",
            tools=[],
            tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
            logger=logger,
        )

        history = self.assert_success(result)
        truncated_events = [e for e in events if e[0] == "response_truncated"]
        assert len(truncated_events) == 1
        assert truncated_events[0][1]["message"]["content"] == "Partial."
        assert truncated_events[0][1]["usage"] == {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        }
        # The continuation prompt append is reported via message_added after
        # the response_truncated event.
        assert any(
            e[0] == "message_added"
            and e[1]["message"].get("content") == DEFAULT_CONTINUATION_PROMPT
            for e in events
        )

    def test_tool_executor_exception_returns_error(self) -> None:
        """
        LLS: returns (error, history) when tool_executor raises an exception
        (state unchanged).
        """
        tool_call = make_tool_call("get_weather", "call_1", {})
        self.mock_client.chat.completions.create.return_value = make_response(
            content=None, tool_calls=[tool_call], finish_reason="tool_calls"
        )

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            raise RuntimeError("boom")

        result = self.agent.run_agent(
            prompt="What's the weather?",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        assert isinstance(result, tuple)
        error, history = result
        assert isinstance(error, str)
        # LLS: a tool-executor exception returns (error, history); wording unspecified.
        assert history[-1]["role"] == "assistant"

    def test_max_iterations_exceeded_returns_error(self) -> None:
        """
        LLS: returns (error, history) when the maximum iterations are exceeded.
        """
        agent = AgentLoopImpl(make_config(max_iterations=2))
        tool_call = make_tool_call("get_weather", "call_1", {})
        self.mock_client.chat.completions.create.return_value = make_response(
            content=None, tool_calls=[tool_call], finish_reason="tool_calls"
        )

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            return self.inline_result("42")

        result = agent.run_agent(
            prompt="What's the weather?",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        assert isinstance(result, tuple)
        error, history = result
        assert isinstance(error, str)
        # LLS: exceeding max iterations returns (error, history); wording unspecified.
        assert self.mock_client.chat.completions.create.call_count == 2
        assert len([m for m in history if m.get("role") == "assistant"]) == 2

    # ---------------------------------------------------------------
    # Signals from tool_executor
    # ---------------------------------------------------------------

    def test_tool_failure_appended_and_loop_continues(self) -> None:
        """
        LLS: a ToolFailure from tool_executor is appended to the conversation
        as a tool result and the loop continues (recoverable; no agent failure).
        """
        tool_call = make_tool_call("get_weather", "call_1", {"location": "???"})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=[tool_call], finish_reason="tool_calls"),
            make_response(content="Let me retry with valid arguments.", finish_reason="stop"),
            make_succeed_response(),
        ]

        def executor(name: str, arguments: Dict[str, Any]) -> ToolFailure[str]:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            return ToolFailure(value="Invalid arguments: location is required")

        result = self.agent.run_agent(
            prompt="What's the weather?",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        history = self.assert_success(result)
        assert any(str(m.get("content", "")) == "Let me retry with valid arguments." for m in history)
        tool_messages = [m for m in history if m.get("role") == "tool"]
        assert len(tool_messages) == 1
        # The failure message becomes the tool result content.
        assert tool_messages[0]["content"] == "Invalid arguments: location is required"
        # No stubbing metadata exists (a tool failure never supersedes).
        assert "_stub_key" not in tool_messages[0]
        assert self.mock_client.chat.completions.create.call_count == 3

    def test_tool_failure_never_supersedes(self) -> None:
        """
        LLS: a ToolFailure is appended to the conversation as a tool result
        and the loop continues (recoverable); it never supersedes an earlier
        result — an earlier read of the same file stays live (not stubbed).
        """
        agent = AgentLoopImpl(make_config(max_iterations=4))
        read_call = make_tool_call("read_file", "call_1", {"path": "foo.txt"})
        edit_call = make_tool_call("replace_lines", "call_2", {"path": "foo.txt"})
        agent._client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=[read_call], finish_reason="tool_calls"),
            make_response(content=None, tool_calls=[edit_call], finish_reason="tool_calls"),
            make_succeed_response(),
        ]

        def executor(name: str, arguments: Dict[str, Any]) -> Any:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            if name == "replace_lines":
                return ToolFailure(
                    value=(
                        "replace_lines requires the line-numbered view: call "
                        "read_file('foo.txt', include_line_numbers=True)"
                    )
                )
            # read_file: a writable-file read supersedes the earlier result
            # for the file.
            return ToolResult(
                content="line1\nline2",
                supersedes=True,
                note="Read 2 lines (line-numbered)",
            )

        events: List[Tuple[str, Dict[str, Any]]] = []

        def logger(event: str, data: Dict[str, Any]) -> None:
            events.append((event, data))

        result = agent.run_agent(
            prompt="Edit foo.txt",
            tools=make_tool_definitions(),
            tool_executor=executor,
            logger=logger,
        )

        history = self.assert_success(result)
        tool_messages = [m for m in history if m.get("role") == "tool"]
        # Read, failure: two tool messages.
        assert len(tool_messages) == 2
        # The failure message is appended as a tool result (a reminder).
        assert "include_line_numbers=True" in tool_messages[1]["content"]
        # The earlier read is NOT stubbed by the failure: its content is live.
        assert tool_messages[0]["content"] == "line1\nline2"
        # A tool failure carries no close_buffer (no buffers to close).
        assert not hasattr(ToolFailure(value="x"), "close_buffer")
        # No message_stubbed event was emitted for the failure.
        assert all(e != "message_stubbed" for e, _ in events)

    def test_continue_signal_produces_no_tool_result(self) -> None:
        """
        LLS: a Continue from tool_executor produces no tool result and the
        loop continues.
        """
        tool_call = make_tool_call("get_weather", "call_1", {})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=[tool_call], finish_reason="tool_calls"),
            make_succeed_response(),
        ]

        invocations: List[str] = []

        def executor(name: str, arguments: Dict[str, Any]) -> Continue:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            invocations.append(name)
            return Continue()

        result = self.agent.run_agent(
            prompt="Do something",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        history = self.assert_success(result)
        assert invocations == ["get_weather"]
        assert [m for m in history if m.get("role") == "tool"] == []
        assert self.mock_client.chat.completions.create.call_count == 2

    # ---------------------------------------------------------------
    # Stubbing: supersedes flag -> in-place stub of the earlier result
    # ---------------------------------------------------------------

    def test_non_superseding_result_appended_without_stubbing(self) -> None:
        """
        LLS: a result with the supersedes flag unset is appended to the
        conversation; nothing is stubbed, no matter how many arrive.
        """
        tc1 = make_tool_call("read_file", "call_1", {"file_path": "ro.txt"})
        tc2 = make_tool_call("read_file", "call_2", {"file_path": "ro.txt"})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=[tc1], finish_reason="tool_calls"),
            make_response(content=None, tool_calls=[tc2], finish_reason="tool_calls"),
            make_succeed_response(),
        ]

        events: List[Tuple[str, Dict[str, Any]]] = []

        def logger(event: LogEvent, data: Dict[str, Any]) -> None:
            events.append((event, data))

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            return self.inline_result("raw data")

        result = self.agent.run_agent(
            prompt="Read the file twice",
            tools=make_tool_definitions(),
            tool_executor=executor,
            logger=logger,
        )

        history = self.assert_success(result)
        tool_messages = [m for m in history if m.get("role") == "tool"]
        assert len(tool_messages) == 2
        for msg in tool_messages:
            assert msg["content"] == "raw data"
            assert STUB_TEXT not in msg["content"]
        # No stubbing occurred.
        assert all(e != "message_stubbed" for e, _ in events)

    def test_superseding_result_stubs_earlier_result(self) -> None:
        """
        LLS: a result with the supersedes flag set stubs the earlier
        non-stubbed result for the same file (here: the file's virtual name
        in the tool call's file_path argument) in place — the stubbed message
        keeps its position and its content is replaced by the pinned static
        stub text — the message_stubbed event is emitted with the stubbed
        message and the replacement message, and the new result becomes the
        live result for that file.
        """
        tc1 = make_tool_call("read_file", "call_1", {"file_path": "foo.txt"})
        tc2 = make_tool_call("read_file", "call_2", {"file_path": "foo.txt"})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=[tc1], finish_reason="tool_calls"),
            make_response(content=None, tool_calls=[tc2], finish_reason="tool_calls"),
            make_succeed_response(),
        ]

        events: List[Tuple[str, Dict[str, Any]]] = []

        def logger(event: LogEvent, data: Dict[str, Any]) -> None:
            events.append((event, data))

        counter: Dict[str, int] = {"n": 0}

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            counter["n"] += 1
            return ToolResult(
                content=f"version {counter['n']}",
                supersedes=True,
                note="Read 2 lines (plain)",
            )

        result = self.agent.run_agent(
            prompt="Read foo.txt twice",
            tools=make_tool_definitions(),
            tool_executor=executor,
            logger=logger,
        )

        history = self.assert_success(result)
        # Two tool messages, both keeping their positions (append-only except
        # for in-place stubbing).
        tool_messages = [m for m in history if m.get("role") == "tool"]
        assert len(tool_messages) == 2
        # The first is stubbed in place with the pinned static stub text.
        assert tool_messages[0]["content"] == STUB_TEXT
        # The second is the live result for the file.
        assert tool_messages[1]["content"] == "version 2"
        assert tool_messages[1].get("note", "") == ""

        # The message_stubbed event carries the stubbed message and the
        # replacement message.
        stubbed_events = [d for e, d in events if e == "message_stubbed"]
        assert len(stubbed_events) == 1
        assert stubbed_events[0]["stubbed_message"]["content"] == STUB_TEXT
        assert stubbed_events[0]["replacement_message"]["content"] == "version 2"

        # The follow-up request shows the stub in the first tool message's
        # position and the live content (with its note appended, per the LLS)
        # at the end — the prefix up to the most recent live result is
        # preserved.
        third_messages = self.mock_client.chat.completions.create.call_args_list[2].kwargs[
            "messages"
        ]
        tool_contents = [
            m.get("content", "")
            for m in third_messages
            if m.get("role") == "tool"
        ]
        assert tool_contents[0] == STUB_TEXT
        assert tool_contents[1] == "version 2\nRead 2 lines (plain)"

    def test_different_files_do_not_stub_each_other(self) -> None:
        """
        LLS: a result supersedes the earlier result for the SAME file or tool
        command only; results for different files do not affect each other.
        """
        tc1 = make_tool_call("read_file", "call_1", {"file_path": "a.txt"})
        tc2 = make_tool_call("read_file", "call_2", {"file_path": "b.txt"})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=[tc1], finish_reason="tool_calls"),
            make_response(content=None, tool_calls=[tc2], finish_reason="tool_calls"),
            make_succeed_response(),
        ]

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            return self.stub_result("content for " + arguments.get("file_path", "?"))

        result = self.agent.run_agent(
            prompt="Read both files",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        history = self.assert_success(result)
        tool_messages = [m for m in history if m.get("role") == "tool"]
        assert len(tool_messages) == 2
        # Both live: each is the first result for its own file.
        assert tool_messages[0]["content"] == "content for a.txt"
        assert tool_messages[1]["content"] == "content for b.txt"

    def test_verify_result_stubs_earlier_verify_result(self) -> None:
        """
        LLS: a verification result supersedes the earlier non-stubbed
        verification result — keyed by the tool command itself (verify has
        no file_path argument).
        """
        tc1 = make_tool_call("verify", "call_1", {})
        tc2 = make_tool_call("verify", "call_2", {})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=[tc1], finish_reason="tool_calls"),
            make_response(content=None, tool_calls=[tc2], finish_reason="tool_calls"),
            make_succeed_response(),
        ]

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            return self.stub_result("verification report")

        result = self.agent.run_agent(
            prompt="Verify twice",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        history = self.assert_success(result)
        tool_messages = [m for m in history if m.get("role") == "tool"]
        assert len(tool_messages) == 2
        assert tool_messages[0]["content"] == STUB_TEXT
        assert tool_messages[1]["content"] == "verification report"

    # ---------------------------------------------------------------
    # System prompt
    # ---------------------------------------------------------------

    def test_system_prompt_sent_first_not_in_history(self) -> None:
        """
        LLS: the conversation context is organized as the system prompt, then
        the agent conversation; the system prompt is not part of the
        conversation history.
        """
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content="Done.", finish_reason="stop"),
            make_succeed_response(),
        ]

        result = self.agent.run_agent(
            prompt="Build it",
            tools=[],
            tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
            system_prompt="You are a builder.",
        )

        history = self.assert_success(result)
        # The system prompt opens the API request.
        messages = self.mock_client.chat.completions.create.call_args_list[0].kwargs["messages"]
        assert messages[0] == {"role": "system", "content": "You are a builder."}
        # The history contains only conversation messages (no system message;
        # the termination reminder is a user message).
        assert all(m.get("role") != "system" for m in history)

    def test_empty_prompt_sends_no_user_message(self) -> None:
        """
        LLS: an empty prompt sends no user message.
        """
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content="I will act.", finish_reason="stop"),
            make_succeed_response(),
        ]

        result = self.agent.run_agent(
            prompt="",
            tools=[],
            tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
            system_prompt="Act on the files.",
        )

        history = self.assert_success(result)
        messages = self.mock_client.chat.completions.create.call_args_list[0].kwargs["messages"]
        assert messages[0] == {"role": "system", "content": "Act on the files."}
        assert not any(m.get("role") == "user" for m in messages)
        # History starts with the assistant message (empty prompt: no user
        # message; the termination reminder and tool results follow later).
        assert history[0]["role"] == "assistant"

    # ---------------------------------------------------------------
    # Termination reminder
    # ---------------------------------------------------------------

    def test_termination_reminder_injected_on_every_stop(self) -> None:
        """
        LLS: there is no free-text final answer. When the model stops with
        free text, the termination reminder is injected on EVERY stop (using
        the configured generator's message when present) and the loop
        continues until a termination signal.
        """
        events: List[Tuple[str, Dict[str, Any]]] = []

        def logger(event: LogEvent, data: Dict[str, Any]) -> None:
            events.append((event, data))

        agent = AgentLoopImpl(
            make_config(termination_reminder_generator=lambda: "You must use a tool to finish.")
        )
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content="I think I'm done.", finish_reason="stop"),
            make_response(content="OK, I will use the tool.", finish_reason="stop"),
            make_succeed_response(),
        ]

        result = agent.run_agent(
            prompt="Do something",
            tools=[],
            tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
            logger=logger,
        )

        history = self.assert_success(result)
        assert self.mock_client.chat.completions.create.call_count == 3

        # Every stop injected the generator's message into the conversation.
        reminder_messages = [
            m
            for m in history
            if m.get("role") == "user" and m.get("content") == "You must use a tool to finish."
        ]
        assert len(reminder_messages) == 2

        # One reminder_injected event per stop, using the generator's message.
        reminder_events = [e for e in events if e[0] == "reminder_injected"]
        assert len(reminder_events) == 2
        assert all(
            e[1]["message"] == "You must use a tool to finish." for e in reminder_events
        )

        # Each appended reminder was reported via message_added, before the
        # reminder_injected event (logger invoked after each history update).
        reminder_added = [
            e
            for e in events
            if e[0] == "message_added"
            and e[1]["message"].get("content") == "You must use a tool to finish."
        ]
        assert len(reminder_added) == 2
        assert events.index(reminder_added[0]) < events.index(reminder_events[0])

        # Each reminder is included in the follow-up API call.
        for i in (1, 2):
            messages = self.mock_client.chat.completions.create.call_args_list[i].kwargs[
                "messages"
            ]
            assert any(
                m.get("role") == "user"
                and m.get("content") == "You must use a tool to finish."
                for m in messages
            )

    # ---------------------------------------------------------------
    # Message hygiene and logging
    # ---------------------------------------------------------------

    def test_internal_metadata_stripped_before_api_calls(self) -> None:
        """
        LLS: internal metadata fields (_-prefixed) are stripped before
        sending messages to the API.
        """
        tool_call = make_tool_call("read_file", "call_1", {"path": "/tmp/f.txt"})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=[tool_call], finish_reason="tool_calls"),
            make_succeed_response(),
        ]

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            return self.inline_result("file data")

        result = self.agent.run_agent(
            prompt="Read the file",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        history = self.assert_success(result)

        # No _-prefixed keys in any message sent to the API on any call.
        for call in self.mock_client.chat.completions.create.call_args_list:
            for msg in call.kwargs["messages"]:
                assert not any(k.startswith("_") for k in msg.keys())

        # Assistant tool calls are converted to the LLS ToolCall dict shape.
        second_messages = self.mock_client.chat.completions.create.call_args_list[1].kwargs[
            "messages"
        ]
        assistant = next(m for m in second_messages if m.get("role") == "assistant")
        assert assistant["tool_calls"][0]["id"] == "call_1"
        assert assistant["tool_calls"][0]["type"] == "function"
        assert assistant["tool_calls"][0]["function"]["name"] == "read_file"
        assert assistant["tool_calls"][0]["function"]["arguments"] == '{"path": "/tmp/f.txt"}'

        # Tool messages reference the originating tool call.
        tool_msg = next(m for m in second_messages if m.get("role") == "tool")
        assert tool_msg["tool_call_id"] == "call_1"
        assert tool_msg["content"] == "file data"

    def test_tool_result_note_rendered_into_model_visible_content(self) -> None:
        """
        LLS: a ToolResult's note is consumed by the agent's model execution:
        it is carried as internal metadata (_note) and rendered into the
        model-visible tool message content, which is otherwise pure file data.
        """
        tool_call = make_tool_call("read_file", "call_1", {"path": "/tmp/f.txt"})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=[tool_call], finish_reason="tool_calls"),
            make_succeed_response(),
        ]

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            return self.inline_result(
                "file data",
                note="Read 4 lines (plain)",
            )

        result = self.agent.run_agent(
            prompt="Read the file",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        history = self.assert_success(result)

        # The internal history message carries the note as metadata.
        tool_msg = next(m for m in history if m.get("role") == "tool")
        assert tool_msg["content"] == "file data"
        assert tool_msg["_note"] == "Read 4 lines (plain)"

        # The API message renders the note into the content and strips the
        # internal _note key.
        second_messages = self.mock_client.chat.completions.create.call_args_list[1].kwargs[
            "messages"
        ]
        api_tool = next(m for m in second_messages if m.get("role") == "tool")
        assert api_tool["content"] == "file data\nRead 4 lines (plain)"
        assert "_note" not in api_tool

    def test_logger_invoked_after_each_history_update(self) -> None:
        """
        LLS: the logger is invoked after each history update, in
        chronological order, with the documented events.
        """
        events: List[LogEvent] = []

        def logger(event: LogEvent, data: Dict[str, Any]) -> None:
            events.append(event)

        self.mock_client.chat.completions.create.side_effect = [
            make_response(content="Hello back.", finish_reason="stop"),
            make_succeed_response(),
        ]

        result = self.agent.run_agent(
            prompt="Hi",
            tools=[],
            tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
            logger=logger,
        )

        history = self.assert_success(result)
        # Each history append fires message_added after the append; reminders
        # fire message_added then reminder_injected; the run ends with
        # tool_called/run_terminated in chronological order. No tool_result
        # event fires for the termination signal: a termination signal is not
        # a ToolResult (LLS logger table: "tool_result | Tool results
        # received"), so no tool result is received on this path.
        assert events == [
            "message_added",  # user prompt
            "api_response",   # stop response
            "message_added",  # assistant "Hello back." message appended
            "message_added",  # termination reminder appended
            "reminder_injected",
            "api_response",   # succeed response
            "message_added",  # assistant tool-call message appended
            "tool_called",
            "run_terminated",
        ]

    def test_logger_exceptions_ignored(self) -> None:
        """
        LLS: logger callback exceptions are caught and ignored; the run
        still completes.
        """
        def logger(event: LogEvent, data: Dict[str, Any]) -> None:
            raise RuntimeError("logger exploded")

        self.mock_client.chat.completions.create.side_effect = [
            make_response(content="Still works.", finish_reason="stop"),
            make_succeed_response(),
        ]

        result = self.agent.run_agent(
            prompt="Hi",
            tools=[],
            tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
            logger=logger,
        )

        history = self.assert_success(result)
        assert any(str(m.get("content", "")) == "Still works." for m in history)

    # ---------------------------------------------------------------
    # Usage and configuration
    # ---------------------------------------------------------------

    def test_cumulative_usage_request_count_increments(self) -> None:
        """
        LLS: cumulative usage is tracked across API calls; request_count
        increments once per call; per-request usage is reported via
        api_response.
        """
        tool_call = make_tool_call("get_weather", "call_1", {})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(
                content=None,
                tool_calls=[tool_call],
                finish_reason="tool_calls",
                usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            ),
            make_response(
                content="Sunny.",
                finish_reason="stop",
                usage={"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
            ),
            make_succeed_response(),
        ]

        events: List[Tuple[str, Dict[str, Any]]] = []

        def logger(event: LogEvent, data: Dict[str, Any]) -> None:
            events.append((event, data))

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            if name == "succeed":
                return TerminateAgentWithSuccess(NoChangeResult())
            return self.inline_result("x")

        result = self.agent.run_agent(
            prompt="Weather?",
            tools=make_tool_definitions(),
            tool_executor=executor,
            logger=logger,
        )

        history = self.assert_success(result)
        final_events = [e for e in events if e[0] == "run_terminated"]
        assert len(final_events) == 1
        assert final_events[0][1]["cumulative_usage"] == {
            "prompt_tokens": 25,
            "completion_tokens": 47,
            "total_tokens": 72,
            "request_count": 3,
        }
        api_events = [e for e in events if e[0] == "api_response"]
        assert [e[1]["usage"] for e in api_events] == [
            {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
            {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        ]

    def test_agent_loop_config_defaults(self) -> None:
        """
        LLS (agent_loop interface): AgentLoopConfig defaults are
        max_iterations=10, temperature=0.0, timeout=60.0.
        """
        config = AgentLoopConfig(base_url="http://x", api_key="k", model="m")
        assert config.max_iterations == 10
        assert config.temperature == 0.0
        assert config.timeout == 60.0
        assert config.max_tokens is None
        assert config.termination_reminder_generator is None
        assert config.continuation_prompt is None

    # ---------------------------------------------------------------
    # Invariants
    # ---------------------------------------------------------------

    def test_no_state_persists_between_runs(self) -> None:
        """
        LLS invariant: no state persists between calls; each run starts a
        fresh conversation and fresh stubbing state.
        """
        # Each run stops with content, so each injects termination reminders
        # and fails via the iteration limit (default max_iterations=3).
        self.mock_client.chat.completions.create.return_value = make_response(
            content="First answer.", finish_reason="stop"
        )
        first = self.agent.run_agent(
            prompt="Question one",
            tools=[],
            tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
        )

        self.mock_client.chat.completions.create.return_value = make_response(
            content="Second answer.", finish_reason="stop"
        )
        second = self.agent.run_agent(
            prompt="Question two",
            tools=[],
            tool_executor=lambda name, arguments: TerminateAgentWithSuccess(NoChangeResult()) if name == "succeed" else Continue(),
        )

        assert isinstance(first, tuple)
        first_error, first_history = first
        assert isinstance(first_error, str)
        assert isinstance(second, tuple)
        second_error, second_history = second
        assert isinstance(second_error, str)
        assert first_history[0] == {"role": "user", "content": "Question one"}
        assert second_history[0] == {"role": "user", "content": "Question two"}
        # No leftovers from the first run in the second run's history: the
        # second run's user messages are its prompt followed by termination
        # reminders (no trace of the first run).
        second_user_messages = [m for m in second_history if m.get("role") == "user"]
        assert second_user_messages[0] == {"role": "user", "content": "Question two"}
        assert all(m.get("content") != "Question one" for m in second_user_messages)


if __name__ == "__main__":
    unittest.main()
