"""Unit tests for agent_runner_impl aligned with grounding specifications."""

import json
import unittest
from typing import Any, List, Optional, Set
from unittest.mock import MagicMock, patch

from lib.agent_conversation_history import ConversationHistory, Message, ModelRequest
from lib.agent_loop_guard import LoopFailure, LoopGuard, LoopReminder
from lib.agent_runner import AgentOutcome, AgentRunner
from lib.agent_runner_impl import AgentRunner as AgentRunnerImpl, OpenAIError, __initialize__
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from lib.model_config import ModelConfig
from lib.runner_logger import LogEvent, RunnerLogger
from lib.tool_provider import (
    ActualParameterBindings,
    FollowUpToolCall,
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
    temperature = 0.2
    max_tokens: Optional[int] = None
    is_step_mode = False
    is_startup_reads = False
    inject_followups = False


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

    def append_tool_response(
        self,
        response: Response,
        tool_name: str,
        tool_call_id: str,
        wire_parameter_bindings: Optional[WireParameterBindings] = None,
    ) -> None:
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

    def __init__(self) -> None:
        self.recorded_executions: List[tuple[str, ActualParameterBindings]] = []
        self.progress_count: int = 0
        self.return_value: Any = None
        self.return_values: List[Any] = []

    def record_tool_execution(
        self, tool_name: str, bindings: ActualParameterBindings
    ) -> Any:
        self.recorded_executions.append((tool_name, bindings))
        if self.return_values:
            return self.return_values.pop(0)
        return self.return_value

    def record_progress(self) -> None:
        self.progress_count += 1


class MockToolManager:
    tier = "agent_session"

    def __init__(self) -> None:
        self._tools: Set[Tool] = set()
        self.executions: List[tuple[str, WireParameterBindings]] = []
        self.responses: dict[str, Response] = {}
        self.handlers: dict[str, Any] = {}

    @property
    def installed_tools(self) -> Set[Tool]:
        return self._tools

    def install_tool(self, tool: Tool) -> None:
        self._tools.add(tool)

    def execute_tool(self, name: str, wire_parameter_bindings: WireParameterBindings) -> Response:
        self.executions.append((name, wire_parameter_bindings))
        if name in self.handlers:
            return self.handlers[name](wire_parameter_bindings)
        return self.responses.get(
            name, Response(is_failed=False, is_terminated=False, content="executed")
        )


class MockConverter:
    @property
    def actual_type(self) -> type:
        return str

    @property
    def wire_type(self) -> Any:
        return None

    def convert(self, wire_value: Any) -> Any:
        return wire_value


class DummyTool:
    def __init__(self, name: str, parameters: Set[Parameter]) -> None:
        self._name = name
        self._parameters = parameters

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Tool {self._name}"

    @property
    def parameters(self) -> Set[Parameter]:
        return self._parameters

    def execute_tool(self, actual_parameter_bindings: ActualParameterBindings) -> Response:
        return Response(is_failed=False, is_terminated=False, content="ok")


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
    def test_response_without_tool_calls_prompts_reminder_and_continues(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Injecting tool reminder and continuing when model returns no tool calls."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # Turn 1: Model returns text without tool calls
        comp1 = DummyCompletion([DummyChoice(DummyMessage("I will inspect the files."))])
        # Turn 2: Model invokes terminating tool call
        tc = DummyToolCall(id="call_finish", name="finish_task", arguments=json.dumps({"summary": "done"}))
        comp2 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        mock_client.chat.completions.create.side_effect = [comp1, comp2]

        term_resp = Response(is_failed=False, is_terminated=True, content="Done")
        self.tool_mgr.responses["finish_task"] = term_resp

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            # Requirement: When a model response produces no tool executions, the agent runner appends a prompt to the conversation history reminding that progress and conclusion require invoking tools, and continues the turn loop.
            # Requirement: [AgentRunner] When a model response contains no tool executions, the agent runner injects a tool reminder into the conversation history and continues the turn loop.
            # Requirement: When tool execution produces a terminating response, the agent runner concludes the run and returns an agent outcome, or halts with an unexpected failure if the response indicates terminating failure.
            self.assertTrue(outcome.is_success)
            self.assertEqual(len(self.history.messages), 4)
            self.assertEqual(self.history.messages[0].role, "assistant")
            self.assertEqual(self.history.messages[0].content, "I will inspect the files.")
            self.assertEqual(self.history.messages[1].role, "user")
            self.assertIn("No tools were executed", self.history.messages[1].content)
            self.assertEqual(self.history.messages[2].role, "assistant")
            # Requirement: The agent runner logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, prefix reuse measurements comparing current wire payloads against previous request payloads with divergence diagnostics, tool names and arguments or text previews, and execution outcomes, including corrective reminders in tool result transcripts when present.
            # Requirement: [AgentRunner] The agent runner records log events for model requests, responses, and tool executions to the runner logger, providing summaries with turn progress, tool calls with arguments or text snippets, and execution outcomes.
            comp_events = [e for e in self.logger.events if e.event_name == "model_completion"]
            self.assertTrue(len(comp_events) >= 2)
            self.assertIn("[Turn 1] Assistant (text):", comp_events[0].summary)
            self.assertIn("[Turn 2] Assistant: finish_task", comp_events[1].summary)

            tool_events = [e for e in self.logger.events if e.event_name == "tool_execution"]
            self.assertTrue(len(tool_events) >= 1)
            self.assertIn("[Turn 2] Tool finish_task: COMPLETED -> Done", tool_events[0].summary)

    @patch("lib.agent_runner_impl.OpenAI")
    def test_conversation_limit_exceeded_fails(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Concluding with failure when turns reach the conversation limit."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        comp = DummyCompletion([DummyChoice(DummyMessage("Still thinking..."))])
        mock_client.chat.completions.create.return_value = comp

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)

            # Requirement: When turns reach the conversation limit from model config, the agent runner halts with an unexpected failure.
            # Requirement: [AgentRunner] When the conversation limit from model config is exceeded, the agent runner halts with an unexpected failure.
            with self.assertRaises(RuntimeError) as ctx:
                runner.run()
            self.assertIn("Conversation limit reached", str(ctx.exception))
            self.assertEqual(mock_client.chat.completions.create.call_count, 5)

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
            @property
            def name(self) -> str:
                return "finish_task"

            @property
            def description(self) -> str:
                return "Finishes task"

            @property
            def parameters(self) -> Set[Parameter]:
                return {
                    Parameter(
                        name="summary",
                        description="Summary",
                        parameter_converter=None,  # type: ignore
                        is_required=True,
                    )
                }

            def execute_tool(self, actual_parameter_bindings: ActualParameterBindings) -> Response:
                return term_resp

        self.tool_mgr.install_tool(DummyTool())

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            # Requirement: [AgentRunner] The agent runner drives turns by sending model requests to a language model and executing requested tools.
            # Requirement: When tool execution produces a terminating response, the agent runner concludes the run and returns an agent outcome, or halts with an unexpected failure if the response indicates terminating failure.
            # Requirement: [AgentRunner] When tool execution produces a termination outcome, the agent runner concludes and returns an agent outcome, or halts with an unexpected failure if the termination indicates a failing outcome.
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

        tc1 = DummyToolCall(id="call_fail", name="edit_file", arguments=json.dumps({"path": "foo.py"}))
        comp1 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc1]))])
        tc2 = DummyToolCall(id="call_finish", name="finish_task", arguments=json.dumps({"summary": "recovered"}))
        comp2 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc2]))])
        mock_client.chat.completions.create.side_effect = [comp1, comp2]

        self.tool_mgr.responses["edit_file"] = Response(is_failed=True, is_terminated=False, content="Error: file not found")
        self.tool_mgr.responses["finish_task"] = Response(is_failed=False, is_terminated=True, content="Recovered")

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            # Requirement: When driving a turn, the agent runner transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from model config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter name, and correlates tool results with model invocations according to OpenAI tool calling conventions.
            self.assertEqual(mock_client.chat.completions.create.call_count, 2)
            turn2_messages = mock_client.chat.completions.create.call_args_list[1].kwargs["messages"]
            asst_tc_msg = next(m for m in turn2_messages if m["role"] == "assistant" and "tool_calls" in m)
            self.assertEqual(asst_tc_msg["tool_calls"][0]["id"], "call_fail")
            self.assertEqual(asst_tc_msg["tool_calls"][0]["function"]["name"], "edit_file")
            tool_res_msg = next(m for m in turn2_messages if m["role"] == "tool")
            self.assertEqual(tool_res_msg["tool_call_id"], "call_fail")

            # Requirement: When tool execution produces a non-terminating failure response, the failure feedback is appended to the conversation history and the run continues.
            # Requirement: When tool execution produces a terminating response, the agent runner concludes the run and returns an agent outcome, or halts with an unexpected failure if the response indicates terminating failure.
            self.assertTrue(outcome.is_success)
            self.assertEqual(len(self.history.tool_responses), 2)
            self.assertTrue(self.history.tool_responses[0][0].is_failed)
            self.assertEqual(self.history.tool_responses[0][0].content, "Error: file not found")
            self.assertFalse(self.history.tool_responses[1][0].is_failed)
            self.assertEqual(self.history.tool_responses[1][0].content, "Recovered")

    @patch("lib.agent_runner_impl.OpenAI")
    def test_continuation_turn_on_truncated_response(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Model response truncated due to finish_reason='length' triggers continuation turn."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # Turn 1: Truncated response (no tool calls, finish_reason="length")
        comp1 = DummyCompletion([DummyChoice(
            DummyMessage("Part 1: The analysis begins..."),
            finish_reason="length",
        )])
        # Turn 2: Completes and calls tool
        tc = DummyToolCall(id="call_finish", name="finish_task", arguments="{}")
        comp2 = DummyCompletion([DummyChoice(
            DummyMessage("Part 2: concluding.", tool_calls=[tc]),
            finish_reason="stop",
        )])
        mock_client.chat.completions.create.side_effect = [comp1, comp2]

        self.tool_mgr.responses["finish_task"] = Response(is_failed=False, is_terminated=True, content="Done")

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            # Requirement: When a model response is truncated at the generation limit, the agent runner resumes generation with a continuation turn.
            # Requirement: When tool execution produces a terminating response, the agent runner concludes the run and returns an agent outcome, or halts with an unexpected failure if the response indicates terminating failure.
            self.assertTrue(outcome.is_success)
            # Expect: assistant Part 1 -> user continuation prompt -> assistant Part 2 -> tool response
            self.assertEqual(len(self.history.messages), 4)
            self.assertEqual(self.history.messages[0].role, "assistant")
            self.assertEqual(self.history.messages[1].role, "user")
            self.assertIn("truncated due to length", self.history.messages[1].content)
            self.assertEqual(self.history.messages[2].role, "assistant")
            self.assertEqual(self.history.messages[3].role, "tool")

    @patch("lib.agent_runner_impl.OpenAI")
    def test_model_error_handling(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Handling OpenAIError by logging and returning a failed outcome."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = OpenAIError("API Rate Limited")

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            with self.assertRaises(RuntimeError) as ctx:
                runner.run()

            self.assertIn("Model error: API Rate Limited", str(ctx.exception))
            # Requirement: The agent runner logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, prefix reuse measurements comparing current wire payloads against previous request payloads with divergence diagnostics, tool names and arguments or text previews, and execution outcomes, including corrective reminders in tool result transcripts when present.
            self.assertTrue(any(e.event_name == "model_error" and "[Turn 1] Model error:" in e.summary for e in self.logger.events))

    @patch("lib.agent_runner_impl.OpenAI")
    def test_completion_request_uses_temperature_0_2(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Transmitting completion request with temperature=0.2."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        comp = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[
            DummyToolCall(id="c1", name="finish", arguments="{}")
        ]))])
        mock_client.chat.completions.create.return_value = comp
        self.tool_mgr.responses["finish"] = Response(is_failed=False, is_terminated=True, content="Done")

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            runner.run()
            # Requirement: When driving a turn, the agent runner transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from model config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter name, and correlates tool results with model invocations according to OpenAI tool calling conventions.
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            self.assertEqual(call_kwargs["temperature"], 0.2)
            self.assertEqual(call_kwargs["timeout"], 30.0)
            self.assertNotIn("max_tokens", call_kwargs)

    @patch("lib.agent_runner_impl.OpenAI")
    def test_model_config_parameters_forwarded_to_completion_request(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Transmitting completion request with temperature, timeout, and max_tokens from model config."""
        self.model_cfg.temperature = 0.7
        self.model_cfg.timeout = 100
        self.model_cfg.max_tokens = 4096

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        comp = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[
            DummyToolCall(id="c1", name="finish", arguments="{}")
        ]))])
        mock_client.chat.completions.create.return_value = comp
        self.tool_mgr.responses["finish"] = Response(is_failed=False, is_terminated=True, content="Done")

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            runner.run()
            # Requirement: When driving a turn, the agent runner transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from model config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter name, and correlates tool results with model invocations according to OpenAI tool calling conventions.
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            self.assertEqual(call_kwargs["temperature"], 0.7)
            self.assertEqual(call_kwargs["timeout"], 100.0)
            self.assertEqual(call_kwargs["max_tokens"], 4096)

    @patch("lib.agent_runner_impl.OpenAI")
    def test_loop_guard_reminder_injected_into_conversation(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Injecting loop reminder into conversation history when loop guard warns."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tc = DummyToolCall(id="call_read", name="read_file", arguments=json.dumps({"file": "foo.py"}))
        comp1 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        tc_term = DummyToolCall(id="call_finish", name="finish", arguments="{}")
        comp2 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc_term]))])
        mock_client.chat.completions.create.side_effect = [comp1, comp2]

        self.tool_mgr.responses["read_file"] = Response(is_failed=False, is_terminated=False, content="file content")
        self.tool_mgr.responses["finish"] = Response(is_failed=False, is_terminated=True, content="Done")

        self.loop_guard.return_values = [LoopReminder(feedback="Tool 'read_file' has repeated 3 times."), None]

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            # Requirement: Before executing each tool call, the agent runner records the tool execution in the loop guard, injecting a loop reminder into the conversation history when a reminder is produced, or concluding the run with an unexpected failure when a loop failure is produced.
            # Requirement: [AgentRunner] The agent runner evaluates tool executions with the loop guard, injecting reminders or halting with an unexpected failure on runaway repetition.
            self.assertTrue(outcome.is_success)
            self.assertTrue(any(e.event_name == "loop_reminder" for e in self.logger.events))
            reminder_msgs = [m for m in self.history.messages if m.role == "user" and "repeated 3 times" in m.content]
            self.assertEqual(len(reminder_msgs), 1)

    @patch("lib.agent_runner_impl.OpenAI")
    def test_loop_guard_failure_terminates_run(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Terminating session immediately upon fatal loop failure."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tc = DummyToolCall(id="call_repeat", name="read_file", arguments=json.dumps({"file": "foo.py"}))
        comp = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        mock_client.chat.completions.create.return_value = comp

        self.loop_guard.return_value = LoopFailure(explanation="Fatal loop detected: tool executed 5 times.")

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            with self.assertRaises(RuntimeError) as ctx:
                runner.run()

            # Requirement: Before executing each tool call, the agent runner records the tool execution in the loop guard, injecting a loop reminder into the conversation history when a reminder is produced, or concluding the run with an unexpected failure when a loop failure is produced.
            # Requirement: [AgentRunner] The agent runner evaluates tool executions with the loop guard, injecting reminders or halting with an unexpected failure on runaway repetition.
            self.assertIn("Fatal loop detected: tool executed 5 times.", str(ctx.exception))
            self.assertTrue(any(e.event_name == "loop_failure" for e in self.logger.events))
            self.assertEqual(len(self.tool_mgr.executions), 0)

    @patch("lib.agent_runner_impl.OpenAI")
    def test_productive_progress_clears_loop_guard(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Forward progress (edit / advance) clears loop guard repetition tracking."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        tc_read = DummyToolCall(id="c1", name="read_file", arguments=json.dumps({"file": "a.py"}))
        tc_replace = DummyToolCall(id="c2", name="replace", arguments=json.dumps({"file": "a.py", "target": "1", "rep": "2"}))
        tc_advance = DummyToolCall(id="c3", name="advance", arguments="{}")
        comp1 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc_read, tc_replace, tc_advance]))])
        mock_client.chat.completions.create.return_value = comp1

        self.tool_mgr.responses["read_file"] = Response(is_failed=False, is_terminated=False, content="read")
        self.tool_mgr.responses["replace"] = Response(is_failed=False, is_terminated=False, content="replaced")
        self.tool_mgr.responses["advance"] = Response(is_failed=False, is_terminated=True, content="advanced")

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            self.assertTrue(outcome.is_success)
            # Requirement: Productive tool executions that modify workspace files or advance the guide step clear repetition tracking in the loop guard.
            self.assertEqual(self.loop_guard.progress_count, 2)

    @patch("lib.agent_runner_impl.OpenAI")
    def test_completion_request_orders_tools_and_parameters_deterministically(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Completion requests sort tools by name and parameters by name deterministically."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        tc = DummyToolCall(id="call_0", name="zebra", arguments="{}")
        comp = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        mock_client.chat.completions.create.return_value = comp

        conv = MockConverter()
        param_z = Parameter(name="z_param", description="z desc", parameter_converter=conv, is_required=True)
        param_a = Parameter(name="a_param", description="a desc", parameter_converter=conv, is_required=False)
        param_b = Parameter(name="b_param", description="b desc", parameter_converter=conv, is_required=True)

        tool_zebra = DummyTool(name="zebra", parameters={param_z, param_a})
        tool_alpha = DummyTool(name="alpha", parameters={param_b, param_a})

        self.tool_mgr.install_tool(tool_zebra)
        self.tool_mgr.install_tool(tool_alpha)
        self.tool_mgr.responses["zebra"] = Response(is_failed=False, is_terminated=True, content="done")

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            self.assertTrue(outcome.is_success)
            # Requirement: When driving a turn, the agent runner transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from model config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter name, and correlates tool results with model invocations according to OpenAI tool calling conventions.
            tools_arg = mock_client.chat.completions.create.call_args.kwargs.get("tools")
            self.assertIsNotNone(tools_arg)
            tool_names = [t["function"]["name"] for t in tools_arg]
            self.assertEqual(tool_names, ["alpha", "zebra"])

            alpha_params = list(tools_arg[0]["function"]["parameters"]["properties"].keys())
            self.assertEqual(alpha_params, ["a_param", "b_param"])

            zebra_params = list(tools_arg[1]["function"]["parameters"]["properties"].keys())
            self.assertEqual(zebra_params, ["a_param", "z_param"])

    @patch("lib.agent_runner_impl.OpenAI")
    def test_tool_execution_logs_corrective_reminder_in_transcript(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Tool execution log event transcript representation includes corrective reminder when present."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        tc1 = DummyToolCall(id="c1", name="failing_tool", arguments="{}")
        tc2 = DummyToolCall(id="c2", name="finish", arguments="{}")
        comp1 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc1]))])
        comp2 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc2]))])
        mock_client.chat.completions.create.side_effect = [comp1, comp2]

        self.tool_mgr.responses["failing_tool"] = Response(
            is_failed=True,
            is_terminated=False,
            content="Execution failed.",
            reminder="Ensure parameters are non-empty.",
        )
        self.tool_mgr.responses["finish"] = Response(
            is_failed=False,
            is_terminated=True,
            content="Finished successfully.",
            reminder=None,
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            self.assertTrue(outcome.is_success)
            # Requirement: The agent runner logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, prefix reuse measurements comparing current wire payloads against previous request payloads with divergence diagnostics, tool names and arguments or text previews, and execution outcomes, including corrective reminders in tool result transcripts when present.
            tool_events = [e for e in self.logger.events if e.event_name == "tool_execution"]
            self.assertEqual(len(tool_events), 2)
            self.assertIn("Ensure parameters are non-empty.", tool_events[0].transcript_representation)
            self.assertNotIn("Reminder:", tool_events[1].transcript_representation)

    @patch("lib.agent_runner_impl.OpenAI")
    def test_prefix_reuse_measured_and_logged_across_turns(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Measuring and logging prefix reuse for conversations sent to OpenAI across turns."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        tc1 = DummyToolCall(id="c1", name="step_tool", arguments="{}")
        tc2 = DummyToolCall(id="c2", name="finish", arguments="{}")
        comp1 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc1]))])
        comp2 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc2]))])
        mock_client.chat.completions.create.side_effect = [comp1, comp2]

        self.tool_mgr.responses["step_tool"] = Response(
            is_failed=False,
            is_terminated=False,
            content="Step output.",
        )
        self.tool_mgr.responses["finish"] = Response(
            is_failed=False,
            is_terminated=True,
            content="Finished.",
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            self.assertTrue(outcome.is_success)
            # Requirement: The agent runner logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, prefix reuse measurements comparing current wire payloads against previous request payloads with divergence diagnostics, tool names and arguments or text previews, and execution outcomes, including corrective reminders in tool result transcripts when present.
            req_events = [e for e in self.logger.events if e.event_name == "model_request"]
            self.assertEqual(len(req_events), 2)
            self.assertIn("[Turn 1] initial request", req_events[0].summary)
            self.assertIn("Prefix reuse: N/A", req_events[0].transcript_representation)
            self.assertIn("[Turn 2] Prefix reuse:", req_events[1].summary)
            self.assertIn("100% of prev request retained", req_events[1].summary)
            self.assertIn("Prefix intact:", req_events[1].transcript_representation)

    @patch("lib.agent_runner_impl.OpenAI")
    def test_prefix_reuse_divergence_diagnostics_logged(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Measuring and logging prefix reuse divergence diagnostics when previous turn message diverges."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        self.history.append_message(Message(role="user", content="Initial prompt"))

        tc1 = DummyToolCall(id="c1", name="step_tool", arguments="{}")
        tc2 = DummyToolCall(id="c2", name="finish", arguments="{}")
        comp1 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc1]))])
        comp2 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc2]))])
        mock_client.chat.completions.create.side_effect = [comp1, comp2]

        def handle_step(bindings: Any) -> Response:
            self.history._messages[0] = Message(role="user", content="Changed prompt")
            return Response(is_failed=False, is_terminated=False, content="Step done.")

        self.tool_mgr.handlers["step_tool"] = handle_step
        self.tool_mgr.responses["finish"] = Response(
            is_failed=False,
            is_terminated=True,
            content="Finished.",
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            self.assertTrue(outcome.is_success)
            # Requirement: The agent runner logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, prefix reuse measurements comparing current wire payloads against previous request payloads with divergence diagnostics, tool names and arguments or text previews, and execution outcomes, including corrective reminders in tool result transcripts when present.
            req_events = [e for e in self.logger.events if e.event_name == "model_request"]
            self.assertEqual(len(req_events), 2)
            self.assertIn("diverged at msg 0", req_events[1].summary)
            self.assertIn("Divergence detected at message index 0:", req_events[1].transcript_representation)
            self.assertIn("Content changed", req_events[1].transcript_representation)

    @patch("lib.agent_runner_impl.OpenAI")
    def test_follow_up_tool_call_dispatched_when_inject_followups_enabled(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Dispatching follow-up tool call with synthetic assistant invocation when inject_followups is True."""
        self.model_cfg.inject_followups = True
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        tc = DummyToolCall(id="call_initial", name="initial_tool", arguments="{}")
        comp = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        mock_client.chat.completions.create.return_value = comp

        follow_up = FollowUpToolCall(
            tool_name="followup_tool",
            wire_parameter_bindings=WireParameterBindings(bindings=set()),
        )
        self.tool_mgr.responses["initial_tool"] = Response(
            is_failed=False,
            is_terminated=False,
            content="Initial tool executed.",
            follow_up_tool_call=follow_up,
        )
        self.tool_mgr.responses["followup_tool"] = Response(
            is_failed=False,
            is_terminated=True,
            content="Followup tool executed.",
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            # Requirement: When configured by model config to inject followups, a tool response specifying a follow-up tool call prompts execution of the designated tool through the tool manager, appending a synthetic assistant invocation and the resulting follow-up response to the conversation history immediately following the originating response.
            # Requirement: [AgentRunner] The agent runner can dispatch follow-up tool calls specified by tool responses through the tool manager, appending an antecedent synthetic assistant tool invocation message and the follow-up tool response to the conversation history immediately following the originating response.
            self.assertTrue(outcome.is_success)
            self.assertTrue(outcome.response.is_terminated)
            self.assertEqual(outcome.response.content, "Followup tool executed.")
            # Both tools should have been executed
            executed_names = [e[0] for e in self.tool_mgr.executions]
            self.assertEqual(executed_names, ["initial_tool", "followup_tool"])

            # Verify conversation history sequence:
            # 1. assistant tool call message (initial_tool)
            # 2. tool response message (initial_tool)
            # 3. synthetic assistant tool call message (followup_tool)
            # 4. tool response message (followup_tool)
            self.assertEqual(len(self.history.messages), 4)
            self.assertEqual(self.history.messages[0].role, "assistant")
            self.assertEqual(self.history.messages[1].role, "tool")
            self.assertEqual(self.history.messages[1].content, "Initial tool executed.")
            self.assertEqual(self.history.messages[2].role, "assistant")
            self.assertEqual(self.history.messages[2].tool_name, "followup_tool")
            self.assertEqual(self.history.messages[3].role, "tool")
            self.assertEqual(self.history.messages[3].content, "Followup tool executed.")

    @patch("lib.agent_runner_impl.OpenAI")
    def test_follow_up_tool_call_not_dispatched_when_inject_followups_disabled(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Follow-up tool call is ignored when inject_followups is False."""
        self.model_cfg.inject_followups = False
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        tc1 = DummyToolCall(id="call_initial", name="initial_tool", arguments="{}")
        comp1 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc1]))])
        tc2 = DummyToolCall(id="call_finish", name="finish_tool", arguments="{}")
        comp2 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc2]))])
        mock_client.chat.completions.create.side_effect = [comp1, comp2]

        follow_up = FollowUpToolCall(
            tool_name="followup_tool",
            wire_parameter_bindings=WireParameterBindings(bindings=set()),
        )
        self.tool_mgr.responses["initial_tool"] = Response(
            is_failed=False,
            is_terminated=False,
            content="Initial tool executed.",
            follow_up_tool_call=follow_up,
        )
        self.tool_mgr.responses["finish_tool"] = Response(
            is_failed=False,
            is_terminated=True,
            content="Finished.",
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            outcome = runner.run()

            self.assertTrue(outcome.is_success)
            # followup_tool was NOT dispatched automatically
            executed_names = [e[0] for e in self.tool_mgr.executions]
            self.assertEqual(executed_names, ["initial_tool", "finish_tool"])

    @patch("lib.agent_runner_impl.OpenAI")
    def test_terminating_failure_tool_raises_runtime_error(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Tool execution producing terminating failure raises RuntimeError."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tc = DummyToolCall(id="call_fail", name="fail", arguments=json.dumps({"reason": "Cannot proceed"}))
        comp = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        mock_client.chat.completions.create.return_value = comp

        self.tool_mgr.responses["fail"] = Response(is_failed=True, is_terminated=True, content="Cannot proceed")

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentRunner)
            with self.assertRaises(RuntimeError) as ctx:
                runner.run()

            # Requirement: When tool execution produces a terminating response, the agent runner concludes the run and returns an agent outcome, or halts with an unexpected failure if the response indicates terminating failure.
            # Requirement: [AgentRunner] When tool execution produces a termination outcome, the agent runner concludes and returns an agent outcome, or halts with an unexpected failure if the termination indicates a failing outcome.
            self.assertIn("Agent failed: Cannot proceed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
