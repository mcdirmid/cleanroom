"""Unit tests for agent_node_cleaner_impl aligned with grounding specifications."""

import unittest
from typing import List, Optional, Set

from lib.agent_conversation_history import ConversationHistory, Message, ModelRequest
from lib.agent_node_cleaner import AgentNodeCleaner
from lib.agent_node_cleaner_impl import (
    AgentNodeCleaner as AgentNodeCleanerImpl,
    CleanedNode as CleanedNodeImpl,
    __initialize__,
)
from lib.agent_runner import AgentOutcome, AgentRunner
from lib.bazel_graph_storage import BazelGraphStorage, NodeDefinition, TaskPrompt
from lib.dag_node_cleaner import CleanedNode
from lib.dag_storage import Change, Dependency, Feedback, Message as DagMessage, Node
from lib.file_alias import BoundFile, FileContent, UnboundFile
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from lib.model_config import ModelConfig
from lib.node_config import NodeConfig
from lib.sandbox import Sandbox, StartupToolExecution
from lib.tool_provider import Response, WireParameterBindings


class MockStorage:
    tier = "system"

    def __init__(self) -> None:
        self.definitions: dict[str, NodeDefinition] = {}
        self.messages: dict[str, Set[DagMessage]] = {}
        self.dependents: dict[str, Set[Node]] = {}
        self.dependencies: dict[str, Set[Dependency]] = {}

    def get_node_definition(self, node: Node) -> Optional[NodeDefinition]:
        return self.definitions.get(node.address)

    def get_messages(self, node: Node) -> Set[DagMessage]:
        return self.messages.get(node.address, set())

    def clear_messages(self, node: Node) -> None:
        self.messages[node.address] = set()

    def add_message(self, message: DagMessage, to: Node) -> None:
        self.messages.setdefault(to.address, set()).add(message)

    def get_dependents(self, node: Node) -> Set[Node]:
        return self.dependents.get(node.address, set())

    def get_dependencies(self, node: Node) -> Set[Dependency]:
        return self.dependencies.get(node.address, set())

    def is_dirty(self, node: Node) -> bool:
        return bool(self.messages.get(node.address))

    def register_dependent(self, node: Node) -> None:
        pass

    def clear_dependents(self, node: Node) -> None:
        pass


class MockSandbox:
    tier = "agent_session"

    def __init__(self) -> None:
        self.has_modifications = False
        self.templates_materialized = False
        self.startup_executions: List[StartupToolExecution] = []

    def get_startup_tool_executions(self) -> List[StartupToolExecution]:
        return list(self.startup_executions)

    def materialize_startup_templates(self) -> None:
        self.templates_materialized = True


class MockHistory:
    tier = "agent_session"

    def __init__(self) -> None:
        self._messages: List[Message] = []
        self.tool_responses: List[tuple[Response, str, str, Optional[WireParameterBindings]]] = []

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
        self.tool_responses.append((response, tool_name, tool_call_id, wire_parameter_bindings))
        self._messages.append(
            Message(role="tool", content=response.content, tool_call_id=tool_call_id, tool_name=tool_name)
        )

    def get_model_request(self) -> ModelRequest:
        return ModelRequest(messages=list(self._messages))


class MockRunner:
    tier = "agent_session"

    def __init__(self) -> None:
        self.outcome: AgentOutcome = AgentOutcome(
            is_success=True,
            response=Response(is_failed=False, is_terminated=True, content="Done"),
            conversation_history=MockHistory(),
        )

    def run(self) -> AgentOutcome:
        return self.outcome


class MockModelConfig:
    tier = "system"

    def __init__(self, is_step_mode: bool = False) -> None:
        self.is_step_mode = is_step_mode
        self.model_name = "test-model"
        self.base_url = None
        self.api_key = None
        self.timeout = 60
        self.conversation_limit = 100
        self.temperature = 0.0
        self.max_tokens = None
        self.is_startup_reads = True


