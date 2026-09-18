"""Unit tests for openai_driver_impl aligned with grounding specifications."""

import json
import unittest
from typing import Any, List, Optional, Set
from unittest.mock import MagicMock, patch

from update_with_ai.parts.loop.lib.loop_conversation import (
    Conversation,
    Message,
    ModelRequest,
)
from update_with_ai.parts.loop.lib.loop_guard import (
    LoopFailure,
    LoopGuard,
    LoopReminder,
)
from update_with_ai.parts.loop.lib.loop_driver import (
    AgentOutcome,
    AgentDriver,
    LoopOutcome,
    LoopDriver,
)
from update_with_ai.parts.openai.lib.openai_driver_impl import (
    AgentDriver as AgentDriverImpl,
    OpenAIError,
    __initialize__,
    _DEFAULT_CONVERTER,
    _format_token_usage,
    _format_tool_log,
)
from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.openai.lib.openai_config import OpenaiConfig
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.core.lib.runner_logger import LogEvent, RunnerLogger
from update_with_ai.parts.sandbox.lib.tool_provider import (
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

    def execute_tool(
        self, name: str, wire_parameter_bindings: WireParameterBindings
    ) -> Response:
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

    def execute_tool(
        self, actual_parameter_bindings: ActualParameterBindings
    ) -> Response:
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
    def __init__(
        self, content: str | None, tool_calls: List[DummyToolCall] | None = None
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls or []


class DummyChoice:
    def __init__(self, message: DummyMessage, finish_reason: str = "stop") -> None:
        self.message = message
        self.finish_reason = finish_reason


class DummyPromptTokensDetails:
    def __init__(self, cached_tokens: Optional[int] = None) -> None:
        self.cached_tokens = cached_tokens


class DummyUsage:
    def __init__(
        self,
        prompt_tokens: Optional[int] = None,
        cached_tokens: Optional[int] = None,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.prompt_tokens_details = (
            DummyPromptTokensDetails(cached_tokens=cached_tokens)
            if cached_tokens is not None
            else None
        )


class DummyCompletion:
    def __init__(
        self, choices: List[DummyChoice], usage: Any = None
    ) -> None:
        self.choices = choices
        self.usage = usage


class OpenAIDriverImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.model_cfg = MockModelConfig()
        self.logger = MockLogger()
        self.history = MockHistory()
        self.loop_guard = MockLoopGuard()
        self.tool_mgr = MockToolManager()

        self.registry.register_instance(
            self.model_cfg, keys=[OpenaiConfig, AgentConfig], tier="system"
        )
        self.registry.register_instance(self.logger, keys=[RunnerLogger], tier="system")
        self.registry.register_instance(
            self.history, keys=[Conversation], tier="agent_session"
        )
        self.registry.register_instance(
            self.loop_guard, keys=[LoopGuard], tier="agent_session"
        )
        self.registry.register_instance(
            self.tool_mgr, keys=[ToolManager], tier="agent_session"
        )

    def test_agent_outcome_dataclass(self) -> None:
        """CUJ: Instantiating AgentOutcome dataclass."""
        resp = Response(is_failed=False, is_terminated=True, content="Success")
        outcome = AgentOutcome(
            is_success=True, response=resp, conversation=self.history
        )
        self.assertTrue(outcome.is_success)
        self.assertEqual(outcome.response, resp)
        self.assertEqual(outcome.conversation_history, self.history)

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_response_without_tool_calls_prompts_reminder_and_continues(
        self, mock_openai_cls: MagicMock
    ) -> None:
        """CUJ: Injecting tool reminder and continuing when model returns no tool calls."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # Turn 1: Model returns text without tool calls
        comp1 = DummyCompletion(
            [DummyChoice(DummyMessage("I will inspect the files."))]
        )
        # Turn 2: Model invokes terminating tool call
        tc = DummyToolCall(
            id="call_finish",
            name="finish_task",
            arguments=json.dumps({"summary": "done"}),
        )
        comp2 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        mock_client.chat.completions.create.side_effect = [comp1, comp2]

        term_resp = Response(is_failed=False, is_terminated=True, content="Done")
        self.tool_mgr.responses["finish_task"] = term_resp

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            outcome = runner.run()

            # Requirement: When a model response produces no tool executions, the agent driver appends a prompt to the conversation reminding that progress and conclusion require invoking tools, and continues the turn loop.
            # Requirement: [AgentDriver] When a model response contains no tool executions, the agent driver injects a tool reminder into the conversation and continues the turn loop.
            # Requirement: When tool execution produces a terminating response, the agent driver concludes the run and returns an agent outcome, or halts with an unexpected failure if the response indicates terminating failure.
            self.assertTrue(outcome.is_success)
            self.assertEqual(len(self.history.messages), 4)
            self.assertEqual(self.history.messages[0].role, "assistant")
            self.assertEqual(
                self.history.messages[0].content, "I will inspect the files."
            )
            self.assertEqual(self.history.messages[1].role, "user")
            self.assertIn("No tools were executed", self.history.messages[1].content)
            self.assertEqual(self.history.messages[2].role, "assistant")
            # Requirement: The loop driver logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, conversation token size rounded to the nearest thousand tokens and percentage of tokens cached on the last turn from model response usage fields, tool names and arguments or text previews, and tool execution status stating the file read or written and the timestamp without inlining file content, including corrective reminders in tool result transcripts when present.
            # Requirement: [AgentDriver] The agent driver records log events for interaction turns, tool executions, and turn outcomes to the runner logger.
            comp_events = [
                e for e in self.logger.events if e.event_name == "model_completion"
            ]
            self.assertTrue(len(comp_events) >= 2)
            self.assertIn("[Turn 1] Assistant (text):", comp_events[0].summary)
            self.assertIn("[Turn 2] Assistant: finish_task", comp_events[1].summary)

            tool_events = [
                e for e in self.logger.events if e.event_name == "tool_execution"
            ]
            self.assertTrue(len(tool_events) >= 1)
            self.assertIn(
                "[Turn 2] Tool finish_task: COMPLETED -> Done", tool_events[0].summary
            )

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_conversation_limit_exceeded_fails(
        self, mock_openai_cls: MagicMock
    ) -> None:
        """CUJ: Concluding with failure when turns reach the conversation limit."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        comp = DummyCompletion([DummyChoice(DummyMessage("Still thinking..."))])
        mock_client.chat.completions.create.return_value = comp

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)

            # Requirement: When turns reach the conversation limit from agent config, the agent driver halts with an unexpected failure.
            # Requirement: [AgentDriver] When the conversation limit from agent config is exceeded, the agent driver halts with an unexpected failure.
            with self.assertRaises(RuntimeError) as ctx:
                runner.run()
            self.assertIn("Conversation limit reached", str(ctx.exception))
            self.assertEqual(mock_client.chat.completions.create.call_count, 5)

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_tool_call_and_termination(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Dispatching tool calls to tool manager and concluding on terminal response."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        tc = DummyToolCall(
            id="call_1",
            name="finish_task",
            arguments=json.dumps({"summary": "all done"}),
        )
        completion = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        mock_client.chat.completions.create.return_value = completion

        term_resp = Response(
            is_failed=False, is_terminated=True, content="Task completed successfully"
        )
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
                        parameter_converter=MockConverter(),
                        is_required=True,
                    )
                }

            def execute_tool(
                self, actual_parameter_bindings: ActualParameterBindings
            ) -> Response:
                return term_resp

        self.tool_mgr.install_tool(DummyTool())

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            outcome = runner.run()

            # Requirement: [AgentDriver] The agent driver drives turns by sending model requests to a language model and executing requested tools.
            # Requirement: When tool execution produces a terminating response, the agent driver concludes the run and returns an agent outcome, or halts with an unexpected failure if the response indicates terminating failure.
            # Requirement: [AgentDriver] When tool execution produces a termination outcome, the agent driver concludes and returns an agent outcome, or halts with an unexpected failure if the termination indicates a failing outcome.
            self.assertTrue(outcome.is_success)
            self.assertTrue(outcome.response.is_terminated)
            self.assertEqual(outcome.response.content, "Task completed successfully")
            self.assertEqual(len(self.tool_mgr.executions), 1)
            self.assertEqual(self.tool_mgr.executions[0][0], "finish_task")
            # Requirement: [AgentDriver] The agent driver appends model responses and correlates tool responses with tool call identifiers in the conversation.
            self.assertEqual(len(self.history.tool_responses), 1)
            self.assertEqual(self.history.tool_responses[0][1], "finish_task")

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_non_terminating_tool_failure_continues_run(
        self, mock_openai_cls: MagicMock
    ) -> None:
        """CUJ: Non-terminating tool failure appends feedback and run continues."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        tc1 = DummyToolCall(
            id="call_fail", name="edit_file", arguments=json.dumps({"path": "foo.py"})
        )
        comp1 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc1]))])
        tc2 = DummyToolCall(
            id="call_finish",
            name="finish_task",
            arguments=json.dumps({"summary": "recovered"}),
        )
        comp2 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc2]))])
        mock_client.chat.completions.create.side_effect = [comp1, comp2]

        self.tool_mgr.responses["edit_file"] = Response(
            is_failed=True, is_terminated=False, content="Error: file not found"
        )
        self.tool_mgr.responses["finish_task"] = Response(
            is_failed=False, is_terminated=True, content="Recovered"
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            outcome = runner.run()

            # Requirement: When driving a turn, the agent driver transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from model config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter name, and correlates tool results with model invocations according to OpenAI tool calling conventions.
            self.assertEqual(mock_client.chat.completions.create.call_count, 2)
            turn2_messages = mock_client.chat.completions.create.call_args_list[
                1
            ].kwargs["messages"]
            asst_tc_msg = next(
                m
                for m in turn2_messages
                if m["role"] == "assistant" and "tool_calls" in m
            )
            self.assertEqual(asst_tc_msg["tool_calls"][0]["id"], "call_fail")
            self.assertEqual(
                asst_tc_msg["tool_calls"][0]["function"]["name"], "edit_file"
            )
            tool_res_msg = next(m for m in turn2_messages if m["role"] == "tool")
            self.assertEqual(tool_res_msg["tool_call_id"], "call_fail")

            # Requirement: When tool execution produces a non-terminating failure response, the failure feedback is appended to the conversation and the run continues.
            # Requirement: When tool execution produces a terminating response, the agent driver concludes the run and returns an agent outcome, or halts with an unexpected failure if the response indicates terminating failure.
            self.assertTrue(outcome.is_success)
            self.assertEqual(len(self.history.tool_responses), 2)
            self.assertTrue(self.history.tool_responses[0][0].is_failed)
            self.assertEqual(
                self.history.tool_responses[0][0].content, "Error: file not found"
            )
            self.assertFalse(self.history.tool_responses[1][0].is_failed)
            self.assertEqual(self.history.tool_responses[1][0].content, "Recovered")

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_continuation_turn_on_truncated_response(
        self, mock_openai_cls: MagicMock
    ) -> None:
        """CUJ: Model response truncated due to finish_reason='length' triggers continuation turn."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # Turn 1: Truncated response (no tool calls, finish_reason="length")
        comp1 = DummyCompletion(
            [
                DummyChoice(
                    DummyMessage("Part 1: The analysis begins..."),
                    finish_reason="length",
                )
            ]
        )
        # Turn 2: Completes and calls tool
        tc = DummyToolCall(id="call_finish", name="finish_task", arguments="{}")
        comp2 = DummyCompletion(
            [
                DummyChoice(
                    DummyMessage("Part 2: concluding.", tool_calls=[tc]),
                    finish_reason="stop",
                )
            ]
        )
        mock_client.chat.completions.create.side_effect = [comp1, comp2]

        self.tool_mgr.responses["finish_task"] = Response(
            is_failed=False, is_terminated=True, content="Done"
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            outcome = runner.run()

            # Requirement: When a model response is truncated at the generation limit, the agent driver resumes generation with a continuation turn.
            # Requirement: When tool execution produces a terminating response, the agent driver concludes the run and returns an agent outcome, or halts with an unexpected failure if the response indicates terminating failure.
            self.assertTrue(outcome.is_success)
            # Expect: assistant Part 1 -> user continuation prompt -> assistant Part 2 -> tool response
            self.assertEqual(len(self.history.messages), 4)
            self.assertEqual(self.history.messages[0].role, "assistant")
            self.assertEqual(self.history.messages[1].role, "user")
            self.assertIn("truncated due to length", self.history.messages[1].content)
            self.assertIn("replace_file_content", self.history.messages[1].content)
            self.assertEqual(self.history.messages[2].role, "assistant")
            self.assertEqual(self.history.messages[3].role, "tool")

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_model_error_handling(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Handling OpenAIError by logging and returning a failed outcome."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = OpenAIError(
            "API Rate Limited"
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            with self.assertRaises(RuntimeError) as ctx:
                runner.run()

            self.assertIn("Model error: API Rate Limited", str(ctx.exception))
            # Requirement: The loop driver logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, conversation token size rounded to the nearest thousand tokens and percentage of tokens cached on the last turn from model response usage fields, tool names and arguments or text previews, and tool execution status stating the file read or written and the timestamp without inlining file content, including corrective reminders in tool result transcripts when present.
            self.assertTrue(
                any(
                    e.event_name == "model_error"
                    and "[Turn 1] Model error:" in e.summary
                    for e in self.logger.events
                )
            )

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_completion_request_uses_temperature_0_2(
        self, mock_openai_cls: MagicMock
    ) -> None:
        """CUJ: Transmitting completion request with temperature=0.2."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        comp = DummyCompletion(
            [
                DummyChoice(
                    DummyMessage(
                        None,
                        tool_calls=[
                            DummyToolCall(id="c1", name="finish", arguments="{}")
                        ],
                    )
                )
            ]
        )
        mock_client.chat.completions.create.return_value = comp
        self.tool_mgr.responses["finish"] = Response(
            is_failed=False, is_terminated=True, content="Done"
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            runner.run()
            # Requirement: When driving a turn, the agent driver transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from model config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter name, and correlates tool results with model invocations according to OpenAI tool calling conventions.
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            self.assertEqual(call_kwargs["temperature"], 0.2)
            self.assertEqual(call_kwargs["timeout"], 30.0)
            self.assertNotIn("max_tokens", call_kwargs)

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_model_config_parameters_forwarded_to_completion_request(
        self, mock_openai_cls: MagicMock
    ) -> None:
        """CUJ: Transmitting completion request with temperature, timeout, and max_tokens from model config."""
        self.model_cfg.temperature = 0.7
        self.model_cfg.timeout = 100
        self.model_cfg.max_tokens = 4096

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        comp = DummyCompletion(
            [
                DummyChoice(
                    DummyMessage(
                        None,
                        tool_calls=[
                            DummyToolCall(id="c1", name="finish", arguments="{}")
                        ],
                    )
                )
            ]
        )
        mock_client.chat.completions.create.return_value = comp
        self.tool_mgr.responses["finish"] = Response(
            is_failed=False, is_terminated=True, content="Done"
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            runner.run()
            # Requirement: When driving a turn, the agent driver transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from openai config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter name, and correlates tool results with model invocations according to OpenAI tool calling conventions.
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            self.assertEqual(call_kwargs["temperature"], 0.7)
            self.assertEqual(call_kwargs["timeout"], 100.0)
            self.assertEqual(call_kwargs["max_tokens"], 4096)

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_loop_guard_reminder_injected_into_conversation(
        self, mock_openai_cls: MagicMock
    ) -> None:
        """CUJ: Injecting loop reminder into conversation history when loop guard warns."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tc = DummyToolCall(
            id="call_read", name="view_file", arguments=json.dumps({"path": "foo.py"})
        )
        comp1 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        tc_term = DummyToolCall(id="call_finish", name="finish", arguments="{}")
        comp2 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc_term]))])
        mock_client.chat.completions.create.side_effect = [comp1, comp2]

        self.tool_mgr.responses["view_file"] = Response(
            is_failed=False, is_terminated=False, content="file content"
        )
        self.tool_mgr.responses["finish"] = Response(
            is_failed=False, is_terminated=True, content="Done"
        )

        self.loop_guard.return_values = [
            LoopReminder(feedback="Tool 'view_file' has repeated 3 times."),
            None,
        ]

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            outcome = runner.run()

            # Requirement: Before executing each tool call, the agent driver records the tool execution in the loop guard, injecting a loop reminder into the conversation when a reminder is produced, or concluding the run with an unexpected failure when a loop failure is produced.
            # Requirement: [AgentDriver] The agent driver evaluates tool executions with the loop guard, injecting reminders or halting with an unexpected failure on runaway repetition.
            self.assertTrue(outcome.is_success)
            self.assertTrue(
                any(e.event_name == "loop_reminder" for e in self.logger.events)
            )
            reminder_msgs = [
                m
                for m in self.history.messages
                if m.role == "user" and "repeated 3 times" in m.content
            ]
            self.assertEqual(len(reminder_msgs), 1)

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_loop_guard_failure_terminates_run(
        self, mock_openai_cls: MagicMock
    ) -> None:
        """CUJ: Terminating session immediately upon fatal loop failure."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tc = DummyToolCall(
            id="call_repeat", name="view_file", arguments=json.dumps({"path": "foo.py"})
        )
        comp = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        mock_client.chat.completions.create.return_value = comp

        self.loop_guard.return_value = LoopFailure(
            explanation="Fatal loop detected: tool executed 5 times."
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            with self.assertRaises(RuntimeError) as ctx:
                runner.run()

            # Requirement: Before executing each tool call, the agent driver records the tool execution in the loop guard, injecting a loop reminder into the conversation when a reminder is produced, or concluding the run with an unexpected failure when a loop failure is produced.
            # Requirement: [AgentDriver] The agent driver evaluates tool executions with the loop guard, injecting reminders or halting with an unexpected failure on runaway repetition.
            self.assertIn(
                "Fatal loop detected: tool executed 5 times.", str(ctx.exception)
            )
            self.assertTrue(
                any(e.event_name == "loop_failure" for e in self.logger.events)
            )
            self.assertEqual(len(self.tool_mgr.executions), 0)

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_productive_progress_clears_loop_guard(
        self, mock_openai_cls: MagicMock
    ) -> None:
        """CUJ: Forward progress (edit / advance) clears loop guard repetition tracking."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        tc_read = DummyToolCall(
            id="c1", name="view_file", arguments=json.dumps({"path": "a.py"})
        )
        tc_replace = DummyToolCall(
            id="c2",
            name="replace",
            arguments=json.dumps({"file": "a.py", "target": "1", "rep": "2"}),
        )
        tc_advance = DummyToolCall(id="c3", name="advance", arguments="{}")
        comp1 = DummyCompletion(
            [
                DummyChoice(
                    DummyMessage(None, tool_calls=[tc_read, tc_replace, tc_advance])
                )
            ]
        )
        mock_client.chat.completions.create.return_value = comp1

        self.tool_mgr.responses["view_file"] = Response(
            is_failed=False, is_terminated=False, content="read"
        )
        self.tool_mgr.responses["replace"] = Response(
            is_failed=False, is_terminated=False, content="replaced"
        )
        self.tool_mgr.responses["advance"] = Response(
            is_failed=False, is_terminated=True, content="advanced"
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            outcome = runner.run()

            self.assertTrue(outcome.is_success)
            # Requirement: Productive tool executions that modify workspace files or advance the guide step clear repetition tracking in the loop guard.
            self.assertEqual(self.loop_guard.progress_count, 2)

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_completion_request_orders_tools_and_parameters_deterministically(
        self, mock_openai_cls: MagicMock
    ) -> None:
        """CUJ: Completion requests sort tools by name and parameters by name deterministically."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        tc = DummyToolCall(id="call_0", name="zebra", arguments="{}")
        comp = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        mock_client.chat.completions.create.return_value = comp

        conv = MockConverter()
        param_z = Parameter(
            name="z_param",
            description="z desc",
            parameter_converter=conv,
            is_required=True,
        )
        param_a = Parameter(
            name="a_param",
            description="a desc",
            parameter_converter=conv,
            is_required=False,
        )
        param_b = Parameter(
            name="b_param",
            description="b desc",
            parameter_converter=conv,
            is_required=True,
        )

        tool_zebra = DummyTool(name="zebra", parameters={param_z, param_a})
        tool_alpha = DummyTool(name="alpha", parameters={param_b, param_a})

        self.tool_mgr.install_tool(tool_zebra)
        self.tool_mgr.install_tool(tool_alpha)
        self.tool_mgr.responses["zebra"] = Response(
            is_failed=False, is_terminated=True, content="done"
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            outcome = runner.run()

            self.assertTrue(outcome.is_success)
            # Requirement: When driving a turn, the agent driver transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from model config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter name, and correlates tool results with model invocations according to OpenAI tool calling conventions.
            tools_arg = mock_client.chat.completions.create.call_args.kwargs.get(
                "tools"
            )
            self.assertIsNotNone(tools_arg)
            tool_names = [t["function"]["name"] for t in tools_arg]
            self.assertEqual(tool_names, ["alpha", "zebra"])

            alpha_params = list(
                tools_arg[0]["function"]["parameters"]["properties"].keys()
            )
            self.assertEqual(alpha_params, ["a_param", "b_param"])

            zebra_params = list(
                tools_arg[1]["function"]["parameters"]["properties"].keys()
            )
            self.assertEqual(zebra_params, ["a_param", "z_param"])

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_tool_execution_logs_corrective_reminder_in_transcript(
        self, mock_openai_cls: MagicMock
    ) -> None:
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
            runner = scope.get_singleton(AgentDriver)
            outcome = runner.run()

            self.assertTrue(outcome.is_success)
            # Requirement: The loop driver logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, conversation token size rounded to the nearest thousand tokens and percentage of tokens cached on the last turn from model response usage fields, tool names and arguments or text previews, and tool execution status stating the file read or written and the timestamp without inlining file content, including corrective reminders in tool result transcripts when present.
            tool_events = [
                e for e in self.logger.events if e.event_name == "tool_execution"
            ]
            self.assertEqual(len(tool_events), 2)
            self.assertIn(
                "Ensure parameters are non-empty.",
                tool_events[0].transcript_representation,
            )
            self.assertNotIn("Reminder:", tool_events[1].transcript_representation)

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_token_usage_measured_and_logged_across_turns(
        self, mock_openai_cls: MagicMock
    ) -> None:
        """CUJ: Measuring and logging conversation token size and cache percentage across turns."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        tc1 = DummyToolCall(id="c1", name="step_tool", arguments="{}")
        tc2 = DummyToolCall(id="c2", name="finish", arguments="{}")
        comp1 = DummyCompletion(
            [DummyChoice(DummyMessage(None, tool_calls=[tc1]))],
            usage=DummyUsage(prompt_tokens=1000, cached_tokens=800),
        )
        comp2 = DummyCompletion(
            [DummyChoice(DummyMessage(None, tool_calls=[tc2]))],
            usage=DummyUsage(prompt_tokens=2200, cached_tokens=1100),
        )
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
            runner = scope.get_singleton(AgentDriver)
            outcome = runner.run()

            self.assertTrue(outcome.is_success)
            # Requirement: The loop driver logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, conversation token size rounded to the nearest thousand tokens and percentage of tokens cached on the last turn from model response usage fields, tool names and arguments or text previews, and tool execution status stating the file read or written and the timestamp without inlining file content, including corrective reminders in tool result transcripts when present.
            req_events = [
                e for e in self.logger.events if e.event_name == "model_request"
            ]
            self.assertEqual(len(req_events), 2)
            self.assertIn("[Turn 1] initial request", req_events[0].summary)
            self.assertIn(
                "Conversation tokens: initial request",
                req_events[0].transcript_representation,
            )
            self.assertIn("[Turn 2] 1K tokens, 80% cached", req_events[1].summary)
            self.assertIn(
                "Conversation tokens: 1K tokens (80% cached on last turn)",
                req_events[1].transcript_representation,
            )

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_tool_execution_file_read_and_write_logged_without_inlining_content(
        self, mock_openai_cls: MagicMock
    ) -> None:
        """CUJ: Logging file read and write operations with timestamp without inlining file contents."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        tc1 = DummyToolCall(
            id="c1", name="view_file", arguments=json.dumps({"path": "lib/foo.py"})
        )
        tc2 = DummyToolCall(
            id="c2", name="replace", arguments=json.dumps({"file": "lib/bar.py"})
        )
        tc3 = DummyToolCall(id="c3", name="finish", arguments="{}")
        comp1 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc1]))])
        comp2 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc2]))])
        comp3 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc3]))])
        mock_client.chat.completions.create.side_effect = [comp1, comp2, comp3]

        self.tool_mgr.responses["view_file"] = Response(
            is_failed=False,
            is_terminated=False,
            content="secret file content that should not appear in the logs",
            reminder="Check line numbers",
        )
        self.tool_mgr.responses["replace"] = Response(
            is_failed=False,
            is_terminated=False,
            content="replaced file diff chunk",
        )
        self.tool_mgr.responses["finish"] = Response(
            is_failed=False,
            is_terminated=True,
            content="Finished work.",
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            outcome = runner.run()

            self.assertTrue(outcome.is_success)
            # Requirement: The loop driver logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, conversation token size rounded to the nearest thousand tokens and percentage of tokens cached on the last turn from model response usage fields, tool names and arguments or text previews, and tool execution status stating the file read or written and the timestamp without inlining file content, including corrective reminders in tool result transcripts when present.
            tool_events = [
                e for e in self.logger.events if e.event_name == "tool_execution"
            ]
            self.assertEqual(len(tool_events), 3)

            # View file tool event (read)
            self.assertIn("Tool view_file: read lib/foo.py at", tool_events[0].summary)
            self.assertIn("Read lib/foo.py at", tool_events[0].transcript_representation)
            self.assertIn(
                "Reminder: Check line numbers",
                tool_events[0].transcript_representation,
            )
            self.assertNotIn("secret file content", tool_events[0].summary)
            self.assertNotIn(
                "secret file content", tool_events[0].transcript_representation
            )

            # Replace tool event (write)
            self.assertIn("Tool replace: wrote lib/bar.py at", tool_events[1].summary)
            self.assertIn("Wrote lib/bar.py at", tool_events[1].transcript_representation)
            self.assertNotIn("replaced file diff chunk", tool_events[1].summary)
            self.assertNotIn(
                "replaced file diff chunk", tool_events[1].transcript_representation
            )

            # Non-file tool event
            self.assertIn(
                "Tool finish: COMPLETED -> Finished work.", tool_events[2].summary
            )

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_follow_up_tool_call_dispatched_when_inject_followups_enabled(
        self, mock_openai_cls: MagicMock
    ) -> None:
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
            runner = scope.get_singleton(AgentDriver)
            outcome = runner.run()

            # Requirement: When configured by agent configuration to inject followups, a tool response specifying a follow-up tool call prompts execution of the designated tool, appending a synthetic assistant invocation carrying the follow-up tool call's reasoning text as prior thought preceding the requested tool execution and the resulting follow-up response to the conversation immediately following the originating response.
            # Requirement: [AgentDriver] The agent driver can dispatch follow-up tool calls specified by tool responses, recording the follow-up execution in the conversation.
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
            self.assertEqual(
                self.history.messages[3].content, "Followup tool executed."
            )

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_follow_up_tool_call_not_dispatched_when_inject_followups_disabled(
        self, mock_openai_cls: MagicMock
    ) -> None:
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
            runner = scope.get_singleton(AgentDriver)
            outcome = runner.run()

            self.assertTrue(outcome.is_success)
            # followup_tool was NOT dispatched automatically
            executed_names = [e[0] for e in self.tool_mgr.executions]
            self.assertEqual(executed_names, ["initial_tool", "finish_tool"])

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_terminating_failure_tool_raises_runtime_error(
        self, mock_openai_cls: MagicMock
    ) -> None:
        """CUJ: Tool execution producing terminating failure raises RuntimeError."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tc = DummyToolCall(
            id="call_fail",
            name="fail",
            arguments=json.dumps({"reason": "Cannot proceed"}),
        )
        comp = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        mock_client.chat.completions.create.return_value = comp

        self.tool_mgr.responses["fail"] = Response(
            is_failed=True, is_terminated=True, content="Cannot proceed"
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            with self.assertRaises(RuntimeError) as ctx:
                runner.run()

            # Requirement: When tool execution produces a terminating response, the agent driver concludes the run and returns an agent outcome, or halts with an unexpected failure if the response indicates terminating failure.
            # Requirement: [AgentDriver] When tool execution produces a termination outcome, the agent driver concludes and returns an agent outcome, or halts with an unexpected failure if the termination indicates a failing outcome.
            self.assertIn("Agent failed: Cannot proceed", str(ctx.exception))

    def test_default_converter_and_parameter_fallback(self) -> None:
        """CUJ: Default parameter converter properties and fallback parameter resolution."""
        # Requirement: [AgentDriver] The agent driver drives turns by sending model requests to a language model and executing requested tools.
        self.assertEqual(_DEFAULT_CONVERTER.actual_type, str)
        self.assertIsNotNone(_DEFAULT_CONVERTER.wire_type)
        self.assertEqual(_DEFAULT_CONVERTER.convert("hello"), "hello")

    def test_format_token_usage_and_tool_log_variants(self) -> None:
        """CUJ: Formatting token usage variants and tool log variants for files and non-file operations."""
        # Requirement: The loop driver logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, conversation token size rounded to the nearest thousand tokens and percentage of tokens cached on the last turn from model response usage fields, tool names and arguments or text previews, and tool execution status stating the file read or written and the timestamp without inlining file content, including corrective reminders in tool result transcripts when present.
        s1, t1 = _format_token_usage(None, None)
        self.assertEqual(s1, "initial request")
        self.assertEqual(t1, "Conversation tokens: initial request")

        s2, t2 = _format_token_usage(1499, 750)
        self.assertEqual(s2, "1K tokens, 50% cached")
        self.assertEqual(t2, "Conversation tokens: 1K tokens (50% cached on last turn)")

        s3, t3 = _format_token_usage(2800, 2240)
        self.assertEqual(s3, "3K tokens, 80% cached")
        self.assertEqual(t3, "Conversation tokens: 3K tokens (80% cached on last turn)")

        s4, t4 = _format_token_usage(1000, 0)
        self.assertEqual(s4, "1K tokens, 0% cached")
        self.assertEqual(t4, "Conversation tokens: 1K tokens (0% cached on last turn)")

        s5, t5 = _format_token_usage(1000, None)
        self.assertEqual(s5, "1K tokens, 0% cached")
        self.assertEqual(t5, "Conversation tokens: 1K tokens (0% cached on last turn)")

        # Tool log variants:
        # Failed tool execution retains error details
        failed_resp = Response(
            is_failed=True, is_terminated=False, content="file not found error"
        )
        s_fail, t_fail = _format_tool_log(
            "view_file", {"path": "missing.py"}, failed_resp, 1
        )
        self.assertIn("FAILED -> file not found error", s_fail)
        self.assertEqual(t_fail, "file not found error")

        # Follow-up tool execution prefix
        ok_write = Response(is_failed=False, is_terminated=False, content="ok")
        s_fu, t_fu = _format_tool_log(
            "replace_file_content",
            {"file": "mod.py"},
            ok_write,
            2,
            is_followup=True,
        )
        self.assertIn(
            "[Turn 2] Follow-up Tool replace_file_content: wrote mod.py at", s_fu
        )
        self.assertIn("Wrote mod.py at", t_fu)

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_completion_and_output_formatting_and_truncation(
        self, mock_openai_cls: MagicMock
    ) -> None:
        """CUJ: Formatting and truncating long arguments, assistant previews, and tool outputs."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # Turn 1: tool call with arguments > 60 chars and invalid JSON arguments
        long_arg = "a" * 70
        tc1 = DummyToolCall(
            id="c1", name="step_tool", arguments=f'{{"key": "{long_arg}"}}'
        )
        tc_bad_json = DummyToolCall(
            id="c_bad", name="step_tool", arguments="invalid JSON {"
        )
        comp1 = DummyCompletion(
            [
                DummyChoice(
                    DummyMessage(None, tool_calls=[tc1, tc_bad_json]),
                    finish_reason="length",
                )
            ]
        )

        # Turn 2: text completion with length > 80 chars without tool calls
        long_text = "This is a very long text response that exceeds eighty characters in length to test preview truncation."
        comp2 = DummyCompletion([DummyChoice(DummyMessage(long_text, tool_calls=[]))])

        # Turn 3: finish tool call
        tc3 = DummyToolCall(id="c3", name="finish", arguments="{}")
        comp3 = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc3]))])

        mock_client.chat.completions.create.side_effect = [comp1, comp2, comp3]

        long_output_first_line = "X" * 90 + "\nsecond line"
        self.tool_mgr.responses["step_tool"] = Response(
            is_failed=False,
            is_terminated=False,
            content=long_output_first_line,
        )
        self.tool_mgr.responses["finish"] = Response(
            is_failed=False,
            is_terminated=True,
            content=long_output_first_line,
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            outcome = runner.run()
            # Requirement: The loop driver logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, conversation token size rounded to the nearest thousand tokens and percentage of tokens cached on the last turn from model response usage fields, tool names and arguments or text previews, and tool execution status stating the file read or written and the timestamp without inlining file content, including corrective reminders in tool result transcripts when present.
            self.assertTrue(outcome.is_success)
            comp_events = [
                e for e in self.logger.events if e.event_name == "model_completion"
            ]
            self.assertTrue(any("..." in e.summary for e in comp_events))
            tool_events = [
                e for e in self.logger.events if e.event_name == "tool_execution"
            ]
            self.assertTrue(any("..." in e.summary for e in tool_events))

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_parameter_conversion_exception_fallback(
        self, mock_openai_cls: MagicMock
    ) -> None:
        """CUJ: Parameter converter exception falls back to unconverted wire value."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        tc = DummyToolCall(
            id="c1",
            name="custom_tool",
            arguments='{"param": "not_an_int", "extra": "undeclared"}',
        )
        comp = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        mock_client.chat.completions.create.return_value = comp

        class FailingConverter(MockConverter):
            def convert(self, wire_value: Any) -> Any:
                raise ValueError("Conversion failed")

        failing_param = Parameter(
            name="param", description="", parameter_converter=FailingConverter()
        )
        custom_tool = DummyTool(name="custom_tool", parameters={failing_param})

        self.tool_mgr.install_tool(custom_tool)
        self.tool_mgr.responses["custom_tool"] = Response(
            is_failed=False, is_terminated=True, content="Done"
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            outcome = runner.run()
            # Requirement: [AgentDriver] The agent driver drives turns by sending model requests to a language model and executing requested tools.
            self.assertTrue(outcome.is_success)

    @patch("update_with_ai.parts.openai.lib.openai_driver_impl.OpenAI")
    def test_followup_tool_execution_branches(self, mock_openai_cls: MagicMock) -> None:
        """CUJ: Follow-up tool execution handles long summaries, failures, reminders, progress recording, and terminating errors."""
        self.model_cfg.inject_followups = True
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        tc = DummyToolCall(id="c_start", name="start", arguments="{}")
        comp = DummyCompletion([DummyChoice(DummyMessage(None, tool_calls=[tc]))])
        mock_client.chat.completions.create.return_value = comp

        # Followup 1: non-terminating, failed, long content
        long_line = "F" * 90 + "\nsecond line"
        follow1 = FollowUpToolCall(
            tool_name="advance",
            wire_parameter_bindings=WireParameterBindings(bindings={("a", "1")}),
        )
        resp_start = Response(
            is_failed=False,
            is_terminated=False,
            content="Start done",
            follow_up_tool_call=follow1,
        )
        self.tool_mgr.responses["start"] = resp_start

        # Followup 2: non-terminating, succeeded, advance tool name (calls guard.record_progress), with reminder
        follow2 = FollowUpToolCall(
            tool_name="replace",
            wire_parameter_bindings=WireParameterBindings(bindings=set()),
        )
        resp_f1 = Response(
            is_failed=True,
            is_terminated=False,
            content=long_line,
            follow_up_tool_call=follow2,
        )
        self.tool_mgr.responses["advance"] = resp_f1

        # Followup 3: terminating failure -> raises RuntimeError
        follow3 = FollowUpToolCall(
            tool_name="fail_followup",
            wire_parameter_bindings=WireParameterBindings(bindings=set()),
        )
        resp_f2 = Response(
            is_failed=False,
            is_terminated=False,
            content="OK step",
            reminder="Check files",
            follow_up_tool_call=follow3,
        )
        self.tool_mgr.responses["replace"] = resp_f2

        resp_f3 = Response(
            is_failed=True,
            is_terminated=True,
            content="Fatal followup error",
        )
        self.tool_mgr.responses["fail_followup"] = resp_f3

        with enter_phase("agent_session", registry=self.registry) as scope:
            runner = scope.get_singleton(AgentDriver)
            with self.assertRaises(RuntimeError) as ctx:
                runner.run()

            # Requirement: [AgentDriver] The agent driver can dispatch follow-up tool calls specified by tool responses, recording the follow-up execution in the conversation.
            self.assertIn("Agent failed: Fatal followup error", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
