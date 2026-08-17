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
    FinalAnswer,
    HistoryEntry,
    LogEvent,
    LoggerCallback,
    ToolDefinition,
)
from update_with_ai.lib.agent_loop_impl import AgentLoopImpl
from update_with_ai.lib.tool_provider import (
    Continue,
    TerminateAgentWithFailure,
    TerminateAgentWithSuccess,
    ToolFailure,
    ToolResult,
)


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


class TestAgentLoopImpl(unittest.TestCase):
    """AgentLoopImpl behavior against the agent_loop_impl LLS."""

    def setUp(self) -> None:
        self.openai_patcher = patch("update_with_ai.lib.agent_loop_impl.OpenAI")
        self.mock_openai_class = self.openai_patcher.start()
        self.addCleanup(self.openai_patcher.stop)
        self.mock_client = self.mock_openai_class.return_value
        self.agent = AgentLoopImpl(make_config())

    # ---------------------------------------------------------------
    # Normal outcomes
    # ---------------------------------------------------------------

    def test_final_answer_when_model_stops_with_content(self) -> None:
        """
        LLS: FinalAnswer is returned when the model produces an answer
        (no tool calls).
        """
        self.mock_client.chat.completions.create.return_value = make_response(
            content="The capital of France is Paris.", finish_reason="stop"
        )

        result = self.agent.run_agent(
            prompt="What is the capital of France?",
            tools=[],
            tool_executor=lambda name, arguments: ToolResult(
                content="unused", content_id=None, stub_previous=False
            ),
        )

        assert isinstance(result, FinalAnswer)
        assert result.answer == "The capital of France is Paris."
        assert result.history[0] == {
            "role": "user",
            "content": "What is the capital of France?",
        }
        assert result.history[1]["role"] == "assistant"
        assert result.history[1]["content"] == "The capital of France is Paris."

        kwargs = self.mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "test-model"
        assert kwargs["temperature"] == 0.0
        assert "tools" not in kwargs  # no tools advertised to the model

    def test_tool_result_then_final_answer(self) -> None:
        """
        LLS: tool calls are delegated to tool_executor once per tool call
        with (name, arguments); the ToolResult is appended and the loop
        continues to a FinalAnswer.
        """
        tool_call = make_tool_call("get_weather", "call_123", {"location": "San Francisco"})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=[tool_call], finish_reason="tool_calls"),
            make_response(content="It is sunny in San Francisco.", finish_reason="stop"),
        ]

        calls: List[Tuple[str, Dict[str, Any]]] = []

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            calls.append((name, arguments))
            return ToolResult(
                content='{"weather": "Sunny"}', content_id=None, stub_previous=False
            )

        result = self.agent.run_agent(
            prompt="What's the weather in San Francisco?",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        assert isinstance(result, FinalAnswer)
        assert result.answer == "It is sunny in San Francisco."
        # Once per tool call, with the parsed arguments and the tool name.
        assert calls == [("get_weather", {"location": "San Francisco"})]

        # Tool result immediately follows the tool call in chronological order.
        history = result.history
        tool_messages = [m for m in history if m.get("role") == "tool"]
        assert len(tool_messages) == 1
        assert tool_messages[0]["tool_call_id"] == "call_123"
        assert tool_messages[0]["content"] == '{"weather": "Sunny"}'
        assistant_index = next(
            i for i, m in enumerate(history) if m.get("role") == "assistant"
        )
        assert history.index(tool_messages[0]) > assistant_index
        assert self.mock_client.chat.completions.create.call_count == 2

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
            tool_executor=lambda name, arguments: Continue(),
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
        and unknown finish_reason (plus length/content_filter truncation).
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
                make_response(content="x", finish_reason="length"),
                "Incomplete response: length",
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
                    tool_executor=lambda name, arguments: Continue(),
                )
                assert isinstance(result, tuple)
                error, history = result
                assert isinstance(error, str)
                assert error == expected_error
                assert isinstance(history, list)

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
            return ToolResult(content="42", content_id=None, stub_previous=False)

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
        ]

        def executor(name: str, arguments: Dict[str, Any]) -> ToolFailure[str]:
            return ToolFailure(value="Invalid arguments: location is required")

        result = self.agent.run_agent(
            prompt="What's the weather?",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        assert isinstance(result, FinalAnswer)
        assert result.answer == "Let me retry with valid arguments."
        tool_messages = [m for m in result.history if m.get("role") == "tool"]
        assert len(tool_messages) == 1
        # The failure message becomes the tool result content; no stub by default.
        assert tool_messages[0]["content"] == "Invalid arguments: location is required"
        assert tool_messages[0]["_content_id"] is None
        assert tool_messages[0]["_stub_previous"] is False
        assert self.mock_client.chat.completions.create.call_count == 2

    def test_continue_signal_produces_no_tool_result(self) -> None:
        """
        LLS: a Continue from tool_executor produces no tool result and the
        loop continues.
        """
        tool_call = make_tool_call("get_weather", "call_1", {})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=[tool_call], finish_reason="tool_calls"),
            make_response(content="Done.", finish_reason="stop"),
        ]

        invocations: List[str] = []

        def executor(name: str, arguments: Dict[str, Any]) -> Continue:
            invocations.append(name)
            return Continue()

        result = self.agent.run_agent(
            prompt="Do something",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        assert isinstance(result, FinalAnswer)
        assert result.answer == "Done."
        assert invocations == ["get_weather"]
        assert [m for m in result.history if m.get("role") == "tool"] == []
        assert self.mock_client.chat.completions.create.call_count == 2

    # ---------------------------------------------------------------
    # content_id-based stubbing
    # ---------------------------------------------------------------

    def test_stub_previous_stubs_earlier_results_and_retains_position(self) -> None:
        """
        LLS: with stub_previous=True, all previous non-stubbed results with
        the same content_id are stubbed and the new result is appended;
        stubbed messages retain their position.
        """
        tc1 = make_tool_call("read_file", "call_1", {"path": "/tmp/f.txt"})
        tc2 = make_tool_call("read_file", "call_2", {"path": "/tmp/f.txt"})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=[tc1], finish_reason="tool_calls"),
            make_response(content=None, tool_calls=[tc2], finish_reason="tool_calls"),
            make_response(content="Final.", finish_reason="stop"),
        ]

        counter: Dict[str, int] = {"n": 0}

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            counter["n"] += 1
            return ToolResult(
                content=f"version {counter['n']}", content_id="file_content", stub_previous=True
            )

        result = self.agent.run_agent(
            prompt="Read the file",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        assert isinstance(result, FinalAnswer)
        history = result.history
        tool_messages = [m for m in history if m.get("role") == "tool"]
        assert len(tool_messages) == 2
        # First result stubbed in place, metadata retained.
        assert tool_messages[0]["_stubbed"] is True
        assert tool_messages[0]["_content_id"] == "file_content"
        assert tool_messages[0]["content"] == "Content removed because newer version is available"
        # New result appended with full content, not stubbed.
        assert tool_messages[1]["content"] == "version 2"
        assert tool_messages[1].get("_stubbed") is not True
        # The stubbed message retains its original position (before the second
        # assistant turn); the new result is appended at the end.
        assistant_indices = [i for i, m in enumerate(history) if m.get("role") == "assistant"]
        assert history.index(tool_messages[0]) < assistant_indices[1]
        assert history.index(tool_messages[1]) == len(history) - 2

    def test_content_id_none_appends_unconditionally(self) -> None:
        """
        LLS: with content_id=None the result is appended unconditionally
        (never stubbed), even for repeated tool calls.
        """
        tc1 = make_tool_call("read_file", "call_1", {})
        tc2 = make_tool_call("read_file", "call_2", {})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=[tc1], finish_reason="tool_calls"),
            make_response(content=None, tool_calls=[tc2], finish_reason="tool_calls"),
            make_response(content="Final.", finish_reason="stop"),
        ]

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            return ToolResult(content="raw data", content_id=None, stub_previous=False)

        result = self.agent.run_agent(
            prompt="Read the file twice",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        assert isinstance(result, FinalAnswer)
        tool_messages = [m for m in result.history if m.get("role") == "tool"]
        assert len(tool_messages) == 2
        for msg in tool_messages:
            assert msg["content"] == "raw data"
            assert msg.get("_stubbed") is not True

    def test_stub_previous_false_keeps_previous_results(self) -> None:
        """
        LLS: with stub_previous=False, previous results with the same
        content_id remain unchanged.
        """
        tc1 = make_tool_call("read_file", "call_1", {})
        tc2 = make_tool_call("read_file", "call_2", {})
        self.mock_client.chat.completions.create.side_effect = [
            make_response(content=None, tool_calls=[tc1], finish_reason="tool_calls"),
            make_response(content=None, tool_calls=[tc2], finish_reason="tool_calls"),
            make_response(content="Final.", finish_reason="stop"),
        ]

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            return ToolResult(content="same id data", content_id="cid", stub_previous=False)

        result = self.agent.run_agent(
            prompt="Read the file twice",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        assert isinstance(result, FinalAnswer)
        tool_messages = [m for m in result.history if m.get("role") == "tool"]
        assert len(tool_messages) == 2
        for msg in tool_messages:
            assert msg["content"] == "same id data"
            assert msg.get("_stubbed") is not True

    # ---------------------------------------------------------------
    # Termination reminder
    # ---------------------------------------------------------------

    def test_reminder_injected_at_most_once_and_loop_continues(self) -> None:
        """
        LLS: at most one reminder is injected per run on the stop path; the
        reminder is appended as a message (message_added), the reminder
        event is emitted, and the loop continues.
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
        ]

        result = agent.run_agent(
            prompt="Do something",
            tools=[],
            tool_executor=lambda name, arguments: Continue(),
            logger=logger,
        )

        assert isinstance(result, FinalAnswer)
        assert result.answer == "OK, I will use the tool."
        assert self.mock_client.chat.completions.create.call_count == 2

        # Exactly one reminder message in the history.
        reminder_messages = [
            m
            for m in result.history
            if m.get("role") == "user" and m.get("content") == "You must use a tool to finish."
        ]
        assert len(reminder_messages) == 1

        # Exactly one reminder_injected event.
        reminder_events = [e for e in events if e[0] == "reminder_injected"]
        assert len(reminder_events) == 1
        assert reminder_events[0][1]["message"] == "You must use a tool to finish."

        # The appended reminder was reported via message_added, before the
        # reminder_injected event (logger invoked after each history update).
        reminder_added = [
            e
            for e in events
            if e[0] == "message_added"
            and e[1]["message"].get("content") == "You must use a tool to finish."
        ]
        assert len(reminder_added) == 1
        assert events.index(reminder_added[0]) < events.index(reminder_events[0])

        # The reminder is included in the follow-up API call.
        second_messages = self.mock_client.chat.completions.create.call_args_list[1].kwargs[
            "messages"
        ]
        assert any(
            m.get("role") == "user" and m.get("content") == "You must use a tool to finish."
            for m in second_messages
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
            make_response(content="Done.", finish_reason="stop"),
        ]

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            return ToolResult(content="file data", content_id="cid", stub_previous=True)

        result = self.agent.run_agent(
            prompt="Read the file",
            tools=make_tool_definitions(),
            tool_executor=executor,
        )

        assert isinstance(result, FinalAnswer)

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

    def test_logger_invoked_after_each_history_update(self) -> None:
        """
        LLS: the logger is invoked after each history update, in
        chronological order, with the documented events.
        """
        events: List[LogEvent] = []

        def logger(event: LogEvent, data: Dict[str, Any]) -> None:
            events.append(event)

        self.mock_client.chat.completions.create.return_value = make_response(
            content="Hello back.", finish_reason="stop"
        )

        result = self.agent.run_agent(
            prompt="Hi",
            tools=[],
            tool_executor=lambda name, arguments: Continue(),
            logger=logger,
        )

        assert isinstance(result, FinalAnswer)
        # message_added for the user prompt and the assistant reply, each
        # fired after the corresponding history append, in order.
        assert events == ["message_added", "api_response", "message_added", "final_answer"]

    def test_logger_exceptions_ignored(self) -> None:
        """
        LLS: logger callback exceptions are caught and ignored; the run
        still completes.
        """
        def logger(event: LogEvent, data: Dict[str, Any]) -> None:
            raise RuntimeError("logger exploded")

        self.mock_client.chat.completions.create.return_value = make_response(
            content="Still works.", finish_reason="stop"
        )

        result = self.agent.run_agent(
            prompt="Hi",
            tools=[],
            tool_executor=lambda name, arguments: Continue(),
            logger=logger,
        )

        assert isinstance(result, FinalAnswer)
        assert result.answer == "Still works."

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
        ]

        events: List[Tuple[str, Dict[str, Any]]] = []

        def logger(event: LogEvent, data: Dict[str, Any]) -> None:
            events.append((event, data))

        def executor(name: str, arguments: Dict[str, Any]) -> ToolResult:
            return ToolResult(content="x", content_id=None, stub_previous=False)

        result = self.agent.run_agent(
            prompt="Weather?",
            tools=make_tool_definitions(),
            tool_executor=executor,
            logger=logger,
        )

        assert isinstance(result, FinalAnswer)
        final_events = [e for e in events if e[0] == "final_answer"]
        assert len(final_events) == 1
        assert final_events[0][1]["cumulative_usage"] == {
            "prompt_tokens": 15,
            "completion_tokens": 27,
            "total_tokens": 42,
            "request_count": 2,
        }
        api_events = [e for e in events if e[0] == "api_response"]
        assert [e[1]["usage"] for e in api_events] == [
            {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
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

    # ---------------------------------------------------------------
    # Invariants
    # ---------------------------------------------------------------

    def test_no_state_persists_between_runs(self) -> None:
        """
        LLS invariant: no state persists between calls; each run starts a
        fresh conversation.
        """
        self.mock_client.chat.completions.create.return_value = make_response(
            content="First answer.", finish_reason="stop"
        )
        first = self.agent.run_agent(
            prompt="Question one",
            tools=[],
            tool_executor=lambda name, arguments: Continue(),
        )

        self.mock_client.chat.completions.create.return_value = make_response(
            content="Second answer.", finish_reason="stop"
        )
        second = self.agent.run_agent(
            prompt="Question two",
            tools=[],
            tool_executor=lambda name, arguments: Continue(),
        )

        assert isinstance(first, FinalAnswer)
        assert isinstance(second, FinalAnswer)
        assert first.history[0] == {"role": "user", "content": "Question one"}
        assert second.history[0] == {"role": "user", "content": "Question two"}
        # No leftovers from the first run in the second run's history.
        assert [m for m in second.history if m.get("role") == "user"] == [
            {"role": "user", "content": "Question two"}
        ]


if __name__ == "__main__":
    unittest.main()