class MockNodeConfig:
    tier = "agent_session"

    def __init__(self, guide_file: Optional[UnboundFile] = None) -> None:
        self.read_only_files: Set[BoundFile] = set()
        self.read_write_files: Set[BoundFile] = set()
        self.guide_file = guide_file
        self.templates: Set[tuple[BoundFile, FileContent]] = set()
        self.guide = None
        self.blame_targets: Set[BoundFile] = set()
        self.verification_checks = []


class AgentNodeCleanerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.storage = MockStorage()
        self.sandbox = MockSandbox()
        self.history = MockHistory()
        self.runner = MockRunner()
        self.node_cfg = MockNodeConfig()
        self.model_cfg = MockModelConfig()

        self.registry.register_instance(self.storage, keys=[BazelGraphStorage], tier="system")
        self.registry.register_instance(self.sandbox, keys=[Sandbox], tier="agent_session")
        self.registry.register_instance(self.history, keys=[ConversationHistory], tier="agent_session")
        self.registry.register_instance(self.runner, keys=[AgentRunner], tier="agent_session")
        self.registry.register_instance(self.node_cfg, keys=[NodeConfig], tier="agent_session")
        self.registry.register_instance(self.model_cfg, keys=[ModelConfig], tier="system")

    def test_cleaned_node_lifecycle(self) -> None:
        """CUJ: CleanedNode holds and exposes the target node in the session tier."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            cleaned_node = scope.get_singleton(CleanedNode)
            with self.assertRaises(RuntimeError):
                _ = cleaned_node.node

            target = Node(address="//pkg:target")
            assert isinstance(cleaned_node, CleanedNodeImpl)
            # Requirement: The cleaned node is configured with the node currently being cleaned within the agent session phase.
            cleaned_node.set_node(target)
            # Requirement: [CleanedNode] The cleaned node presents the node currently being cleaned in the agent session.
            self.assertEqual(cleaned_node.node, target)

    def test_clean_node_seeds_history_and_materializes_templates(self) -> None:
        """CUJ: Seeding conversation history with task prompt, pending messages, and startup executions."""
        node = Node(address="//pkg:clean_test")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Clean this node"),
        )
        self.storage.messages[node.address] = {Feedback(), Change()}
        startup_exec = StartupToolExecution(
            tool_name="read_file",
            wire_parameter_bindings=WireParameterBindings(bindings={("file", "dag_storage.pyi")}),
            response=Response(is_failed=False, is_terminated=False, content="spec content"),
        )
        self.sandbox.startup_executions.append(startup_exec)

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(AgentNodeCleaner)
            # Requirement: [AgentNodeCleaner] An agent node cleaner cleans a dirty node within an agent session phase.
            # Requirement: Node cleaning executes within an agent session phase, configuring the cleaned node with the dirty node.
            # Requirement: Node cleaning executes an agent runner with the sandbox and conversation history.
            msgs = cleaner.clean_node(node)

            # Requirement: Startup templates from the sandbox are materialized for missing read-write files.
            self.assertTrue(self.sandbox.templates_materialized)
            # Verify history seeded
            # Requirement: The conversation history is seeded with the task prompt, node definition, incoming pending messages ordered deterministically by content, and paired startup tool executions from the sandbox.
            history_contents = [m.content for m in self.history.messages]
            self.assertTrue(any("Clean this node" in c for c in history_contents))
            # Verify messages are ordered deterministically by content: "Change" before "Feedback"
            change_idx = next(i for i, c in enumerate(history_contents) if "Incoming message: Change" in c)
            feedback_idx = next(i for i, c in enumerate(history_contents) if "Incoming message: Feedback" in c)
            self.assertLess(change_idx, feedback_idx)
            self.assertTrue(any("spec content" in c for c in history_contents))
            self.assertEqual(self.history.tool_responses[0][3], startup_exec.wire_parameter_bindings)

    def test_clean_node_with_file_modifications_produces_change_message(self) -> None:
        """CUJ: Producing Change message when run succeeds with file modifications."""
        node = Node(address="//pkg:mod_test")
        self.sandbox.has_modifications = True
        self.runner.outcome = AgentOutcome(
            is_success=True,
            response=Response(is_failed=False, is_terminated=True, content="Changes applied"),
            conversation_history=self.history,
        )

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(AgentNodeCleaner)
            # Requirement: When the agent outcome indicates change with workspace file modifications, change messages are produced for downstream dependent nodes.
            # Requirement: [AgentNodeCleaner] When workspace file modifications occur and task verification passes, the agent node cleaner produces change messages.
            msgs = cleaner.clean_node(node)

            self.assertEqual(len(msgs), 1)
            self.assertIsInstance(list(msgs)[0], Change)

    def test_clean_node_with_blame_produces_feedback_message(self) -> None:
        """CUJ: Producing Feedback message when blame outcome occurs."""
        node = Node(address="//pkg:blame_test")
        self.runner.outcome = AgentOutcome(
            is_success=True,
            response=Response(is_failed=False, is_terminated=True, content="Blamed //pkg:upstream"),
            conversation_history=self.history,
        )

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(AgentNodeCleaner)
            # Requirement: When the agent outcome indicates blame, feedback messages are produced for the blamed dependency node.
            # Requirement: [AgentNodeCleaner] When blame is signaled, the agent node cleaner produces feedback messages addressed to dependency nodes.
            msgs = cleaner.clean_node(node)

            self.assertEqual(len(msgs), 1)
            self.assertIsInstance(list(msgs)[0], Feedback)

    def test_clean_node_without_modifications_produces_no_messages(self) -> None:
        """CUJ: Producing no messages when cleaning succeeds without workspace file modifications."""
        node = Node(address="//pkg:no_mod")
        self.sandbox.has_modifications = False
        self.runner.outcome = AgentOutcome(
            is_success=True,
            response=Response(is_failed=False, is_terminated=True, content="Cleaned without changes"),
            conversation_history=self.history,
        )

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(AgentNodeCleaner)
            msgs = cleaner.clean_node(node)

            # Requirement: [AgentNodeCleaner] When cleaning succeeds without workspace file modifications, no messages are produced.
            self.assertEqual(len(msgs), 0)

    def test_clean_node_failure_leaves_node_dirty_and_no_messages(self) -> None:
        """CUJ: Node remains dirty and no messages produced on agent outcome failure."""
        node = Node(address="//pkg:fail_test")
        self.runner.outcome = AgentOutcome(
            is_success=False,
            response=Response(is_failed=True, is_terminated=True, content="Failed"),
            conversation_history=self.history,
        )

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(AgentNodeCleaner)
            # Requirement: When the agent outcome indicates failure, the node remains dirty and no propagating messages are produced.
            msgs = cleaner.clean_node(node)
            self.assertEqual(len(msgs), 0)

            # Requirement: [NodeCleaner] Cleaning a dirty node communicates whether processing should continue.
            # Requirement: [NodeCleaner] Processing cannot continue only if a failure occurs while cleaning the node that cannot be handled by cleaning any other node.
            cont = cleaner.clean(node)
            self.assertFalse(cont)
            self.assertTrue(self.storage.is_dirty(node))
            self.assertGreater(len(self.storage.get_messages(node)), 0)

    def test_clean_delivers_messages_to_dependents_and_dependencies(self) -> None:
        """CUJ: Clean operation delivers Change messages to dependents and clears prior messages."""
        node = Node(address="//pkg:clean_op")
        dependent = Node(address="//pkg:dependent")
        self.storage.dependents[node.address] = {dependent}
        self.storage.messages[node.address] = {Feedback()}  # Prior dirty message
        self.sandbox.has_modifications = True

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(AgentNodeCleaner)
            # Requirement: [NodeCleaner] Cleaning a dirty node communicates whether processing should continue.
            cont = cleaner.clean(node)

            self.assertTrue(cont)
            # Prior messages on node cleared
            # Requirement: [NodeCleaner] When cleaning a dirty node, a node cleaner interacts with dag storage to deliver messages and manages whether the node remains dirty.
            self.assertEqual(len(self.storage.messages[node.address]), 0)
            # Dependent received Change message
            # Requirement: [NodeCleaner] Delivering messages delivers change messages to dependents when modifications are made, or feedback messages to dependencies when defects require revision.
            self.assertEqual(len(self.storage.messages[dependent.address]), 1)
            self.assertIsInstance(list(self.storage.messages[dependent.address])[0], Change)

    def test_clean_delivers_feedback_to_dependencies(self) -> None:
        """CUJ: Clean operation delivers Feedback messages to dependencies."""
        node = Node(address="//pkg:clean_op_feedback")
        dependency = Node(address="//pkg:dependency")
        self.storage.dependencies[node.address] = {Dependency(node=dependency)}
        self.runner.outcome = AgentOutcome(
            is_success=True,
            response=Response(is_failed=False, is_terminated=True, content="Blamed //pkg:dependency"),
            conversation_history=self.history,
        )

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(AgentNodeCleaner)
            cont = cleaner.clean(node)
            self.assertTrue(cont)
            self.assertEqual(len(self.storage.messages[dependency.address]), 1)
            self.assertIsInstance(list(self.storage.messages[dependency.address])[0], Feedback)

    def test_clean_node_seeds_history_with_step_mode_guide(self) -> None:
        """CUJ: Seeding conversation history augments task prompt with advance instruction in step mode."""
        node = Node(address="//pkg:step_guide_test")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Ensure the lib conforms to the guide"),
        )
        self.node_cfg.guide_file = UnboundFile(short_name="guide.md")
        self.model_cfg.is_step_mode = True

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(AgentNodeCleaner)
            # Requirement: When seeding conversation history with a task prompt for a node configured with a guide, the prompt is augmented with instructions directing the agent to call advance without arguments to view each guide step and not supply a change summary until all guide steps are complete when progressive guidance is active, or identifying the guide file by its file alias when progressive guidance is inactive.
            _ = cleaner.clean_node(node)

            history_contents = [m.content for m in self.history.messages]
            prompt_content = next(c for c in history_contents if "Ensure the lib conforms" in c)
            self.assertIn("advance", prompt_content)
            self.assertIn("change_summary", prompt_content)
            self.assertNotIn("guide.md", prompt_content)

    def test_clean_node_seeds_history_with_non_step_mode_guide(self) -> None:
        """CUJ: Seeding conversation history augments task prompt with guide file alias when not in step mode."""
        node = Node(address="//pkg:nostep_guide_test")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Ensure the lib conforms to the guide"),
        )
        self.node_cfg.guide_file = UnboundFile(short_name="my_guide.md")
        self.model_cfg.is_step_mode = False

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(AgentNodeCleaner)
            # Requirement: When seeding conversation history with a task prompt for a node configured with a guide, the prompt is augmented with instructions directing the agent to call advance without arguments to view each guide step and not supply a change summary until all guide steps are complete when progressive guidance is active, or identifying the guide file by its file alias when progressive guidance is inactive.
            _ = cleaner.clean_node(node)

            history_contents = [m.content for m in self.history.messages]
            prompt_content = next(c for c in history_contents if "Ensure the lib conforms" in c)
            self.assertIn("my_guide.md", prompt_content)
            self.assertNotIn("advance", prompt_content)

    def test_clean_node_seeds_history_without_guide_leaves_prompt_unaugmented(self) -> None:
        """CUJ: Seeding conversation history leaves task prompt unaugmented when no guide is configured."""
        node = Node(address="//pkg:noguide_test")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Ensure the lib conforms without guide"),
        )
        self.node_cfg.guide_file = None

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(AgentNodeCleaner)
            _ = cleaner.clean_node(node)

            history_contents = [m.content for m in self.history.messages]
            prompt_content = next(c for c in history_contents if "Ensure the lib conforms without guide" in c)
            self.assertEqual(prompt_content, "Ensure the lib conforms without guide")


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None

