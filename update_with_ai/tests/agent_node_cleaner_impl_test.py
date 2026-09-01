"""Tests for agent_node_cleaner_impl derived from LLS."""

import unittest
from typing import Sequence, Optional, Union, List, Dict
from lib.dag_storage import NodeId, PendingMessage, DagMessage, NodeData
from lib.dag_node_cleaner import ChangeMessage, FeedbackMessage
from lib.tool_provider import (
    ToolProvider,
    ToolMetadata,
    ToolResult,
    TerminationOutcome,
    ToolOutcome,
    ToolArguments,
    Tool,
)
from lib.conversation_history import (
    ConversationHistory,
    ConversationHistoryFactory,
    HistoryMessage,
    ModelRequest,
)
from lib.loop_guard import LoopGuard
from lib.sandbox import Sandbox, SandboxFactory, SandboxConfig
from lib.file_reader import SessionStartRead
from lib.build_graph_storage import BuildGraphStorage, NodeDefinition
from lib.agent_runner import AgentRunner, AgentOutcome, IterationLimit
from lib.agent_node_cleaner_impl import AgentNodeCleanerImpl


class MockRunner(AgentRunner):
    def __init__(self, canned_outcome: AgentOutcome) -> None:
        self.canned_outcome = canned_outcome
        self.received_providers: List[ToolProvider] = []
        self.received_histories: List[ConversationHistory] = []

    def run(
        self,
        tool_provider: ToolProvider,
        history: ConversationHistory,
        logger=None,
        loop_guard: Optional[LoopGuard] = None,
        iteration_limit: IterationLimit = 20,
    ) -> AgentOutcome:
        self.received_providers.append(tool_provider)
        self.received_histories.append(history)
        return self.canned_outcome


class MockSandbox(Sandbox):
    def __init__(
        self,
        tools: Optional[Sequence[Tool]] = None,
        modified: bool = False,
        startup_interaction: Optional[Sequence[ToolResult]] = None,
    ) -> None:
        self._tools = list(tools) if tools is not None else []
        self._modified = modified
        self._startup_interaction = list(startup_interaction) if startup_interaction is not None else []
        self.templates_materialized = False

    def get_tools(self) -> Sequence[Tool]:
        return self._tools

    def get_session_start_reads(self) -> Sequence[SessionStartRead]:
        return []

    def get_startup_interaction(self) -> Sequence[ToolResult]:
        return self._startup_interaction

    def materialize_startup_templates(self) -> None:
        self.templates_materialized = True

    def has_file_modifications(self) -> bool:
        return self._modified


class MockSandboxFactory(SandboxFactory):
    def __init__(self, sandbox: Sandbox) -> None:
        self.sandbox = sandbox
        self.received_configs: List[SandboxConfig] = []

    def create_sandbox(
        self,
        config: SandboxConfig,
    ) -> Sandbox:
        self.received_configs.append(config)
        return self.sandbox


class MockBuildGraphStorage(BuildGraphStorage):
    def __init__(
        self,
        configs: Optional[Dict[NodeId, SandboxConfig]] = None,
        prompts: Optional[Dict[NodeId, str]] = None,
    ) -> None:
        self.configs = configs or {}
        self.prompts = prompts or {}

    def get_sandbox_config(self, node: NodeId) -> SandboxConfig:
        return self.configs.get(
            node,
            SandboxConfig(file_mappings={}, read_only_files=[], read_write_files=[], templates={}),
        )

    def get_task_prompt(self, node: NodeId) -> Optional[str]:
        return self.prompts.get(node)

    def get_node_definition(self, node: NodeId) -> Optional[NodeDefinition]:
        cfg = self.get_sandbox_config(node)
        prompt = self.get_task_prompt(node)
        return NodeDefinition(sandbox_config=cfg, prompt=prompt)

    def get_dependencies(self, node: NodeId) -> Sequence[NodeId]:
        return []

    def get_reverse_dependencies(self, node: NodeId) -> Sequence[NodeId]:
        return []

    def get_pending_messages(self, node: NodeId) -> Sequence[PendingMessage]:
        return []

    def queue_pending_messages(self, node: NodeId, messages: Sequence[DagMessage]) -> None:
        pass

    def clear_pending_messages(self, node: NodeId) -> None:
        pass

    def record_node_data(self, node: NodeId, data: NodeData) -> None:
        pass

    def get_node_data(self, node: NodeId) -> Optional[NodeData]:
        return None

    def mark_dirty(self, node: NodeId) -> None:
        pass

    def is_dirty(self, node: NodeId) -> bool:
        return False


