"""Tests for agent_runner_impl derived from LLS."""

import unittest
from typing import Sequence, Optional, Union, List
from lib.tool_provider import (
    Tool,
    ToolProvider,
    ToolMetadata,
    ToolResult,
    ToolFailure,
    TerminationOutcome,
    ToolOutcome,
    ToolArguments,
)
from lib.conversation_history import (
    ConversationHistory,
    HistoryMessage,
    ModelRequest,
)
from lib.loop_guard import (
    LoopGuard,
    LoopReminder,
    LoopFailure,
)
from lib.runner_logger import RunnerLogger, LogEvent
from lib.openai_ext import (
    OpenAiExt,
    CompletionRequest,
    CompletionResponse,
)
from lib.agent_runner import AgentOutcome
from lib.agent_runner_impl import AgentRunnerImpl


class MockOpenAiExt(OpenAiExt):
    def __init__(self, scripted_responses: Optional[List[CompletionResponse]] = None) -> None:
        self.scripted_responses = list(scripted_responses) if scripted_responses else []
        self.requests: List[CompletionRequest] = []

    def create_chat_completion(self, request: CompletionRequest) -> CompletionResponse:
        self.requests.append(request)
        if self.scripted_responses:
            return self.scripted_responses.pop(0)
        # Default response: direct terminal completion
        return CompletionResponse(
            message=HistoryMessage(role="assistant", content="Completed"),
            prompt_tokens=10,
            completion_tokens=5,
        )


class RecordingTool(Tool):
    def __init__(self, name: str, outcome: ToolOutcome) -> None:
        self._name = name
        self._outcome = outcome
        self.invocations: List[ToolArguments] = []

    def get_metadata(self) -> ToolMetadata:
        return ToolMetadata(name=self._name, purpose="Test tool", parameters_schema={})

    def execute(self, arguments: ToolArguments) -> ToolOutcome:
        self.invocations.append(dict(arguments))
        return self._outcome


class MockToolProvider(ToolProvider):
    def __init__(self, tools: Sequence[Tool]) -> None:
        self._tools = list(tools)

    def get_tools(self) -> Sequence[Tool]:
        return self._tools


class TrackingHistory(ConversationHistory):
    def __init__(self) -> None:
        self.messages: List[HistoryMessage] = []
        self.get_request_calls = 0

    def initialize(self, initial_messages: Sequence[HistoryMessage]) -> None:
        self.messages = list(initial_messages)

    def append(self, item: Union[HistoryMessage, ToolResult]) -> None:
        if isinstance(item, ToolResult):
            self.messages.append(HistoryMessage(role="tool", content=item.content))
        else:
            self.messages.append(item)

    def get_model_request(self) -> ModelRequest:
        self.get_request_calls += 1
        return ModelRequest(messages=list(self.messages))

    def get_messages(self) -> Sequence[HistoryMessage]:
        return list(self.messages)


class MockLoopGuard(LoopGuard):
    def __init__(self, trigger_call_index: int = -1, is_fatal: bool = False) -> None:
        self.trigger_call_index = trigger_call_index
        self.is_fatal = is_fatal
        self.call_count = 0

    def record_tool_call(self, tool_name: str, arguments: ToolArguments) -> Optional[Union[LoopReminder, LoopFailure]]:
        self.call_count += 1
        if self.call_count == self.trigger_call_index:
            if self.is_fatal:
                return LoopFailure(feedback="Fatal loop detected")
            return LoopReminder(content="Loop warning reminder")
        return None

    def record_file_edit(self, file_path: str, line_range: tuple[int, int]) -> Optional[Union[LoopReminder, LoopFailure]]:
        return None

    def reset_progress(self) -> None:
        self.call_count = 0


class MockLogger(RunnerLogger):
    def __init__(self) -> None:
        self.events: List[LogEvent] = []

    def log(self, event: LogEvent) -> None:
        self.events.append(event)


