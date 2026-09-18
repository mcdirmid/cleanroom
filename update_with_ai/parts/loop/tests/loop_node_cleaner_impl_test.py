"""Unit tests for agent_node_cleaner_impl aligned with grounding specifications."""

import unittest
from pathlib import Path
from typing import List, Optional, Sequence, Set

from update_with_ai.parts.loop.lib.loop_conversation import (
    Conversation,
    Message,
    ModelRequest,
)
from update_with_ai.parts.loop.lib.loop_node_cleaner_impl import (
    NodeCleaner as NodeCleanerImpl,
    CleanedNodes as CleanedNodesImpl,
    __initialize__,
)
from update_with_ai.parts.loop.lib.loop_driver import AgentOutcome, AgentDriver
from update_with_ai.parts.agent.lib.agent_storage import (
    AgentStorage,
    NodeDefinition,
    TaskPrompt,
)
from update_with_ai.parts.loop.lib.loop_node_cleaner import NodeCleaner
from update_with_ai.parts.agent.lib.agent_node_config import CleanedNodes, NodeConfig
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
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    enter_phase,
    get_singleton,
    system,
)
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.sandbox.lib.sandbox import Sandbox, StartupToolExecution
from update_with_ai.parts.sandbox.lib.template_format import TemplateFormatter
from update_with_ai.parts.sandbox.lib.tool_provider import (
    Response,
    WireParameterBindings,
)


def _make_workspace_path(path: str) -> WorkspacePath:
    obj = object.__new__(WorkspacePath)
    object.__setattr__(obj, "path", path)
    return obj


class MockTemplateFormatter:
    tier = agent_session

    def format_template(self, content: str, parameters: dict) -> str:
        lines = content.splitlines()
        out = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("<!-- if:"):
                cond = line[len("<!-- if:") : -len("-->")].strip()
                i += 1
                body = []
                while i < len(lines) and not lines[i].startswith("<!-- endif -->"):
                    body.append(lines[i])
                    i += 1
                i += 1
                if parameters.get(cond):
                    sub = self.format_template("\n".join(body), parameters)
                    if sub:
                        out.append(sub)
                continue
            if line.startswith("<!-- for:"):
                loop_def = line[len("<!-- for:") : -len("-->")].strip()
                var_name, in_col = [x.strip() for x in loop_def.split(" in ")]
                i += 1
                body = []
                while i < len(lines) and not lines[i].startswith("<!-- endfor -->"):
                    body.append(lines[i])
                    i += 1
                i += 1
                items = parameters.get(in_col, [])
                for item in items:
                    ctx = dict(parameters)
                    ctx[var_name] = item
                    sub = self.format_template("\n".join(body), ctx)
                    if sub:
                        out.append(sub)
                continue

            rendered = line
            for k, v in parameters.items():
                if isinstance(v, dict):
                    for sub_k, sub_v in v.items():
                        rendered = rendered.replace(f"<{k}.{sub_k}>", str(sub_v))
                else:
                    rendered = rendered.replace(f"<{k}>", str(v))
            out.append(rendered)
            i += 1
        return "\n".join(out)


class MockStorage:
    tier = system

    def __init__(self) -> None:
        self.definitions: dict[Node, NodeDefinition] = {}
        self.messages: dict[Node, Set[DagMessage]] = {}
        self.dependents: dict[Node, Set[Node]] = {}
        self.dependencies: dict[Node, Set[Dependency]] = {}
        self.registered_dependents: List[Node] = []

    def get_node_definition(self, node: Node) -> Optional[NodeDefinition]:
        return self.definitions.get(node)

    def get_messages(self, node: Node) -> Set[DagMessage]:
        return self.messages.get(node, set())

    def clear_messages(self, node: Node) -> None:
        self.messages[node] = set()

    def add_message(self, message: DagMessage, to: Node) -> None:
        self.messages.setdefault(to, set()).add(message)

    def get_dependents(self, node: Node) -> Set[Node]:
        return self.dependents.get(node, set())

    def get_dependencies(self, node: Node) -> Set[Dependency]:
        return self.dependencies.get(node, set())

    def is_dirty(self, node: Node) -> bool:
        return bool(self.messages.get(node))

    def register_dependent(self, node: Node) -> None:
        self.registered_dependents.append(node)
        for dep in self.get_dependencies(node):
            if not dep.is_silent:
                self.dependents.setdefault(dep.node, set()).add(node)

    def clear_dependents(self, node: Node) -> None:
        pass


