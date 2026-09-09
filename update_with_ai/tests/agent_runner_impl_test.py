"""Unit tests for agent_runner_impl aligned with grounding specifications."""

import json
import unittest
from typing import List, Set
from unittest.mock import MagicMock, patch

from lib.agent_conversation_history import ConversationHistory, Message, ModelRequest
from lib.agent_loop_guard import LoopGuard
from lib.agent_runner import AgentOutcome, AgentRunner
from lib.agent_runner_impl import AgentRunner as AgentRunnerImpl, OpenAIError, __initialize__
from lib.lifecycle import LifecycleRegistry, enter_phase
from lib.model_config import ModelConfig
from lib.runner_logger import LogEvent, RunnerLogger
from lib.tool_provider import (
    ActualParameterBindings,
    Parameter,
    Response,
    Tool,
    ToolManager,
    WireParameterBindings,
)


class MockModelConfig:
    tier = "system"
    model_name = "test-model"
    base_url = "https://api.test.com"
    api_key = "test-key"
    timeout = 30
    conversation_limit = 5
    is_step_mode = False
    is_startup_reads = False


class MockLogger:
    tier = "system"

    def __init__(self) -> None:
        self.events: List[LogEvent] = []

    def consume(self, event: LogEvent) -> None:
        self.events.append(event)


class MockHistory:
    tier = "agent_session"

    def __init__(self) -> None:
        self._messages: List[Message] = []
        self.tool_responses: List[tuple[Response, str, str]] = []

    @property
    def messages(self) -> List[Message]:
        return list(self._messages)

    def append_message(self, message: Message) -> None:
        self._messages.append(message)

    def append_tool_response(self, response: Response, tool_name: str, tool_call_id: str) -> None:
        self.tool_responses.append((response, tool_name, tool_call_id))
        self._messages.append(
            Message(
                role="tool",
                content=response.content,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
            )
        )

    def get_model_request(self) -> ModelRequest:
        return ModelRequest(messages=list(self._messages))


class MockLoopGuard:
    tier = "agent_session"

    def record_tool_execution(
        self, tool_name: str, bindings: ActualParameterBindings
    ) -> None:
        return None

    def record_progress(self) -> None:
        pass


class MockToolManager:
    tier = "agent_session"

    def __init__(self) -> None:
        self._tools: Set[Tool] = set()
        self.executions: List[tuple[str, WireParameterBindings]] = []
        self.responses: dict[str, Response] = {}

    @property
    def installed_tools(self) -> Set[Tool]:
        return self._tools

    def install_tool(self, tool: Tool) -> None:
        self._tools.add(tool)

    def execute_tool(self, name: str, wire_parameter_bindings: WireParameterBindings) -> Response:
        self.executions.append((name, wire_parameter_bindings))
        return self.responses.get(
            name, Response(is_failed=False, is_terminated=False, content="executed")
        )


class DummyFunction:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class DummyToolCall:
    def __init__(self, id: str, name: str, arguments: str) -> None:
        self.id = id
        self.function = DummyFunction(name, arguments)


