"""Unit tests for agent_node_cleaner_impl aligned with grounding specifications."""

import unittest
from pathlib import Path
from typing import List, Optional, Set

from update_with_ai.parts.agent.lib.agent_conversation import (
    Conversation,
    Message,
    ModelRequest,
)
from update_with_ai.parts.agent.lib.agent_node_cleaner_impl import (
    NodeCleaner as NodeCleanerImpl,
    CleanedNode as CleanedNodeImpl,
    __initialize__,
)
from update_with_ai.parts.agent.lib.agent_driver import AgentOutcome, AgentDriver
from update_with_ai.parts.agent.lib.agent_storage import (
    AgentStorage,
    NodeDefinition,
    TaskPrompt,
)
from update_with_ai.parts.dag.lib.dag_node_cleaner import CleanedNode, NodeCleaner
from update_with_ai.parts.dag.lib.dag_storage import (
    Change,
    Dependency,
    Feedback,
    Message as DagMessage,
    Node,
)
from update_with_ai.parts.agent.lib.agent_file_alias import (
    BoundFile,
    FileContent,
    ReadOnlyFile,
    ReadWriteFile,
    UnboundFile,
    WorkspacePath,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton
from update_with_ai.parts.agent.lib.agent_node_config import NodeConfig
from update_with_ai.parts.sandbox.lib.sandbox import Sandbox, StartupToolExecution
from update_with_ai.parts.sandbox.lib.tool_provider import (
    Response,
    WireParameterBindings,
)


def _make_workspace_path(path: str) -> WorkspacePath:
    obj = object.__new__(WorkspacePath)
    object.__setattr__(obj, "path", path)
    return obj


class MockStorage:
    tier = "system"

    def __init__(self) -> None:
        self.definitions: dict[str, NodeDefinition] = {}
        self.messages: dict[str, Set[DagMessage]] = {}
        self.dependents: dict[str, Set[Node]] = {}
        self.dependencies: dict[str, Set[Dependency]] = {}
        self.registered_dependents: List[Node] = []

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
        self.registered_dependents.append(node)
        for dep in self.get_dependencies(node):
            if not dep.is_silent:
                self.dependents.setdefault(dep.node.address, set()).add(node)

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
        self.tool_responses: List[
            tuple[Response, str, str, Optional[WireParameterBindings]]
        ] = []

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
        self.tool_responses.append(
            (response, tool_name, tool_call_id, wire_parameter_bindings)
        )
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


class MockRunner:
    tier = "agent_session"

    def __init__(self) -> None:
        self.outcome: AgentOutcome = AgentOutcome(
            is_success=True,
            response=Response(is_failed=False, is_terminated=True, content="Done"),
            conversation_history=MockHistory(),
        )
        self.run_count = 0
        self.error: Optional[Exception] = None

    def run(self) -> AgentOutcome:
        self.run_count += 1
        if self.error is not None:
            raise self.error
        return self.outcome


class MockNodeConfig:
    tier = "agent_session"

    def __init__(
        self,
        guide_file: Optional[UnboundFile] = None,
        is_step_mode: Optional[bool] = None,
        allows_step_mode: bool = True,
    ) -> None:
        self.read_only_files: Set[BoundFile] = set()
        self.read_write_files: Set[BoundFile] = set()
        self.guide_file = guide_file
        self._is_step_mode = is_step_mode
        self.allows_step_mode = allows_step_mode
        self.templates: Set[tuple[BoundFile, FileContent]] = set()
        self.guide = None
        self.blame_targets: Set[BoundFile] = set()
        self.verification_checks = []
        self.feedback: List[str] = []

    @property
    def is_step_mode(self) -> bool:
        if self._is_step_mode is not None:
            return self._is_step_mode and self.allows_step_mode
        return False

    @is_step_mode.setter
    def is_step_mode(self, val: bool) -> None:
        self._is_step_mode = val


class AgentNodeCleanerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.storage = MockStorage()
        self.sandbox = MockSandbox()
        self.history = MockHistory()
        self.runner = MockRunner()
        self.node_cfg = MockNodeConfig()

        self.registry.register_instance(
            self.storage, keys=[AgentStorage], tier="system"
        )
        self.registry.register_instance(
            self.sandbox, keys=[Sandbox], tier="agent_session"
        )
        self.registry.register_instance(
            self.history, keys=[Conversation], tier="agent_session"
        )
        self.registry.register_instance(
            self.runner, keys=[AgentDriver], tier="agent_session"
        )
        self.registry.register_instance(
            self.node_cfg, keys=[NodeConfig], tier="agent_session"
        )

    def test_cleaned_node_lifecycle(self) -> None:
        """CUJ: CleanedNode holds and exposes the target node in the session tier."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            cleaned_node = scope.get_singleton(CleanedNode)
            with self.assertRaises(RuntimeError):
                _ = cleaned_node.node

            target = Node(address="//pkg:target")
            assert isinstance(cleaned_node, CleanedNodeImpl)
            # Requirement: The cleaned node presents the node currently being cleaned to session services.
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
        rw_file = ReadWriteFile(
            short_name="foo.py",
            workspace_path=_make_workspace_path("/tmp/foo.py"),
            owning_node=node,
        )
        self.node_cfg.read_write_files = {rw_file}
        self.storage.messages[node.address] = {
            Feedback(content="Z defect explanation"),
            Change(content="A spec updated"),
        }
        startup_exec = StartupToolExecution(
            tool_name="read_file",
            wire_parameter_bindings=WireParameterBindings(
                bindings={("file", "dag_storage.pyi")}
            ),
            response=Response(
                is_failed=False, is_terminated=False, content="spec content"
            ),
        )
        self.sandbox.startup_executions.append(startup_exec)

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: The node cleaner cleans a dirty node within an agent session phase where the cleaned node presents the node currently being cleaned to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
            msgs = cleaner.clean_node(node)

            # Requirement: Within the agent session phase, missing read-write files materialize from sandbox startup templates.
            self.assertTrue(self.sandbox.templates_materialized)
            # Verify history seeded
            # Requirement: The conversation is initialized with startup context comprising the node definition and task prompt retrieved from graph storage for the dirty node, incoming pending messages ordered deterministically by content and formatted with their message content, and paired startup tool executions from the sandbox formatted with synthetic tool requests and captured responses.
            history_contents = [m.content for m in self.history.messages]
            self.assertTrue(any("Clean this node" in c for c in history_contents))
            # Verify messages are ordered deterministically by content and formatted with their content
            # Requirement: Incoming feedback messages are formatted as actionable instructions prefaced with directives to fix read-write target files based on the feedback.
            change_idx = next(
                i
                for i, c in enumerate(history_contents)
                if "Incoming change: A spec updated" in c
            )
            feedback_idx = next(
                i
                for i, c in enumerate(history_contents)
                if "Fix foo.py based on feedback: Z defect explanation" in c
            )
            self.assertLess(change_idx, feedback_idx)
            self.assertTrue(any("spec content" in c for c in history_contents))
            self.assertEqual(
                self.history.tool_responses[0][3], startup_exec.wire_parameter_bindings
            )

    def test_clean_node_formats_feedback_in_prompt_when_feedback_present(self) -> None:
        """CUJ: Incoming feedback messages are formatted into seeded history as actionable instructions."""
        node = Node(address="//pkg:step_fb_test")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Clean this node in step mode"),
        )
        rw_file = ReadWriteFile(
            short_name="foo.py",
            workspace_path=_make_workspace_path("/tmp/foo.py"),
            owning_node=node,
        )
        self.node_cfg.read_write_files = {rw_file}
        self.storage.messages[node.address] = {
            Feedback(content="Z defect explanation"),
            Change(content="A spec updated"),
        }
        self.node_cfg.is_step_mode = True

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Incoming feedback messages are formatted as actionable instructions prefaced with directives to fix read-write target files based on the feedback.
            _ = cleaner.clean_node(node)

            history_contents = [m.content for m in self.history.messages]
            self.assertTrue(
                any("Clean this node in step mode" in c for c in history_contents)
            )
            self.assertTrue(
                any("Incoming change: A spec updated" in c for c in history_contents)
            )
            self.assertTrue(
                any(
                    "Fix foo.py based on feedback: Z defect explanation" in c
                    for c in history_contents
                )
            )

    def test_clean_node_with_modifications_produces_change_message(self) -> None:
        """CUJ: Producing Change message when workspace file modifications occur."""
        node = Node(address="//pkg:change_test")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("Task prompt")
        )
        self.sandbox.has_modifications = True
        self.runner.outcome = AgentOutcome(
            is_success=True,
            response=Response(
                is_failed=False, is_terminated=True, content="Changes applied"
            ),
            conversation=self.history,
        )

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Resolving the dirty node produces change messages for downstream dependent nodes when the outcome signals successful advancement with workspace file modifications, and no change messages or change summaries when no workspace files were modified.
            msgs = cleaner.clean_node(node)

            self.assertEqual(len(msgs), 1)
            self.assertIsInstance(list(msgs)[0], Change)

    def test_clean_node_with_blame_produces_feedback_message(self) -> None:
        """CUJ: Producing Feedback message when blame outcome occurs."""
        node = Node(address="//pkg:blame_test")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("Task prompt")
        )
        self.runner.outcome = AgentOutcome(
            is_success=True,
            response=Response(
                is_failed=False,
                is_terminated=True,
                content="Blamed //pkg:upstream: Syntax error in file",
            ),
            conversation=self.history,
        )

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Resolving the dirty node produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
            msgs = cleaner.clean_node(node)

            self.assertEqual(len(msgs), 1)
            fb = list(msgs)[0]
            self.assertIsInstance(fb, Feedback)
            assert isinstance(fb, Feedback)
            self.assertEqual(fb.content, "Syntax error in file")
            self.assertEqual(fb.target, Node(address="//pkg:upstream"))

            # 2. Blame without colon
            self.runner.outcome = AgentOutcome(
                is_success=True,
                response=Response(
                    is_failed=False,
                    is_terminated=True,
                    content="Blamed //pkg:upstream_no_colon",
                ),
                conversation=self.history,
            )
            msgs2 = cleaner.clean_node(node)
            # Requirement: Resolving the dirty node produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
            self.assertEqual(len(msgs2), 1)
            fb2 = list(msgs2)[0]
            assert isinstance(fb2, Feedback)
            self.assertEqual(fb2.content, "Blamed //pkg:upstream_no_colon")
            self.assertEqual(fb2.target, Node(address="//pkg:upstream_no_colon"))

            # 3. Matching blame target in blame_targets by short_name
            bt = ReadOnlyFile(
                short_name="dep.py",
                workspace_path=_make_workspace_path("pkg/dep.py"),
                owning_node=Node(address="//pkg:target_owning_node"),
            )
            self.node_cfg.blame_targets.add(bt)
            self.runner.outcome = AgentOutcome(
                is_success=True,
                response=Response(
                    is_failed=False,
                    is_terminated=True,
                    content="Blamed dep.py: Broken interface contract",
                ),
                conversation=self.history,
            )
            msgs3 = cleaner.clean_node(node)
            # Requirement: Resolving the dirty node produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
            self.assertEqual(len(msgs3), 1)
            fb3 = list(msgs3)[0]
            assert isinstance(fb3, Feedback)
            self.assertEqual(fb3.content, "Broken interface contract")
            self.assertEqual(fb3.target, Node(address="//pkg:target_owning_node"))

            # 4. Matching blame target in blame_targets by owning_node.address
            self.runner.outcome = AgentOutcome(
                is_success=True,
                response=Response(
                    is_failed=False,
                    is_terminated=True,
                    content="Blamed //pkg:target_owning_node: Owning node address match",
                ),
                conversation=self.history,
            )
            msgs4 = cleaner.clean_node(node)
            # Requirement: Resolving the dirty node produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
            self.assertEqual(len(msgs4), 1)
            fb4 = list(msgs4)[0]
            assert isinstance(fb4, Feedback)
            self.assertEqual(fb4.content, "Owning node address match")
            self.assertEqual(fb4.target, Node(address="//pkg:target_owning_node"))

    def test_clean_node_without_modifications_produces_no_messages(self) -> None:
        """CUJ: Producing no messages when cleaning succeeds without workspace file modifications."""
        node = Node(address="//pkg:no_mod")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("Task prompt")
        )
        self.sandbox.has_modifications = False
        self.runner.outcome = AgentOutcome(
            is_success=True,
            response=Response(
                is_failed=False, is_terminated=True, content="Cleaned without changes"
            ),
            conversation=self.history,
        )

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            msgs = cleaner.clean_node(node)

            # Requirement: Resolving the dirty node produces change messages for downstream dependent nodes when the outcome signals successful advancement with workspace file modifications, and no change messages or change summaries when no workspace files were modified.
            self.assertEqual(len(msgs), 0)

    def test_clean_node_failure_leaves_node_dirty_and_no_messages(self) -> None:
        """CUJ: Node remains dirty and no messages produced on agent outcome failure."""
        node = Node(address="//pkg:fail_test")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("Task prompt")
        )
        self.runner.outcome = AgentOutcome(
            is_success=False,
            response=Response(is_failed=True, is_terminated=True, content="Failed"),
            conversation=self.history,
        )

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Resolving the dirty node produces no propagating messages when the outcome signals run failure, leaving the node dirty and communicating that processing cannot continue.
            msgs = cleaner.clean_node(node)
            self.assertEqual(len(msgs), 0)

            # Requirement: [NodeCleaner] Cleaning a dirty node communicates whether processing should continue.
            # Requirement: [NodeCleaner] Processing cannot continue only if a failure occurs while cleaning the node that cannot be handled by cleaning any other node.
            cont = cleaner.clean(node)
            self.assertFalse(cont)
            self.assertTrue(self.storage.is_dirty(node))
            self.assertGreater(len(self.storage.get_messages(node)), 0)
            self.assertNotIn(node, self.storage.registered_dependents)

    def test_clean_node_runner_runtime_error_propagates(self) -> None:
        """CUJ: RuntimeError from agent runner propagates through clean_node and clean."""
        node = Node(address="//pkg:error_test")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("Task prompt")
        )
        self.runner.error = RuntimeError("Agent failed: unrecoverable tool error")

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: The node cleaner cleans a dirty node within an agent session phase where the cleaned node presents the node currently being cleaned to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
            with self.assertRaises(RuntimeError) as ctx:
                cleaner.clean_node(node)
            self.assertIn("Agent failed: unrecoverable tool error", str(ctx.exception))

    def test_clean_node_without_task_prompt_resolves_without_runner(self) -> None:
        """CUJ: Cleaning a dirty node defining no task prompt resolves without agent runner and produces change messages when incoming messages indicate change."""
        node = Node(address="//pkg:promptless_change")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("")
        )
        self.storage.messages[node.address] = {
            Change(content="Upstream library updated")
        }

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: When a dirty node defines no task prompt, cleaning resolves the node without establishing an agent session phase, producing change messages for downstream dependent nodes when incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise.
            msgs = cleaner.clean_node(node)

            self.assertEqual(len(msgs), 1)
            self.assertIsInstance(list(msgs)[0], Change)
            self.assertEqual(self.runner.run_count, 0)

    def test_clean_node_without_task_prompt_and_no_change_messages_produces_no_messages(
        self,
    ) -> None:
        """CUJ: Cleaning a dirty node defining no task prompt produces no propagating messages when incoming pending messages contain no changes."""
        node = Node(address="//pkg:promptless_no_change")
        # Node has no entry in storage definitions (defines no task prompt)
        self.storage.messages[node.address] = {Feedback(content="Defect notice")}

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: When a dirty node defines no task prompt, cleaning resolves the node without establishing an agent session phase, producing change messages for downstream dependent nodes when incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise.
            msgs = cleaner.clean_node(node)

            self.assertEqual(len(msgs), 0)
            self.assertEqual(self.runner.run_count, 0)

    def test_clean_without_task_prompt_delivers_change_to_dependents(self) -> None:
        """CUJ: Clean operation on dirty node with no task prompt delivers Change messages to dependents, clears messages, and registers dependents."""
        node = Node(address="//pkg:promptless_qa")
        dependent = Node(address="//pkg:parent_qa")
        self.storage.dependents[node.address] = {dependent}
        self.storage.messages[node.address] = {Change(content="lib updated")}

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: [NodeCleaner] Cleaning a dirty node communicates whether processing should continue.
            cont = cleaner.clean(node)

            self.assertTrue(cont)
            self.assertEqual(len(self.storage.messages[node.address]), 0)
            self.assertEqual(len(self.storage.messages[dependent.address]), 1)
            self.assertIsInstance(
                list(self.storage.messages[dependent.address])[0], Change
            )
            self.assertEqual(self.runner.run_count, 0)

    def test_clean_registers_dependent_to_non_silent_dependencies(self) -> None:
        """CUJ: Clean operation registers node as dependent to immediate non-silent dependencies."""
        node = Node(address="//pkg:clean_target")
        dep_non_silent = Node(address="//pkg:upstream_code")
        dep_silent = Node(address="//pkg:upstream_silent")
        self.storage.dependencies[node.address] = {
            Dependency(node=dep_non_silent, is_silent=False),
            Dependency(node=dep_silent, is_silent=True),
        }

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Cleaning a dirty node registers the node as a dependent to its non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.
            cont = cleaner.clean(node)

            self.assertTrue(cont)
            self.assertIn(node, self.storage.registered_dependents)
            self.assertIn(node, self.storage.get_dependents(dep_non_silent))
            self.assertNotIn(node, self.storage.get_dependents(dep_silent))

    def test_clean_delivers_messages_to_dependents_and_dependencies(self) -> None:
        """CUJ: Clean operation delivers Change messages to dependents and clears prior messages."""
        node = Node(address="//pkg:clean_op")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("Task prompt")
        )
        dependent = Node(address="//pkg:dependent")
        self.storage.dependents[node.address] = {dependent}
        self.storage.messages[node.address] = {Feedback()}  # Prior dirty message
        self.sandbox.has_modifications = True

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: [NodeCleaner] Cleaning a dirty node communicates whether processing should continue.
            cont = cleaner.clean(node)

            self.assertTrue(cont)
            # Prior messages on node cleared
            self.assertEqual(len(self.storage.messages[node.address]), 0)
            # Dependent received Change message
            # Requirement: Cleaning a dirty node registers the node as a dependent to its non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.
            self.assertEqual(len(self.storage.messages[dependent.address]), 1)
            self.assertIsInstance(
                list(self.storage.messages[dependent.address])[0], Change
            )

    def test_clean_without_modifications_does_not_deliver_change_messages_to_dependents(
        self,
    ) -> None:
        """CUJ: Clean operation does not deliver Change messages or summaries to dependents when no files modified."""
        node = Node(address="//pkg:clean_op_no_mod")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("Task prompt")
        )
        dependent = Node(address="//pkg:dependent_no_mod")
        self.storage.dependents[node.address] = {dependent}
        self.storage.messages[node.address] = {Feedback()}
        self.sandbox.has_modifications = False
        self.runner.outcome = AgentOutcome(
            is_success=True,
            response=Response(
                is_failed=False,
                is_terminated=True,
                content="Session completed successfully: All tests pass",
            ),
            conversation=self.history,
        )

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Resolving the dirty node produces change messages for downstream dependent nodes when the outcome signals successful advancement with workspace file modifications, and no change messages or change summaries when no workspace files were modified.
            # Requirement: [NodeCleaner] Cleaning a dirty node communicates whether processing should continue.
            cont = cleaner.clean(node)

            self.assertTrue(cont)
            self.assertEqual(len(self.storage.messages[node.address]), 0)
            self.assertEqual(
                len(self.storage.messages.get(dependent.address, set())), 0
            )

    def test_clean_delivers_feedback_to_dependencies(self) -> None:
        """CUJ: Clean operation delivers Feedback messages specifically to addressed dependency."""
        node = Node(address="//pkg:clean_op_feedback")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("Task prompt")
        )
        dependency1 = Node(address="//pkg:dependency1")
        dependency2 = Node(address="//pkg:dependency2")
        self.storage.dependencies[node.address] = {
            Dependency(node=dependency1),
            Dependency(node=dependency2),
        }
        self.runner.outcome = AgentOutcome(
            is_success=True,
            response=Response(
                is_failed=False,
                is_terminated=True,
                content="Blamed //pkg:dependency1: Defect in dep 1",
            ),
            conversation=self.history,
        )

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Cleaning a dirty node registers the node as a dependent to its non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.
            cont = cleaner.clean(node)
            self.assertTrue(cont)
            self.assertEqual(
                len(self.storage.messages.get(dependency1.address, set())), 1
            )
            fb = list(self.storage.messages[dependency1.address])[0]
            self.assertIsInstance(fb, Feedback)
            assert isinstance(fb, Feedback)
            self.assertEqual(fb.content, "Defect in dep 1")
            self.assertEqual(
                len(self.storage.messages.get(dependency2.address, set())), 0
            )

    def test_clean_node_seeds_history_with_step_mode_guide(self) -> None:
        """CUJ: Seeding conversation history augments task prompt with advance instruction in step mode."""
        node = Node(address="//pkg:step_guide_test")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Ensure the lib conforms to the guide"),
        )
        self.node_cfg.guide_file = UnboundFile(short_name="guide.md")
        self.node_cfg.is_step_mode = True

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Task prompt instructions for a guided node include directing the agent to call advance without arguments to view each guide step and omit a change summary until all guide steps are complete when guide step mode is active.
            _ = cleaner.clean_node(node)

            history_contents = [m.content for m in self.history.messages]
            prompt_content = next(
                c for c in history_contents if "Ensure the lib conforms" in c
            )
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
        self.node_cfg.is_step_mode = False

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Task prompt instructions for a guided node include identifying the guide file by its file alias and directing the agent to call the finish tool with a change summary describing modifications when complete, or call finish without arguments if no workspace files were modified, when guide step mode is inactive.
            _ = cleaner.clean_node(node)

            history_contents = [m.content for m in self.history.messages]
            prompt_content = next(
                c for c in history_contents if "Ensure the lib conforms" in c
            )
            self.assertIn("my_guide.md", prompt_content)
            self.assertIn("finish", prompt_content)
            self.assertIn("change summary", prompt_content)
            self.assertIn(
                "call finish without arguments if no workspace files were modified",
                prompt_content,
            )
            self.assertNotIn("advance", prompt_content)

    def test_clean_node_seeds_history_without_guide_leaves_prompt_unaugmented(
        self,
    ) -> None:
        """CUJ: Seeding conversation history leaves task prompt unaugmented when no guide is configured."""
        node = Node(address="//pkg:noguide_test")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Ensure the lib conforms without guide"),
        )
        self.node_cfg.guide_file = None

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            _ = cleaner.clean_node(node)

            history_contents = [m.content for m in self.history.messages]
            prompt_content = next(
                c
                for c in history_contents
                if "Ensure the lib conforms without guide" in c
            )
            self.assertEqual(prompt_content, "Ensure the lib conforms without guide")

    def test_clean_node_seeds_history_guide_from_read_only_files(self) -> None:
        """CUJ: Resolving guide short name from read-only markdown files when guide_file is None."""
        node = Node(address="//pkg:ro_guide_test")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Ensure the lib conforms to the guide"),
        )
        self.node_cfg.guide_file = None
        self.node_cfg.read_only_files.add(
            ReadOnlyFile(
                short_name="ro_guide.md",
                workspace_path=_make_workspace_path("pkg/ro_guide.md"),
                owning_node=node,
            )
        )
        self.node_cfg.is_step_mode = False

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Task prompt instructions for a guided node include identifying the guide file by its file alias and directing the agent to call the finish tool with a change summary describing modifications when complete, or call finish without arguments if no workspace files were modified, when guide step mode is inactive.
            _ = cleaner.clean_node(node)

            history_contents = [m.content for m in self.history.messages]
            prompt_content = next(
                c for c in history_contents if "Ensure the lib conforms" in c
            )
            self.assertIn("ro_guide.md", prompt_content)
            self.assertIn("finish", prompt_content)

    def test_clean_node_seeds_history_node_disallows_step_mode(self) -> None:
        """CUJ: When node disallows step mode, model step mode is overridden: feedback is included and guide file is named."""
        node = Node(address="//pkg:disallowed_step_test")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Ensure the lib conforms to the guide"),
        )
        self.node_cfg.guide_file = UnboundFile(short_name="qa.md")
        self.node_cfg.allows_step_mode = False
        self.node_cfg.is_step_mode = True
        self.storage.messages[node.address] = {
            Feedback(content="Fix defect 1"),
        }

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Incoming feedback messages are formatted as actionable instructions prefaced with directives to fix read-write target files based on the feedback.
            # Requirement: Task prompt instructions for a guided node include identifying the guide file by its file alias and directing the agent to call the finish tool with a change summary describing modifications when complete, or call finish without arguments if no workspace files were modified, when guide step mode is inactive.
            _ = cleaner.clean_node(node)

            history_contents = [m.content for m in self.history.messages]
            prompt_content = next(
                c for c in history_contents if "Ensure the lib conforms" in c
            )
            self.assertIn("qa.md", prompt_content)
            self.assertIn("finish", prompt_content)
            self.assertIn("change summary", prompt_content)
            self.assertIn(
                "call finish without arguments if no workspace files were modified",
                prompt_content,
            )
            self.assertNotIn("advance", prompt_content)
            self.assertTrue(
                any("feedback: Fix defect 1" in c for c in history_contents)
            )

    def test_clean_node_retries_on_unexpected_execution_failure(self) -> None:
        """CUJ: Retries execution of the agent session phase a second time on unexpected failure."""
        node = Node(address="//pkg:retry_test")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Prompt"),
        )
        attempts = 0

        def run_with_retry() -> AgentOutcome:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("Transient session failure")
            return AgentOutcome(
                is_success=True,
                response=Response(is_failed=False, is_terminated=True, content="Done"),
                conversation_history=MockHistory(),
            )

        self.runner.run = run_with_retry

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: The node cleaner cleans a dirty node within an agent session phase where the cleaned node presents the node currently being cleaned to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
            msgs = cleaner.clean_node(node)
            self.assertEqual(attempts, 2)
            self.assertEqual(msgs, set())

    def test_clean_node_propagates_failure_after_two_failed_attempts(self) -> None:
        """CUJ: Propagates unexpected failure after two failed attempts."""
        node = Node(address="//pkg:retry_fail_test")
        self.storage.definitions[node.address] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Prompt"),
        )
        self.runner.error = RuntimeError("Persistent session failure")

        with enter_phase("system", registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: The node cleaner cleans a dirty node within an agent session phase where the cleaned node presents the node currently being cleaned to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
            with self.assertRaises(RuntimeError):
                cleaner.clean_node(node)
            self.assertEqual(self.runner.run_count, 2)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