class AgentRunnerImplTest(unittest.TestCase):
    def test_agent_outcome_dataclass(self) -> None:
        """Tests Data Types: AgentOutcome dataclass instantiation."""
        term = TerminationOutcome(content="Completed successfully", is_terminal=True)
        msgs = [HistoryMessage(role="user", content="hello")]
        outcome = AgentOutcome(termination=term, history=msgs)
        self.assertEqual(outcome.termination, term)
        self.assertEqual(outcome.history, msgs)

    def test_multi_turn_tool_execution_flow(self) -> None:
        """Tests CUJ for multi-turn model-tool interaction loop.

        Checks postconditions: model request formatted, tool executed, results appended to history,
        and final termination outcome returned in AgentOutcome.
        """
        adv_tool = RecordingTool("advance", TerminationOutcome(content="Passed verification", is_terminal=True))
        provider = MockToolProvider([adv_tool])
        history = TrackingHistory()
        history.initialize([HistoryMessage(role="user", content="Execute task")])

        # Script response calling advance tool
        scripted = [
            CompletionResponse(
                message=HistoryMessage(
                    role="assistant",
                    content=None,
                    metadata={"tool_calls": [{"function": {"name": "advance", "arguments": "{}"}}]},
                ),
                prompt_tokens=10,
                completion_tokens=5,
            )
        ]
        openai_mock = MockOpenAiExt(scripted_responses=scripted)
        runner = AgentRunnerImpl(openai_ext=openai_mock, model="gpt-4")
        outcome = runner.run(tool_provider=provider, history=history, iteration_limit=10)

        # Must format CompletionRequest to openai_ext
        self.assertEqual(len(openai_mock.requests), 1)
        # Must execute the tool
        self.assertEqual(len(adv_tool.invocations), 1)
        # Outcome must carry termination and complete history
        self.assertIsInstance(outcome, AgentOutcome)
        self.assertTrue(outcome.termination.is_terminal)

    def test_iteration_limit_exhaustion_boundary(self) -> None:
        """Tests all sides of iteration limit boundary:
        1. Within iteration limit -> succeeds with terminal outcome.
        2. Exceeding iteration limit -> concludes with failure AgentOutcome.
        """
        # Side 1: terminates within limit
        quick_tool = RecordingTool("advance", TerminationOutcome(content="Done", is_terminal=True))
        hist1 = TrackingHistory()
        hist1.initialize([HistoryMessage(role="user", content="Quick")])
        openai_mock1 = MockOpenAiExt([
            CompletionResponse(
                message=HistoryMessage(
                    role="assistant",
                    content=None,
                    metadata={"tool_calls": [{"function": {"name": "advance", "arguments": "{}"}}]},
                ),
                prompt_tokens=5,
                completion_tokens=5,
            )
        ])
        runner1 = AgentRunnerImpl(openai_ext=openai_mock1, model="gpt-4")
        outcome_quick = runner1.run(tool_provider=MockToolProvider([quick_tool]), history=hist1, iteration_limit=5)
        self.assertTrue(outcome_quick.termination.is_terminal)
        self.assertEqual(outcome_quick.termination.content, "Done")

        # Side 2: non-terminating tool exceeds limit
        looping_tool = RecordingTool("search", ToolResult(content="Found results"))
        hist2 = TrackingHistory()
        hist2.initialize([HistoryMessage(role="user", content="Search")])
        scripted_loop = [
            CompletionResponse(
                message=HistoryMessage(
                    role="assistant",
                    content=None,
                    metadata={"tool_calls": [{"function": {"name": "search", "arguments": "{}"}}]},
                ),
                prompt_tokens=5,
                completion_tokens=5,
            )
            for _ in range(5)
        ]
        openai_mock2 = MockOpenAiExt(scripted_loop)
        runner2 = AgentRunnerImpl(openai_ext=openai_mock2, model="gpt-4")
        outcome_exhausted = runner2.run(tool_provider=MockToolProvider([looping_tool]), history=hist2, iteration_limit=3)
        self.assertIsInstance(outcome_exhausted, AgentOutcome)
        self.assertTrue(outcome_exhausted.termination.is_terminal)
        self.assertIn("limit", outcome_exhausted.termination.content.lower())

    def test_loop_guard_trigger_and_fatal_termination(self) -> None:
        """Tests CUJ for injecting LoopReminder on repetition and terminating on LoopFailure."""
        retrying_tool = RecordingTool("read", ToolResult(content="content"))
        hist = TrackingHistory()
        hist.initialize([HistoryMessage(role="user", content="Read")])
        guard = MockLoopGuard(trigger_call_index=2, is_fatal=True)

        scripted_loop = [
            CompletionResponse(
                message=HistoryMessage(
                    role="assistant",
                    content=None,
                    metadata={"tool_calls": [{"function": {"name": "read", "arguments": "{}"}}]},
                ),
                prompt_tokens=5,
                completion_tokens=5,
            )
            for _ in range(3)
        ]
        openai_mock = MockOpenAiExt(scripted_loop)
        runner = AgentRunnerImpl(openai_ext=openai_mock, model="gpt-4")
        outcome = runner.run(tool_provider=MockToolProvider([retrying_tool]), history=hist, loop_guard=guard, iteration_limit=10)
        self.assertIsInstance(outcome, AgentOutcome)
        self.assertTrue(outcome.termination.is_terminal)
        self.assertIn("loop", outcome.termination.content.lower())

    def test_run_with_direct_assistant_response_terminates_successfully(self) -> None:
        """Tests that when model returns direct message with no tool calls, run concludes with assistant content."""
        hist = TrackingHistory()
        hist.initialize([HistoryMessage(role="user", content="Simple question")])
        openai_mock = MockOpenAiExt([
            CompletionResponse(
                message=HistoryMessage(role="assistant", content="The answer is 42"),
                prompt_tokens=5,
                completion_tokens=5,
            )
        ])
        runner = AgentRunnerImpl(openai_ext=openai_mock, model="gpt-4")
        outcome = runner.run(tool_provider=MockToolProvider([]), history=hist)
        self.assertTrue(outcome.termination.is_terminal)
        self.assertEqual(outcome.termination.content, "The answer is 42")

    def test_tool_failure_appends_feedback_to_history(self) -> None:
        """Tests that ToolFailure outcomes append error feedback to history before retrying or terminating."""
        fail_tool = RecordingTool("failing_tool", ToolFailure(feedback="Missing required file"))
        hist = TrackingHistory()
        hist.initialize([HistoryMessage(role="user", content="Run failing tool")])

        scripted = [
            CompletionResponse(
                message=HistoryMessage(
                    role="assistant",
                    content=None,
                    metadata={"tool_calls": [{"function": {"name": "failing_tool", "arguments": "{}"}}]},
                ),
                prompt_tokens=5,
                completion_tokens=5,
            ),
            CompletionResponse(
                message=HistoryMessage(role="assistant", content="Acknowledged failure"),
                prompt_tokens=5,
                completion_tokens=5,
            ),
        ]
        openai_mock = MockOpenAiExt(scripted)
        runner = AgentRunnerImpl(openai_ext=openai_mock, model="gpt-4")
        outcome = runner.run(tool_provider=MockToolProvider([fail_tool]), history=hist, iteration_limit=2)
        # Verify feedback was recorded into history
        history_contents = [m.content for m in hist.get_messages()]
        self.assertTrue(any("Missing required file" in str(c) for c in history_contents))

    def test_tool_call_id_correlation_in_history(self) -> None:
        """Tests that tool results appended to history preserve tool_call_id from originating assistant tool call."""
        read_tool = RecordingTool("read_file", ToolResult(content="file contents"))
        hist = TrackingHistory()
        hist.initialize([HistoryMessage(role="user", content="Read a file")])
        scripted = [
            CompletionResponse(
                message=HistoryMessage(
                    role="assistant",
                    content=None,
                    metadata={"tool_calls": [{"id": "call_999", "function": {"name": "read_file", "arguments": "{}"}}]},
                ),
                prompt_tokens=5,
                completion_tokens=5,
            ),
            CompletionResponse(
                message=HistoryMessage(role="assistant", content="Done reading"),
                prompt_tokens=5,
                completion_tokens=5,
            ),
        ]
        openai_mock = MockOpenAiExt(scripted)
        runner = AgentRunnerImpl(openai_ext=openai_mock, model="gpt-4")
        _ = runner.run(tool_provider=MockToolProvider([read_tool]), history=hist, iteration_limit=2)
        tool_messages = [m for m in hist.get_messages() if m.role == "tool"]
        self.assertEqual(len(tool_messages), 1)
        self.assertIsNotNone(tool_messages[0].metadata)
        self.assertEqual(tool_messages[0].metadata.get("tool_call_id"), "call_999")

    def test_runner_logger_event_emission(self) -> None:
        """Tests that runner emits execution progress events to RunnerLogger."""
        hist = TrackingHistory()
        hist.initialize([HistoryMessage(role="user", content="Log test")])
        openai_mock = MockOpenAiExt([
            CompletionResponse(
                message=HistoryMessage(role="assistant", content="Complete"),
                prompt_tokens=5,
                completion_tokens=5,
            )
        ])
        logger = MockLogger()
        runner = AgentRunnerImpl(openai_ext=openai_mock, model="gpt-4")
        _ = runner.run(tool_provider=MockToolProvider([]), history=hist, logger=logger)
        self.assertTrue(len(logger.events) > 0)


if __name__ == "__main__":
    unittest.main()