class DummyMessage:
    def __init__(self, content: str | None, tool_calls: List[DummyToolCall] | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls or []


class DummyChoice:
    def __init__(self, message: DummyMessage, finish_reason: str = "stop") -> None:
        self.message = message
        self.finish_reason = finish_reason


class DummyCompletion:
    def __init__(self, choices: List[DummyChoice]) -> None:
        self.choices = choices


class AgentRunnerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.model_cfg = MockModelConfig()
        self.logger = MockLogger()
        self.history = MockHistory()
        self.loop_guard = MockLoopGuard()
        self.tool_mgr = MockToolManager()

        self.registry.register_instance(self.model_cfg, keys=[ModelConfig], tier="system")
        self.registry.register_instance(self.logger, keys=[RunnerLogger], tier="system")
        self.registry.register_instance(
            self.history, keys=[ConversationHistory], tier="agent_session"
        )
        self.registry.register_instance(self.loop_guard, keys=[LoopGuard], tier="agent_session")
        self.registry.register_instance(self.tool_mgr, keys=[ToolManager], tier="agent_session")

    def test_agent_outcome_dataclass(self) -> None:
        """CUJ: Instantiating AgentOutcome dataclass."""
        resp = Response(is_failed=False, is_terminated=True, content="Success")
        outcome = AgentOutcome(is_success=True, response=resp, conversation_history=self.history)
        self.assertTrue(outcome.is_success)
        self.assertEqual(outcome.response, resp)
        self.assertEqual(outcome.conversation_history, self.history)

    @patch("lib.agent_runner_impl.OpenAI")
    def test_direct_assistant_response(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Concluding successfully when model returns response without tool calls."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        completion = DummyCompletion([DummyChoice(DummyMessage("The task is complete"))])
        mock_client.chat.completions.create.return_value = completion

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            # Requirement: [AgentRunner] The agent runner drives turns by sending model requests to a language model and executing requested tools.
            # Requirement: The agent runner transmits completion requests using model name, base url, api key, and timeout from model config with openai_ext.
            self.assertTrue(outcome.is_success)
            self.assertFalse(outcome.response.is_failed)
            self.assertEqual(len(self.history.messages), 1)
            self.assertEqual(self.history.messages[0].role, "assistant")
            self.assertEqual(self.history.messages[0].content, "The task is complete")
            # Requirement: The agent runner logs log events for requests, completions, and tool results to the runner logger.
            # Requirement: [AgentRunner] The agent runner records log events for model requests, responses, and tool executions to the runner logger.
            self.assertTrue(any(e.event_name == "model_completion" for e in self.logger.events))

    @patch("lib.agent_runner_impl.OpenAI")
    def test_tool_call_and_termination(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Dispatching tool calls to tool manager and concluding on terminal response."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        tc = DummyToolCall(id="call_1", name="finish_task", arguments=json.dumps({"summary": "all done"}))
        completion = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        mock_client.chat.completions.create.return_value = completion

        term_resp = Response(is_failed=False, is_terminated=True, content="Task completed successfully")
        self.tool_mgr.responses["finish_task"] = term_resp

        class DummyTool(Tool):
            name = "finish_task"
            description = "Finishes task"
            parameters = {
                Parameter(
                    name="summary",
                    description="Summary",
                    parameter_converter=None,  # type: ignore
                    is_required=True,
                )
            }
        self.tool_mgr.install_tool(DummyTool())

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            # Requirement: When tool execution produces a terminating response, the agent runner concludes the run and returns an agent outcome.
            # Requirement: [AgentRunner] When tool execution produces a termination outcome, the agent runner concludes and returns an agent outcome.
            self.assertTrue(outcome.is_success)
            self.assertTrue(outcome.response.is_terminated)
            self.assertEqual(outcome.response.content, "Task completed successfully")
            self.assertEqual(len(self.tool_mgr.executions), 1)
            self.assertEqual(self.tool_mgr.executions[0][0], "finish_task")
            # Requirement: [AgentRunner] The agent runner appends model responses and correlates tool responses with tool call identifiers in conversation history.
            self.assertEqual(len(self.history.tool_responses), 1)
            self.assertEqual(self.history.tool_responses[0][1], "finish_task")

    @patch("lib.agent_runner_impl.OpenAI")
    def test_non_terminating_tool_failure_continues_run(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Non-terminating tool failure appends feedback and run continues."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        tc = DummyToolCall(id="call_fail", name="edit_file", arguments=json.dumps({"path": "foo.py"}))
        comp1 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        comp2 = DummyCompletion([DummyChoice(DummyMessage("Recovered from tool error"))])
        mock_client.chat.completions.create.side_effect = [comp1, comp2]

        self.tool_mgr.responses["edit_file"] = Response(is_failed=True, is_terminated=False, content="Error: file not found")

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            # Requirement: When tool execution produces a non-terminating failure response, the failure feedback is appended to the conversation history and the run continues.
            self.assertTrue(outcome.is_success)
            self.assertEqual(len(self.history.tool_responses), 1)
            self.assertTrue(self.history.tool_responses[0][0].is_failed)
            self.assertEqual(self.history.tool_responses[0][0].content, "Error: file not found")
            self.assertEqual(self.history.messages[-1].content, "Recovered from tool error")

    @patch("lib.agent_runner_impl.OpenAI")
    def test_truncation_continuation(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Resuming generation with continuation turn when length-truncated."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        comp_truncated = DummyCompletion([DummyChoice(DummyMessage("Part 1"), finish_reason="length")])
        comp_final = DummyCompletion([DummyChoice(DummyMessage("Part 2"), finish_reason="stop")])
        mock_client.chat.completions.create.side_effect = [comp_truncated, comp_final]

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            # Requirement: When a model response is truncated at the generation limit, the agent runner resumes generation with a continuation turn.
            self.assertTrue(outcome.is_success)
            # Expect: assistant Part 1 -> user continuation prompt -> assistant Part 2
            self.assertEqual(len(self.history.messages), 3)
            self.assertEqual(self.history.messages[0].role, "assistant")
            self.assertEqual(self.history.messages[1].role, "user")
            self.assertIn("truncated due to length", self.history.messages[1].content)
            self.assertEqual(self.history.messages[2].role, "assistant")

    @patch("lib.agent_runner_impl.OpenAI")
    def test_model_error_handling(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Handling OpenAIError by logging and returning a failed outcome."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = OpenAIError("API Rate Limited")

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            # Requirement: The agent runner logs log events for requests, completions, and tool results to the runner logger.
            self.assertFalse(outcome.is_success)
            self.assertTrue(outcome.response.is_failed)
            self.assertTrue(outcome.response.is_terminated)
            self.assertTrue(any(e.event_name == "model_error" for e in self.logger.events))


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - [AgentRunner] The agent runner evaluates tool executions with the loop guard, injecting reminders or terminating on failure.
# - When turns reach the conversation limit from model config, the agent runner concludes with a failure outcome.