class MockSandbox:
    tier = agent_session

    def __init__(self) -> None:
        self.has_modifications = False
        self.templates_materialized = False
        self.startup_executions: List[StartupToolExecution] = []

    def get_startup_tool_executions(self) -> List[StartupToolExecution]:
        return list(self.startup_executions)

    def materialize_startup_templates(self) -> None:
        self.templates_materialized = True


class MockHistory:
    tier = agent_session

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
    tier = agent_session

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
    tier = agent_session

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
        self.blame_targets_by_node: dict[Node, Set[BoundFile]] = {}
        self.verification_checks = []
        self.verification_checks_by_node: dict[Node, list] = {}
        self.src_file_alias_by_node: dict[Node, str] = {}
        self.feedback: List[str] = []

    @property
    def is_step_mode(self) -> bool:
        if self._is_step_mode is not None:
            return self._is_step_mode and self.allows_step_mode
        return False

    @is_step_mode.setter
    def is_step_mode(self, val: bool) -> None:
        self._is_step_mode = val


class LoopNodeCleanerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.storage = MockStorage()
        self.sandbox = MockSandbox()
        self.history = MockHistory()
        self.runner = MockRunner()
        self.node_cfg = MockNodeConfig()
        self.formatter = MockTemplateFormatter()

        self.registry.register_instance(
            self.storage, keys=[AgentStorage], tier=system
        )
        self.registry.register_instance(
            self.sandbox, keys=[Sandbox], tier=agent_session
        )
        self.registry.register_instance(
            self.history, keys=[Conversation], tier=agent_session
        )
        self.registry.register_instance(
            self.runner, keys=[AgentDriver], tier=agent_session
        )
        self.registry.register_instance(
            self.node_cfg, keys=[NodeConfig], tier=agent_session
        )
        self.registry.register_instance(
            self.formatter, keys=[TemplateFormatter], tier=agent_session
        )

    def test_cleaned_node_lifecycle(self) -> None:
        """CUJ: CleanedNodes holds and exposes target nodes in the session tier."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            cleaned_nodes = scope.get_singleton(CleanedNodes)
            with self.assertRaises(RuntimeError):
                _ = cleaned_nodes.nodes

            target1 = Node(unit_address="//pkg:target1")
            target2 = Node(unit_address="//pkg:target2")
            assert isinstance(cleaned_nodes, CleanedNodesImpl)
            # Requirement: The cleaned nodes present the nodes currently being cleaned to session services.
            cleaned_nodes.set_nodes([target1, target2])
            # Requirement: [CleanedNodes] The cleaned nodes present the nodes currently being cleaned in the agent session.
            self.assertEqual(cleaned_nodes.nodes, (target1, target2))

    def test_clean_node_seeds_history_and_materializes_templates(self) -> None:
        """CUJ: Seeding conversation history with task prompt, pending messages, and startup executions."""
        node = Node(unit_address="//pkg:clean_test")
        self.storage.definitions[node] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Clean this node"),
        )
        rw_file = ReadWriteFile(
            relative_path="foo.py",
            workspace_path=_make_workspace_path("/tmp/foo.py"),
            owning_node=node,
        )
        self.node_cfg.read_write_files = {rw_file}
        self.storage.messages[node] = {
            Feedback(content="Z defect explanation"),
            Change(content="A spec updated"),
        }
        startup_exec = StartupToolExecution(
            tool_name="view_file",
            wire_parameter_bindings=WireParameterBindings(
                bindings={("path", "dag_storage.pyi")}
            ),
            response=Response(
                is_failed=False, is_terminated=False, content="spec content"
            ),
        )
        self.sandbox.startup_executions.append(startup_exec)

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: The node cleaner cleans dirty nodes within an agent session phase where the cleaned nodes present the nodes currently being cleaned to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
            msgs = cleaner.clean_nodes([node])

            # Requirement: Within the agent session phase, missing read-write files materialize from sandbox startup templates.
            self.assertTrue(self.sandbox.templates_materialized)
            # Verify history seeded
            # Requirement: The conversation is initialized with startup context comprising the node definition and task prompt retrieved from graph storage for dirty nodes, incoming pending messages ordered deterministically by content and formatted with their message content, and paired startup tool executions from the sandbox formatted with synthetic tool requests and captured responses.
            history_contents = [m.content for m in self.history.messages]
            self.assertTrue(any("Clean this node" in c for c in history_contents))
            # Verify messages are ordered deterministically by content and formatted with their content
            # Requirement: Incoming feedback and change messages are formatted per target node identified by its file alias, prefaced with directives to fix read-write target files based on the feedback.
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
        node = Node(unit_address="//pkg:step_fb_test")
        self.storage.definitions[node] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Clean this node in step mode"),
        )
        rw_file = ReadWriteFile(
            relative_path="foo.py",
            workspace_path=_make_workspace_path("/tmp/foo.py"),
            owning_node=node,
        )
        self.node_cfg.read_write_files = {rw_file}
        self.storage.messages[node] = {
            Feedback(content="Z defect explanation"),
            Change(content="A spec updated"),
            Change(content=""),
        }
        self.node_cfg.is_step_mode = True

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Incoming feedback and change messages are formatted per target node identified by its file alias, prefaced with directives to fix read-write target files based on the feedback.
            _ = cleaner.clean_nodes([node])

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
        node = Node(unit_address="//pkg:change_test")
        self.storage.definitions[node] = NodeDefinition(
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

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Resolving dirty nodes produces change messages for downstream dependent nodes when the outcome signals successful advancement with workspace file modifications, and no change messages or change summaries when no workspace files were modified.
            msgs = cleaner.clean_nodes([node])

            self.assertEqual(len(msgs), 1)
            self.assertIsInstance(list(msgs)[0], Change)

    def test_clean_node_with_blame_produces_feedback_message(self) -> None:
        """CUJ: Producing Feedback message when blame outcome occurs."""
        node = Node(unit_address="//pkg:blame_test")
        self.storage.definitions[node] = NodeDefinition(
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

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Resolving dirty nodes produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
            msgs = cleaner.clean_nodes([node])

            self.assertEqual(len(msgs), 1)
            fb = list(msgs)[0]
            self.assertIsInstance(fb, Feedback)
            assert isinstance(fb, Feedback)
            self.assertEqual(fb.content, "Syntax error in file")
            self.assertEqual(fb.target, Node(unit_address="//pkg:upstream"))

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
            msgs2 = cleaner.clean_nodes([node])
            # Requirement: Resolving dirty nodes produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
            self.assertEqual(len(msgs2), 1)
            fb2 = list(msgs2)[0]
            assert isinstance(fb2, Feedback)
            self.assertEqual(fb2.content, "Blamed //pkg:upstream_no_colon")
            self.assertEqual(fb2.target, Node(unit_address="//pkg:upstream_no_colon"))

            # 3. Matching blame target in blame_targets by relative_path
            bt = ReadOnlyFile(
                relative_path="dep.py",
                workspace_path=_make_workspace_path("pkg/dep.py"),
                owning_node=Node(unit_address="//pkg:target_owning_node"),
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
            msgs3 = cleaner.clean_nodes([node])
            # Requirement: Resolving dirty nodes produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
            self.assertEqual(len(msgs3), 1)
            fb3 = list(msgs3)[0]
            assert isinstance(fb3, Feedback)
            self.assertEqual(fb3.content, "Broken interface contract")
            self.assertEqual(fb3.target, Node(unit_address="//pkg:target_owning_node"))

            # 4. Matching blame target in blame_targets by owning_node.unit_address
            self.runner.outcome = AgentOutcome(
                is_success=True,
                response=Response(
                    is_failed=False,
                    is_terminated=True,
                    content="Blamed //pkg:target_owning_node: Owning node address match",
                ),
                conversation=self.history,
            )
            msgs4 = cleaner.clean_nodes([node])
            # Requirement: Resolving dirty nodes produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
            self.assertEqual(len(msgs4), 1)
            fb4 = list(msgs4)[0]
            assert isinstance(fb4, Feedback)
            self.assertEqual(fb4.content, "Owning node address match")
            self.assertEqual(fb4.target, Node(unit_address="//pkg:target_owning_node"))

            # 5. Matching blame target in blame_targets by owning_node.unit_address#owning_node.role_address
            bt_role = ReadOnlyFile(
                relative_path="role_dep.py",
                workspace_path=_make_workspace_path("pkg/role_dep.py"),
                owning_node=Node(unit_address="//pkg:target_role", role_address="lib"),
            )
            self.node_cfg.blame_targets.add(bt_role)
            self.runner.outcome = AgentOutcome(
                is_success=True,
                response=Response(
                    is_failed=False,
                    is_terminated=True,
                    content="Blamed //pkg:target_role#lib: Owning node role match",
                ),
                conversation=self.history,
            )
            msgs5 = cleaner.clean_nodes([node])
            # Requirement: Resolving dirty nodes produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
            self.assertEqual(len(msgs5), 1)
            fb5 = list(msgs5)[0]
            assert isinstance(fb5, Feedback)
            self.assertEqual(fb5.content, "Owning node role match")
            self.assertEqual(
                fb5.target, Node(unit_address="//pkg:target_role", role_address="lib")
            )

            # 6. Fallback blame parsing when target has # role separator and not in blame_targets
            self.runner.outcome = AgentOutcome(
                is_success=True,
                response=Response(
                    is_failed=False,
                    is_terminated=True,
                    content="Blamed //pkg:fallback_unit#fallback_role: Unmatched role blame",
                ),
                conversation=self.history,
            )
            msgs6 = cleaner.clean_nodes([node])
            # Requirement: Resolving dirty nodes produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
            self.assertEqual(len(msgs6), 1)
            fb6 = list(msgs6)[0]
            assert isinstance(fb6, Feedback)
            self.assertEqual(fb6.content, "Unmatched role blame")
            self.assertEqual(
                fb6.target,
                Node(unit_address="//pkg:fallback_unit", role_address="fallback_role"),
            )

    def test_clean_node_without_modifications_produces_no_messages(self) -> None:
        """CUJ: Producing no messages when cleaning succeeds without workspace file modifications."""
        node = Node(unit_address="//pkg:no_mod")
        self.storage.definitions[node] = NodeDefinition(
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

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            msgs = cleaner.clean_nodes([node])

            # Requirement: Resolving dirty nodes produces change messages for downstream dependent nodes when the outcome signals successful advancement with workspace file modifications, and no change messages or change summaries when no workspace files were modified.
            self.assertEqual(len(msgs), 0)

    def test_clean_node_failure_leaves_node_dirty_and_no_messages(self) -> None:
        """CUJ: Node remains dirty and no messages produced on agent outcome failure."""
        node = Node(unit_address="//pkg:fail_test")
        self.storage.definitions[node] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("Task prompt")
        )
        self.runner.outcome = AgentOutcome(
            is_success=False,
            response=Response(is_failed=True, is_terminated=True, content="Failed"),
            conversation=self.history,
        )

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Resolving dirty nodes produces no propagating messages when the outcome signals run failure, leaving the nodes dirty and communicating that processing cannot continue.
            msgs = cleaner.clean_nodes([node])
            self.assertEqual(len(msgs), 0)

            # Requirement: [NodeCleaner] Cleaning dirty nodes communicates whether processing should continue.
            # Requirement: [NodeCleaner] Processing cannot continue only if a failure occurs while cleaning the nodes that cannot be handled by cleaning any other node.
            cont = cleaner.clean([node])
            self.assertFalse(cont)
            self.assertTrue(self.storage.is_dirty(node))
            self.assertGreater(len(self.storage.get_messages(node)), 0)
            self.assertNotIn(node, self.storage.registered_dependents)

    def test_clean_node_runner_runtime_error_propagates(self) -> None:
        """CUJ: RuntimeError from agent runner propagates through clean_nodes and clean."""
        node = Node(unit_address="//pkg:error_test")
        self.storage.definitions[node] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("Task prompt")
        )
        self.runner.error = RuntimeError("Agent failed: unrecoverable tool error")

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: The node cleaner cleans dirty nodes within an agent session phase where the cleaned nodes present the nodes currently being cleaned to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
            with self.assertRaises(RuntimeError) as ctx:
                cleaner.clean_nodes([node])
            self.assertIn("Agent failed: unrecoverable tool error", str(ctx.exception))

    def test_clean_node_without_task_prompt_resolves_without_runner(self) -> None:
        """CUJ: Cleaning a dirty node defining no task prompt resolves without agent runner and produces change messages when incoming messages indicate change."""
        node = Node(unit_address="//pkg:promptless_change")
        self.storage.definitions[node] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("")
        )
        self.storage.messages[node] = {Change(content="Upstream library updated")}

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: When dirty nodes define no task prompt, cleaning resolves the nodes without establishing an agent session phase, producing change messages for downstream dependent nodes when incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise.
            msgs = cleaner.clean_nodes([node])

            self.assertEqual(len(msgs), 1)
            self.assertIsInstance(list(msgs)[0], Change)
            self.assertEqual(self.runner.run_count, 0)

    def test_clean_node_without_task_prompt_and_no_change_messages_produces_no_messages(
        self,
    ) -> None:
        """CUJ: Cleaning a dirty node defining no task prompt produces no propagating messages when incoming pending messages contain no changes."""
        node = Node(unit_address="//pkg:promptless_no_change")
        self.storage.messages[node] = {Feedback(content="Defect notice")}

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: When dirty nodes define no task prompt, cleaning resolves the nodes without establishing an agent session phase, producing change messages for downstream dependent nodes when incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise.
            msgs = cleaner.clean_nodes([node])

            self.assertEqual(len(msgs), 0)
            self.assertEqual(self.runner.run_count, 0)

    def test_clean_without_task_prompt_delivers_change_to_dependents(self) -> None:
        """CUJ: Clean operation on dirty node with no task prompt delivers Change messages to dependents, clears messages, and registers dependents."""
        node = Node(unit_address="//pkg:promptless_qa")
        dependent = Node(unit_address="//pkg:parent_qa")
        self.storage.dependents[node] = {dependent}
        self.storage.messages[node] = {Change(content="lib updated")}

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: [NodeCleaner] Cleaning dirty nodes communicates whether processing should continue.
            cont = cleaner.clean([node])

            self.assertTrue(cont)
            self.assertEqual(len(self.storage.messages[node]), 0)
            self.assertEqual(len(self.storage.messages[dependent]), 1)
            self.assertIsInstance(list(self.storage.messages[dependent])[0], Change)
            self.assertEqual(self.runner.run_count, 0)

    def test_clean_registers_dependent_to_non_silent_dependencies(self) -> None:
        """CUJ: Clean operation registers node as dependent to immediate non-silent dependencies."""
        node = Node(unit_address="//pkg:clean_target")
        dep_non_silent = Node(unit_address="//pkg:upstream_code")
        dep_silent = Node(unit_address="//pkg:upstream_silent")
        self.storage.dependencies[node] = {
            Dependency(node=dep_non_silent, is_silent=False),
            Dependency(node=dep_silent, is_silent=True),
        }

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Cleaning dirty nodes registers the nodes as dependents to their non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.
            cont = cleaner.clean([node])

            self.assertTrue(cont)
            self.assertIn(node, self.storage.registered_dependents)
            self.assertIn(node, self.storage.get_dependents(dep_non_silent))
            self.assertNotIn(node, self.storage.get_dependents(dep_silent))

    def test_clean_delivers_messages_to_dependents_and_dependencies(self) -> None:
        """CUJ: Clean operation delivers Change messages to dependents and clears prior messages."""
        node = Node(unit_address="//pkg:clean_op")
        self.storage.definitions[node] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("Task prompt")
        )
        dependent = Node(unit_address="//pkg:dependent")
        self.storage.dependents[node] = {dependent}
        self.storage.messages[node] = {Feedback()}
        self.sandbox.has_modifications = True

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: [NodeCleaner] Cleaning dirty nodes communicates whether processing should continue.
            cont = cleaner.clean([node])

            self.assertTrue(cont)
            self.assertEqual(len(self.storage.messages[node]), 0)
            # Requirement: Cleaning dirty nodes registers the nodes as dependents to their non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.
            self.assertEqual(len(self.storage.messages[dependent]), 1)
            self.assertIsInstance(list(self.storage.messages[dependent])[0], Change)

    def test_clean_without_modifications_does_not_deliver_change_messages_to_dependents(
        self,
    ) -> None:
        """CUJ: Clean operation does not deliver Change messages or summaries to dependents when no files modified."""
        node = Node(unit_address="//pkg:clean_op_no_mod")
        self.storage.definitions[node] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("Task prompt")
        )
        dependent = Node(unit_address="//pkg:dependent_no_mod")
        self.storage.dependents[node] = {dependent}
        self.storage.messages[node] = {Feedback()}
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

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Resolving dirty nodes produces change messages for downstream dependent nodes when the outcome signals successful advancement with workspace file modifications, and no change messages or change summaries when no workspace files were modified.
            # Requirement: [NodeCleaner] Cleaning dirty nodes communicates whether processing should continue.
            cont = cleaner.clean([node])

            self.assertTrue(cont)
            self.assertEqual(len(self.storage.messages[node]), 0)
            self.assertEqual(len(self.storage.messages.get(dependent, set())), 0)

    def test_clean_delivers_feedback_to_dependencies(self) -> None:
        """CUJ: Clean operation delivers Feedback messages specifically to addressed dependency."""
        node = Node(unit_address="//pkg:clean_op_feedback")
        self.storage.definitions[node] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("Task prompt")
        )
        dependency1 = Node(unit_address="//pkg:dependency1")
        dependency2 = Node(unit_address="//pkg:dependency2")
        self.storage.dependencies[node] = {
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

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Cleaning dirty nodes registers the nodes as dependents to their non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertEqual(len(self.storage.messages.get(dependency1, set())), 1)
            fb = list(self.storage.messages[dependency1])[0]
            self.assertIsInstance(fb, Feedback)
            assert isinstance(fb, Feedback)
            self.assertEqual(fb.content, "Defect in dep 1")
            self.assertEqual(len(self.storage.messages.get(dependency2, set())), 0)

    def test_clean_node_seeds_history_with_step_mode_guide(self) -> None:
        """CUJ: Seeding conversation history augments task prompt with advance instruction in step mode."""
        node = Node(unit_address="//pkg:step_guide_test")
        self.storage.definitions[node] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Ensure the lib conforms to the guide"),
        )
        self.node_cfg.guide_file = UnboundFile(relative_path="guide.md")
        self.node_cfg.is_step_mode = True

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Task prompt instructions for a guided node include directing the agent to call advance without arguments to view each guide step and omit a change summary until all guide steps are complete when guide step mode is active.
            _ = cleaner.clean_nodes([node])

            history_contents = [m.content for m in self.history.messages]
            prompt_content = next(
                c for c in history_contents if "Ensure the lib conforms" in c
            )
            self.assertIn("advance", prompt_content)
            self.assertIn("change_summary", prompt_content)
            self.assertNotIn("guide.md", prompt_content)

    def test_clean_node_seeds_history_with_non_step_mode_guide(self) -> None:
        """CUJ: Seeding conversation history augments task prompt with guide file alias when not in step mode."""
        node = Node(unit_address="//pkg:nostep_guide_test")
        self.storage.definitions[node] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Ensure the lib conforms to the guide"),
        )
        self.node_cfg.guide_file = UnboundFile(relative_path="my_guide.md")
        self.node_cfg.is_step_mode = False

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Task prompt instructions for a guided node include identifying the guide file by its file alias and directing the agent to call the submit tool with a change summary describing modifications when complete, or call submit without arguments if no workspace files were modified, when guide step mode is inactive.
            _ = cleaner.clean_nodes([node])

            history_contents = [m.content for m in self.history.messages]
            prompt_content = next(
                c for c in history_contents if "Ensure the lib conforms" in c
            )
            self.assertIn("my_guide.md", prompt_content)
            self.assertIn("submit", prompt_content)
            self.assertIn("change summary", prompt_content)
            self.assertIn(
                "call submit without arguments if no workspace files were modified",
                prompt_content,
            )
            self.assertNotIn("advance", prompt_content)

    def test_clean_node_seeds_history_without_guide_leaves_prompt_unaugmented(
        self,
    ) -> None:
        """CUJ: Seeding conversation history leaves task prompt unaugmented when no guide is configured."""
        node = Node(unit_address="//pkg:noguide_test")
        self.storage.definitions[node] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Ensure the lib conforms without guide"),
        )
        self.node_cfg.guide_file = None

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            _ = cleaner.clean_nodes([node])

            history_contents = [m.content for m in self.history.messages]
            prompt_content = next(
                c
                for c in history_contents
                if "Ensure the lib conforms without guide" in c
            )
            self.assertEqual(prompt_content, "Ensure the lib conforms without guide")

    def test_clean_node_seeds_history_guide_from_read_only_files(self) -> None:
        """CUJ: Resolving guide file alias from read-only markdown files when guide_file is None."""
        node = Node(unit_address="//pkg:ro_guide_test")
        self.storage.definitions[node] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Ensure the lib conforms to the guide"),
        )
        self.node_cfg.guide_file = None
        self.node_cfg.read_only_files.add(
            ReadOnlyFile(
                relative_path="ro_guide.md",
                workspace_path=_make_workspace_path("pkg/ro_guide.md"),
                owning_node=node,
            )
        )
        self.node_cfg.is_step_mode = False

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Task prompt instructions for a guided node include identifying the guide file by its file alias and directing the agent to call the submit tool with a change summary describing modifications when complete, or call submit without arguments if no workspace files were modified, when guide step mode is inactive.
            _ = cleaner.clean_nodes([node])

            history_contents = [m.content for m in self.history.messages]
            prompt_content = next(
                c for c in history_contents if "Ensure the lib conforms" in c
            )
            self.assertIn("ro_guide.md", prompt_content)
            self.assertIn("submit", prompt_content)

    def test_clean_node_seeds_history_node_disallows_step_mode(self) -> None:
        """CUJ: When node disallows step mode, model step mode is overridden: feedback is included and guide file is named."""
        node = Node(unit_address="//pkg:disallowed_step_test")
        self.storage.definitions[node] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Ensure the lib conforms to the guide"),
        )
        self.node_cfg.guide_file = UnboundFile(relative_path="qa.md")
        self.node_cfg.allows_step_mode = False
        self.node_cfg.is_step_mode = True
        self.storage.messages[node] = {
            Feedback(content="Fix defect 1"),
        }

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Incoming feedback and change messages are formatted per target node identified by its file alias, prefaced with directives to fix read-write target files based on the feedback.
            # Requirement: Task prompt instructions for a guided node include identifying the guide file by its file alias and directing the agent to call the submit tool with a change summary describing modifications when complete, or call submit without arguments if no workspace files were modified, when guide step mode is inactive.
            _ = cleaner.clean_nodes([node])

            history_contents = [m.content for m in self.history.messages]
            prompt_content = next(
                c for c in history_contents if "Ensure the lib conforms" in c
            )
            self.assertIn("qa.md", prompt_content)
            self.assertIn("submit", prompt_content)
            self.assertIn("change summary", prompt_content)
            self.assertIn(
                "call submit without arguments if no workspace files were modified",
                prompt_content,
            )
            self.assertNotIn("advance", prompt_content)
            self.assertTrue(
                any("feedback: Fix defect 1" in c for c in history_contents)
            )

    def test_clean_node_retries_on_unexpected_execution_failure(self) -> None:
        """CUJ: Retries execution of the agent session phase a second time on unexpected failure."""
        node = Node(unit_address="//pkg:retry_test")
        self.storage.definitions[node] = NodeDefinition(
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

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: The node cleaner cleans dirty nodes within an agent session phase where the cleaned nodes present the nodes currently being cleaned to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
            msgs = cleaner.clean_nodes([node])
            self.assertEqual(attempts, 2)
            self.assertEqual(msgs, set())

    def test_clean_node_propagates_failure_after_two_failed_attempts(self) -> None:
        """CUJ: Propagates unexpected failure after two failed attempts."""
        node = Node(unit_address="//pkg:retry_fail_test")
        self.storage.definitions[node] = NodeDefinition(
            node=node,
            task_prompt=TaskPrompt("Prompt"),
        )
        self.runner.error = RuntimeError("Persistent session failure")

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: The node cleaner cleans dirty nodes within an agent session phase where the cleaned nodes present the nodes currently being cleaned to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
            with self.assertRaises(RuntimeError):
                cleaner.clean_nodes([node])
            self.assertEqual(self.runner.run_count, 2)

    def test_clean_nodes_multi_node_prompt_and_message_formatting(self) -> None:
        """CUJ: Multi-node session formats prompt with file list and formats per-node feedback and change messages."""
        node1 = Node(unit_address="//pkg:unit1")
        node2 = Node(unit_address="//pkg:unit2")
        self.storage.definitions[node1] = NodeDefinition(
            node=node1, task_prompt=TaskPrompt("Prompt for unit 1")
        )
        self.storage.definitions[node2] = NodeDefinition(
            node=node2, task_prompt=TaskPrompt("")
        )
        self.node_cfg.src_file_alias_by_node = {
            node1: "unit1.py",
            node2: "unit2.py",
        }
        self.node_cfg.guide_file = UnboundFile(relative_path="guide.md")
        self.node_cfg.is_step_mode = False
        self.storage.messages[node1] = {
            Change(content=""),
            Change(content="spec 1 updated"),
        }
        self.storage.messages[node2] = {Feedback(content="defect in unit 2")}

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: When cleaning multiple nodes, the task prompt enumerates each target file identified by its file alias alongside its task prompt.
            # Requirement: The task prompt is formatted using the template formatter.
            # Requirement: Incoming feedback and change messages are formatted per target node identified by its file alias, prefaced with directives to fix read-write target files based on the feedback.
            msgs = cleaner.clean_nodes([node1, node2])

            history_contents = [m.content for m in self.history.messages]
            prompt = history_contents[0]
            self.assertIn("Process the following files:", prompt)
            self.assertIn("- `unit1.py`: Prompt for unit 1", prompt)
            self.assertIn("- `unit2.py`", prompt)
            self.assertIn("The guide is in file guide.md. Call submit", prompt)

            self.assertTrue(
                any(
                    "Incoming change for unit1.py: spec 1 updated" in c
                    for c in history_contents
                )
            )
            self.assertTrue(
                any("Incoming change for unit1.py" in c for c in history_contents)
            )
            self.assertTrue(
                any(
                    "Fix unit2.py based on feedback: defect in unit 2" in c
                    for c in history_contents
                )
            )

    def test_clean_multi_node_delivers_changes_to_dependents(self) -> None:
        """CUJ: Multi-node cleaning delivers change messages to dependents of all cleaned nodes."""
        node1 = Node(unit_address="//pkg:unit_a")
        node2 = Node(unit_address="//pkg:unit_b")
        self.storage.definitions[node1] = NodeDefinition(
            node=node1, task_prompt=TaskPrompt("Prompt A")
        )
        self.storage.definitions[node2] = NodeDefinition(
            node=node2, task_prompt=TaskPrompt("Prompt B")
        )
        dep1 = Node(unit_address="//pkg:dep_a")
        dep2 = Node(unit_address="//pkg:dep_b")
        self.storage.dependents[node1] = {dep1}
        self.storage.dependents[node2] = {dep2}
        self.sandbox.has_modifications = True

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Cleaning dirty nodes registers the nodes as dependents to their non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.
            # Requirement: [NodeCleaner] Cleaning dirty nodes communicates whether processing should continue.
            cont = cleaner.clean([node1, node2])
            self.assertTrue(cont)
            self.assertEqual(len(self.storage.messages[dep1]), 1)
            self.assertIsInstance(list(self.storage.messages[dep1])[0], Change)
            self.assertEqual(len(self.storage.messages[dep2]), 1)
            self.assertIsInstance(list(self.storage.messages[dep2])[0], Change)
            self.assertEqual(len(self.storage.messages[node1]), 0)
            self.assertEqual(len(self.storage.messages[node2]), 0)

    def test_clean_multi_node_failure_leaves_all_dirty(self) -> None:
        """CUJ: Multi-node failure leaves all nodes dirty and returns False."""
        node1 = Node(unit_address="//pkg:unit_fail_1")
        node2 = Node(unit_address="//pkg:unit_fail_2")
        self.storage.definitions[node1] = NodeDefinition(
            node=node1, task_prompt=TaskPrompt("Prompt 1")
        )
        self.storage.definitions[node2] = NodeDefinition(
            node=node2, task_prompt=TaskPrompt("Prompt 2")
        )
        self.runner.outcome = AgentOutcome(
            is_success=False,
            response=Response(is_failed=True, is_terminated=True, content="Failed"),
            conversation=self.history,
        )

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: Resolving dirty nodes produces no propagating messages when the outcome signals run failure, leaving the nodes dirty and communicating that processing cannot continue.
            # Requirement: [NodeCleaner] Processing cannot continue only if a failure occurs while cleaning the nodes that cannot be handled by cleaning any other node.
            cont = cleaner.clean([node1, node2])
            self.assertFalse(cont)
            self.assertTrue(self.storage.is_dirty(node1))
            self.assertTrue(self.storage.is_dirty(node2))

    def test_clean_multi_node_without_prompt_delivers_changes(self) -> None:
        """CUJ: Multi-node cleaning when nodes have no task prompt resolves without session phase."""
        node1 = Node(unit_address="//pkg:promptless_1")
        node2 = Node(unit_address="//pkg:promptless_2")
        dep1 = Node(unit_address="//pkg:dep_promptless_1")
        self.storage.dependents[node1] = {dep1}
        self.storage.messages[node1] = {Change(content="lib updated")}

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: When dirty nodes define no task prompt, cleaning resolves the nodes without establishing an agent session phase, producing change messages for downstream dependent nodes when incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise.
            # Requirement: [NodeCleaner] Cleaning dirty nodes communicates whether processing should continue.
            cont = cleaner.clean([node1, node2])
            self.assertTrue(cont)
            self.assertEqual(len(self.storage.messages[dep1]), 1)
            self.assertEqual(self.runner.run_count, 0)

    def test_clean_node_delivers_unaddressed_feedback_to_dependencies(self) -> None:
        """CUJ: Clean operation delivers unaddressed Feedback messages to dependencies."""
        node = Node(unit_address="//pkg:clean_dep_test")
        dep_node = Node(unit_address="//pkg:upstream_dep")
        self.storage.dependencies[node] = {Dependency(node=dep_node)}
        self.storage.definitions[node] = NodeDefinition(
            node=node, task_prompt=TaskPrompt("Prompt")
        )

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            cleaner.clean_nodes = lambda nodes: {
                Feedback(content="generic feedback", target=None)
            }  # type: ignore
            # Requirement: Cleaning dirty nodes registers the nodes as dependents to their non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.
            # Requirement: [NodeCleaner] Cleaning dirty nodes communicates whether processing should continue.
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertIn(dep_node, self.storage.messages)
            msgs = list(self.storage.messages[dep_node])
            self.assertEqual(len(msgs), 1)
            self.assertEqual(msgs[0].content, "generic feedback")


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