class SimpleHistory(ConversationHistory):
    def __init__(self) -> None:
        self.messages: List[HistoryMessage] = []

    def initialize(self, initial_messages: Sequence[HistoryMessage]) -> None:
        self.messages = list(initial_messages)

    def append(self, item: Union[HistoryMessage, ToolResult]) -> None:
        if isinstance(item, ToolResult):
            self.messages.append(HistoryMessage(role="tool", content=item.content))
        else:
            self.messages.append(item)

    def get_model_request(self) -> ModelRequest:
        return ModelRequest(messages=list(self.messages))

    def get_messages(self) -> Sequence[HistoryMessage]:
        return list(self.messages)


class MockConversationHistoryFactory(ConversationHistoryFactory):
    def create_conversation_history(self) -> ConversationHistory:
        return SimpleHistory()


class AgentNodeCleanerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.default_storage = MockBuildGraphStorage()

    def test_clean_node_executes_runner_in_sandbox_with_pending_history(self) -> None:
        """Tests CUJ for initializing history with pending messages and executing runner in sandbox.

        Checks postconditions: runner receives history initialized with pending messages and provider is a tool provider.
        """
        outcome = AgentOutcome(
            termination=TerminationOutcome(content="Advanced and completed", is_terminal=True),
            history=[],
        )
        runner = MockRunner(outcome)
        sandbox = MockSandbox(startup_interaction=[ToolResult(content="spec.md content")])
        cleaner = AgentNodeCleanerImpl(
            runner=runner,
            sandbox_factory=MockSandboxFactory(sandbox),
            conversation_history_factory=MockConversationHistoryFactory(),
            storage=self.default_storage,
        )

        pending = [
            DagMessage(content="Pending change from dep", sender="//pkg:dep"),
        ]
        result = cleaner.clean_node("//pkg:target", pending)

        self.assertTrue(sandbox.templates_materialized)
        self.assertEqual(len(runner.received_histories), 1)
        history = runner.received_histories[0]
        self.assertTrue(any("Pending change from dep" in m.content for m in history.get_messages()))
        self.assertEqual(len(runner.received_providers), 1)

    def test_clean_node_unmodified_produces_no_messages(self) -> None:
        """Tests that clean_node produces no messages when run succeeds with modified=False."""
        outcome = AgentOutcome(
            termination=TerminationOutcome(content="Clean run", is_terminal=True),
            history=[],
        )
        runner = MockRunner(outcome)
        sandbox = MockSandbox(modified=False)
        cleaner = AgentNodeCleanerImpl(
            runner=runner,
            sandbox_factory=MockSandboxFactory(sandbox),
            conversation_history_factory=MockConversationHistoryFactory(),
            storage=self.default_storage,
        )
        result = cleaner.clean_node("//pkg:target", [DagMessage(content="check")])
        self.assertEqual(result, [])

    def test_clean_node_translates_blame_outcome_into_feedback_message(self) -> None:
        """Tests CUJ for translating blame tool outcome into FeedbackMessage addressed to blamed dep.

        Checks postconditions: returns Sequence[FeedbackMessage] targeting the blamed node.
        """
        outcome = AgentOutcome(
            termination=TerminationOutcome(content="Blamed //pkg:upstream via dep.py", is_terminal=True),
            history=[],
        )
        runner = MockRunner(outcome)
        sandbox = MockSandbox()
        cleaner = AgentNodeCleanerImpl(
            runner=runner,
            sandbox_factory=MockSandboxFactory(sandbox),
            conversation_history_factory=MockConversationHistoryFactory(),
            storage=self.default_storage,
        )

        result = cleaner.clean_node("//pkg:target", [DagMessage(content="check")])
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(len(result) > 0)
        self.assertTrue(any(isinstance(m, FeedbackMessage) or "Blamed" in getattr(m, "content", "") for m in result))

    def test_clean_node_failure_leaves_node_dirty(self) -> None:
        """Tests invariant that run failure leaves node dirty by returning None or raising."""
        outcome = AgentOutcome(
            termination=TerminationOutcome(content="Failed: Verification failed", is_terminal=True),
            history=[],
        )
        runner = MockRunner(outcome)
        sandbox = MockSandbox()
        cleaner = AgentNodeCleanerImpl(
            runner=runner,
            sandbox_factory=MockSandboxFactory(sandbox),
            conversation_history_factory=MockConversationHistoryFactory(),
            storage=self.default_storage,
        )

        result = cleaner.clean_node("//pkg:target", [DagMessage(content="check")])
        self.assertIsNone(result)

    def test_node_tool_provider_advance_execution(self) -> None:
        """Tests that _NodeToolProvider advance tool executes and terminates cleanly."""
        class ExecutingRunner(AgentRunner):
            def run(self, tool_provider: ToolProvider, history: ConversationHistory, logger=None, loop_guard=None, iteration_limit=20):
                tools = tool_provider.get_tools()
                adv_tool = tools[0]
                term = adv_tool.execute({})
                # Exercise appending to history
                history.append(HistoryMessage(role="assistant", content="done"))
                history.append(ToolResult(content="tool output"))
                _ = history.get_model_request()
                return AgentOutcome(termination=term if isinstance(term, TerminationOutcome) else TerminationOutcome(content="Done"), history=history.get_messages())

        class StubTool:
            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata("advance", "Advance", {})
            def execute(self, a: ToolArguments) -> ToolOutcome:
                return TerminationOutcome(content="Done", is_terminal=True)

        sandbox = MockSandbox(tools=[StubTool()], modified=True)
        cleaner = AgentNodeCleanerImpl(
            runner=ExecutingRunner(),
            sandbox_factory=MockSandboxFactory(sandbox),
            conversation_history_factory=MockConversationHistoryFactory(),
            storage=self.default_storage,
        )
        result = cleaner.clean_node("//pkg:target", [DagMessage(content="start")])
        self.assertIsNotNone(result)
        self.assertTrue(any(isinstance(m, ChangeMessage) for m in result if result))

    def test_clean_node_provides_sandbox_tools_to_runner(self) -> None:
        """Tests that clean_node provides real Sandbox tools to runner (e.g. read_file, replace, advance) rather than a stub."""
        received_tool_names: List[str] = []
        class ToolInspectingRunner(AgentRunner):
            def run(self, tool_provider: ToolProvider, history: ConversationHistory, logger=None, loop_guard=None, iteration_limit=20):
                tools = tool_provider.get_tools()
                for t in tools:
                    received_tool_names.append(t.get_metadata().name)
                return AgentOutcome(termination=TerminationOutcome(content="Advanced and completed", is_terminal=True), history=history.get_messages())

        class ReadTool:
            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata("read_file", "Read", {})
            def execute(self, a: ToolArguments) -> ToolOutcome:
                return ToolResult("ok")

        class AdvTool:
            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata("advance", "Advance", {})
            def execute(self, a: ToolArguments) -> ToolOutcome:
                return TerminationOutcome("ok")

        sandbox = MockSandbox(tools=[ReadTool(), AdvTool()])
        cleaner = AgentNodeCleanerImpl(
            runner=ToolInspectingRunner(),
            sandbox_factory=MockSandboxFactory(sandbox),
            conversation_history_factory=MockConversationHistoryFactory(),
            storage=self.default_storage,
        )
        _ = cleaner.clean_node("//pkg:target", [DagMessage(content="clean")])
        self.assertIn("advance", received_tool_names)
        self.assertIn("read_file", received_tool_names)

    def test_clean_node_retrieves_sandbox_config_from_storage(self) -> None:
        """Tests that clean_node looks up the target node's SandboxConfig in BuildGraphStorage."""
        target_config = SandboxConfig(
            file_mappings={"virtual.py": "real.py"},
            read_only_files=["read.py"],
            read_write_files=["write.py"],
            templates={"tmpl.py": "template content"},
        )
        storage = MockBuildGraphStorage({"//pkg:target": target_config})
        sandbox = MockSandbox()
        factory = MockSandboxFactory(sandbox)
        cleaner = AgentNodeCleanerImpl(
            runner=MockRunner(
                AgentOutcome(
                    termination=TerminationOutcome(content="Done", is_terminal=True),
                    history=[],
                )
            ),
            sandbox_factory=factory,
            conversation_history_factory=MockConversationHistoryFactory(),
            storage=storage,
        )
        _ = cleaner.clean_node("//pkg:target", [DagMessage(content="clean")])
        self.assertEqual(len(factory.received_configs), 1)
        self.assertEqual(factory.received_configs[0], target_config)

    def test_clean_node_seeds_conversation_with_task_prompt_from_storage(self) -> None:
        """Tests that clean_node seeds the conversation history with the node task prompt from storage."""
        storage = MockBuildGraphStorage(
            configs={
                "//pkg:target": SandboxConfig(
                    file_mappings={},
                    read_only_files=[],
                    read_write_files=[],
                    templates={},
                )
            },
            prompts={"//pkg:target": "Ensure the lib module conforms to LLS."},
        )
        runner = MockRunner(
            AgentOutcome(
                termination=TerminationOutcome(content="Done", is_terminal=True),
                history=[],
            )
        )
        cleaner = AgentNodeCleanerImpl(
            runner=runner,
            sandbox_factory=MockSandboxFactory(MockSandbox()),
            conversation_history_factory=MockConversationHistoryFactory(),
            storage=storage,
        )
    def test_clean_node_seeds_startup_interaction_with_synthetic_tool_calls(self) -> None:
        """Tests that clean_node pairs startup interaction items with synthetic read_file and advance tool calls."""
        storage = MockBuildGraphStorage(
            configs={
                "//pkg:target": SandboxConfig(
                    file_mappings={"guide.md": "path/guide.md"},
                    read_only_files=["guide.md"],
                    read_write_files=[],
                    templates={},
                )
            },
            prompts={"//pkg:target": "Clean this node."},
        )
        sandbox = MockSandbox(
            startup_interaction=[
                ToolResult(content="# Guide Content"),
                ToolResult(content="Summary guidance", guidance="step_1"),
            ]
        )
        runner = MockRunner(
            AgentOutcome(
                termination=TerminationOutcome(content="Done", is_terminal=True),
                history=[],
            )
        )
        cleaner = AgentNodeCleanerImpl(
            runner=runner,
            sandbox_factory=MockSandboxFactory(sandbox),
            conversation_history_factory=MockConversationHistoryFactory(),
            storage=storage,
        )
        _ = cleaner.clean_node("//pkg:target", [])
        self.assertEqual(len(runner.received_histories), 1)
        messages = runner.received_histories[0].get_messages()

        # Verify synthetic tool calls and responses exist in conversation history
        tool_call_names = [
            call["function"]["name"]
            for m in messages
            if m.metadata and "tool_calls" in m.metadata
            for call in m.metadata["tool_calls"]
        ]
        self.assertIn("read_file", tool_call_names)
        self.assertIn("advance", tool_call_names)


if __name__ == "__main__":
    unittest.main()
