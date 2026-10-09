# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:46:18Z
# LAST_CHANGED: 2026-10-09T22:20:00Z
# CHANGE: Verify role configuration on role config without pre-priming nodes during session setup
# CODE_HASH: 3c8df6108608
# QA_AUDIT: 2026-10-09T21:46:18Z
# --- END CLEANROOM METADATA ---

"""Unit tests for loop_node_cleaner_impl aligned with grounding specifications."""

from dataclasses import dataclass
import unittest
from typing import Any, List, Optional, Sequence, Set, cast

from update_with_ai.parts.agent.lib.agent_node_config import (
    NodeConfig,
    RoleConfig,
    RoleName,
)
from update_with_ai.parts.agent.lib.agent_storage import (
    AgentStorage,
    NodeDefinition,
    TaskPrompt,
)
from update_with_ai.parts.core.lib import runner_logger
from update_with_ai.parts.dag.lib.dag_storage import (
    ChangeMessage,
    DagDependency,
    DagMessage,
    DagNode,
    FeedbackMessage,
    MessageContent,
    RoleAddress,
    UnitAddress,
)
from update_with_ai.parts.loop.lib.loop_conversation import (
    Conversation,
    ConversationContent,
    ConversationMessage,
    MessageRole,
    ModelRequest,
    ToolCallId,
)
from update_with_ai.parts.loop.lib.loop_driver import LoopDriver, LoopOutcome
from update_with_ai.parts.loop.lib.loop_node_cleaner import NodeCleaner
from update_with_ai.parts.loop.lib.loop_node_cleaner_impl import (
    NodeCleaner as NodeCleanerImpl,
    __initialize__,
)
from update_with_ai.parts.sandbox.lib.sandbox import Sandbox
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system


@dataclass(frozen=True)
class MockBoundFile:
    relative_path: str
    owning_node: Optional[DagNode] = None


@dataclass
class MockResponse:
    content: str = ""
    is_failed: bool = False
    is_terminated: bool = True


def _make_dag_node(unit_address: str, role_address: str = "lib") -> DagNode:
    return DagNode(
        unit_address=UnitAddress(unit_address), role_address=RoleAddress(role_address)
    )


def _make_change(content: str) -> DagMessage:
    return cast(DagMessage, ChangeMessage(content=MessageContent(content)))


class MockStorage:
    tier = system

    def __init__(self) -> None:
        self.definitions: dict[DagNode, NodeDefinition] = {}
        self.messages: dict[DagNode, Set[DagMessage]] = {}
        self.dependencies: dict[DagNode, Set[DagDependency]] = {}

    def get_node_definition(self, node: DagNode) -> Optional[NodeDefinition]:
        return self.definitions.get(node)

    def get_messages(self, node: DagNode) -> Set[DagMessage]:
        return self.messages.get(node, set())

    def clear_messages(self, node: DagNode) -> None:
        self.messages[node] = set()

    def add_message(self, message: DagMessage, to: DagNode) -> None:
        self.messages.setdefault(to, set()).add(message)

    def get_dependencies(self, node: DagNode) -> Set[DagDependency]:
        return self.dependencies.get(node, set())

    def is_dirty(self, node: DagNode) -> bool:
        return bool(self.messages.get(node))


class MockSandbox:
    tier = "agent_session"

    def __init__(self) -> None:
        self.has_modifications = False
        self.templates_materialized = False

    def materialize_startup_templates(self) -> None:
        self.templates_materialized = True


class MockConversation:
    tier = "agent_session"

    def __init__(self) -> None:
        self._messages: List[ConversationMessage] = []

    def initialize(self, initial_messages: Sequence[ConversationMessage] = ()) -> None:
        self._messages = list(initial_messages)

    def append_message(self, message: ConversationMessage) -> None:
        self._messages.append(message)

    def append_tool_response(
        self,
        tool_response: Any,
        tool_call_id: str,
        tool_name: str,
        tool_arguments: str,
    ) -> None:
        self._messages.append(
            ConversationMessage(
                role=MessageRole("tool"),
                content=ConversationContent(str(getattr(tool_response, "content", ""))),
                tool_call_id=ToolCallId(tool_call_id) if tool_call_id else None,
                tool_name=cast(Any, tool_name) if tool_name else None,
            )
        )

    def get_model_request(self) -> ModelRequest:
        return ModelRequest(messages=list(self._messages))


class MockRunner:
    tier = "agent_session"

    def __init__(self) -> None:
        self.outcome = LoopOutcome(
            response=cast(Any, MockResponse(
                is_failed=False, is_terminated=True, content="Done"
            )),
            conversation=ModelRequest(messages=[]),
        )
        self.run_count = 0
        self.error: Optional[Exception] = None
        self.inspect_role: bool = False
        self.captured_role: Optional[str] = None
        self.captured_nodes: Optional[Sequence[Any]] = None
        self.captured_custom_role: Optional[str] = None

    def run(self) -> LoopOutcome:
        self.run_count += 1
        if self.error is not None:
            raise self.error
        if self.inspect_role:
            from support.lib.lifecycle import get_singleton

            role_cfg = get_singleton(RoleConfig)
            self.captured_role = str(role_cfg.role)
            self.captured_nodes = list(role_cfg.nodes)
            role_cfg.set_role(RoleName("custom_role"))
            self.captured_custom_role = str(role_cfg.role)
        return self.outcome


class MockNodeConfig:
    tier = "agent_session"

    def __init__(self) -> None:
        self.read_only_files: Set[Any] = set()
        self.read_write_files: Set[Any] = set()
        self.guide_file: Optional[Any] = None
        self.allows_step_mode: bool = True
        self.is_step_mode: bool = False
        self.templates: Set[tuple[Any, Any]] = set()
        self.template_parameters: dict = {}
        self.guide = None
        self.blame_targets_by_node: dict[DagNode, Set[Any]] = {}
        self.verification_checks: Sequence = []
        self.verification_checks_by_node: dict[DagNode, list] = {}
        self.src_file_alias_by_node: dict[DagNode, str] = {}
        self.verification_success_message: Optional[str] = None
        self.feedback: Sequence[str] = []
        self.per_node_info_by_node: dict = {}


class MockLogger:
    tier = system

    def __init__(self) -> None:
        self.events: List[runner_logger.RunnerLogEvent] = []

    def consume(self, event: runner_logger.RunnerLogEvent) -> None:
        self.events.append(event)


class LoopNodeCleanerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.storage = MockStorage()
        self.sandbox = MockSandbox()
        self.history = MockConversation()
        self.runner = MockRunner()
        self.node_cfg = MockNodeConfig()
        self.logger = MockLogger()

        self.registry.register_instance(
            self.logger, keys=[runner_logger.RunnerLogger], tier=system
        )
        self.registry.register_instance(self.storage, keys=[AgentStorage], tier=system)
        self.registry.register_instance(
            self.sandbox, keys=[Sandbox], tier="agent_session"
        )
        self.registry.register_instance(
            self.history, keys=[Conversation], tier="agent_session"
        )
        self.registry.register_instance(
            self.runner, keys=[LoopDriver], tier="agent_session"
        )
        self.registry.register_instance(
            self.node_cfg, keys=[NodeConfig], tier="agent_session"
        )

    def test_clean_advancement_delivers_changes(self) -> None:
        """CUJ: Successful session advancement with modifications clears messages on cleaned node."""
        node = _make_dag_node("//pkg:unit", "lib")
        self.storage.definitions[node] = NodeDefinition(
            task_prompt=TaskPrompt("Prompt")
        )
        self.storage.messages[node] = {_make_change("dirty")}
        self.sandbox.has_modifications = True

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: MUST clean dirty nodes within an agent session phase presenting the node role.
            # Requirement: MUST clean dirty nodes sharing a role.
            # Requirement: MUST communicate whether processing should continue.
            # Requirement: WHEN the outcome signals advancement with file modifications, MUST mark the nodes clean in graph storage with the change summary.
            # Requirement: WHEN cleaning completes without unhandleable failure, MUST return true.
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertEqual(self.storage.messages.get(node, set()), set())

    def test_clean_blame_delivers_feedback(self) -> None:
        """CUJ: Session outcome signaling blame delivers feedback message to blamed dependency."""
        node = _make_dag_node("//pkg:unit", "lib")
        dep_blamed = _make_dag_node("//pkg:dep_blamed", "lib")
        bf = MockBoundFile(
            relative_path="dep_blamed.py",
            owning_node=dep_blamed,
        )
        self.node_cfg.blame_targets_by_node = {node: {bf}}
        self.storage.definitions[node] = NodeDefinition(
            task_prompt=TaskPrompt("Prompt")
        )
        self.storage.dependencies[node] = {DagDependency(node=dep_blamed)}
        self.storage.messages[node] = {_make_change("dirty")}
        self.runner.outcome = LoopOutcome(
            response=cast(Any, MockResponse(
                is_failed=False,
                is_terminated=True,
                content="Blamed //pkg:dep_blamed: Broken API",
            )),
            conversation=ModelRequest(messages=[]),
        )

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: WHEN the outcome signals blame attributed to a configured blame target, MUST deliver feedback messages strictly to the declared feedback dependency node owning the blamed file.
            # Requirement: WHEN cleaning completes without unhandleable failure, MUST return true.
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertIn(dep_blamed, self.storage.messages)
            msgs = list(self.storage.messages[dep_blamed])
            self.assertEqual(len(msgs), 1)
            self.assertIsInstance(msgs[0], FeedbackMessage)
            assert isinstance(msgs[0], FeedbackMessage)
            self.assertEqual(msgs[0].content, "Broken API")

    def test_clean_run_failure_leaves_nodes_dirty(self) -> None:
        """CUJ: Outcome signaling run failure leaves nodes dirty and returns False."""
        node = _make_dag_node("//pkg:fail_unit", "lib")
        self.storage.definitions[node] = NodeDefinition(
            task_prompt=TaskPrompt("Prompt")
        )
        self.storage.messages[node] = {_make_change("dirty")}
        self.runner.outcome = LoopOutcome(
            response=cast(Any, MockResponse(
                is_failed=True,
                is_terminated=True,
                content="Fatal tool failure",
            )),
            conversation=ModelRequest(messages=[]),
        )

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: WHEN the outcome signals run failure, MUST leave nodes dirty and return false.
            # Requirement: WHEN an unhandleable failure occurs while cleaning, MUST return false.
            cont = cleaner.clean([node])
            self.assertFalse(cont)
            self.assertTrue(self.storage.is_dirty(node))

    def test_clean_promptless_nodes_resolves_without_session(self) -> None:
        """CUJ: Dirty nodes without task prompt resolve pass-through changes without session phase."""
        node = _make_dag_node("//pkg:pass_thru", "lib")
        self.storage.messages[node] = {_make_change("upstream change")}

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: WHEN dirty nodes define no task prompt, MUST resolve pass-through changes without establishing an agent session.
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertEqual(self.runner.run_count, 0)
            self.assertEqual(self.storage.messages.get(node, set()), set())

    def test_clean_retries_on_unexpected_failure(self) -> None:
        """CUJ: Retries session phase once upon encountering unexpected failure before propagating."""
        node = _make_dag_node("//pkg:retry_unit", "lib")
        self.storage.definitions[node] = NodeDefinition(
            task_prompt=TaskPrompt("Prompt")
        )
        self.storage.messages[node] = {_make_change("dirty")}

        attempts = 0

        def run_flaky() -> LoopOutcome:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("Transient crash")
            return LoopOutcome(
                response=cast(Any, MockResponse(
                    is_failed=False,
                    is_terminated=True,
                    content="Success",
                )),
                conversation=ModelRequest(messages=[]),
            )

        self.runner.run = run_flaky

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: MUST retry the session phase once upon encountering an unexpected failure before propagating.
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertEqual(attempts, 2)

    def test_clean_blame_parsing_formats(self) -> None:
        """CUJ: Extracting target and explanation from blame responses with backticks, colons, or package prefixes."""
        node = _make_dag_node("//pkg:unit", "lib")
        dep_blamed = _make_dag_node("//pkg:dep_blamed", "lib")
        bf = MockBoundFile(
            relative_path="dep_blamed.py",
            owning_node=dep_blamed,
        )
        self.node_cfg.blame_targets_by_node = {node: {bf}}
        self.storage.definitions[node] = NodeDefinition(
            task_prompt=TaskPrompt("Prompt")
        )
        self.storage.dependencies[node] = {DagDependency(node=dep_blamed)}
        self.storage.messages[node] = {_make_change("dirty")}

        blame_formats = [
            "Blamed `//pkg:dep_blamed`: Spec contract defect",
            "Blamed `dep_blamed.py`: Method signature mismatch",
            "Blamed //pkg:dep_blamed: Error: invalid argument",
            "Blamed //pkg/sub/dir:dep_blamed: Upstream defect",
        ]

        for fmt in blame_formats:
            self.storage.messages[dep_blamed] = set()
            self.runner.outcome = LoopOutcome(
                response=cast(Any, MockResponse(
                    is_failed=False,
                    is_terminated=True,
                    content=fmt,
                )),
                conversation=ModelRequest(messages=[]),
            )
            with enter_phase(system, registry=self.registry) as scope:
                cleaner = scope.get_singleton(NodeCleanerImpl)
                cont = cleaner.clean([node])
                self.assertTrue(cont)
                self.assertIn(dep_blamed, self.storage.messages)

    def test_clean_blame_unconfigured_target_leaves_nodes_dirty_and_no_propagating_messages(
        self,
    ) -> None:
        """CUJ: Outcome signaling blame for unconfigured target produces no propagating messages and leaves nodes dirty."""
        node = _make_dag_node("//pkg:unit", "lib")
        dep_guide = _make_dag_node("//pkg:dep_guide", "lib")
        self.storage.definitions[node] = NodeDefinition(
            task_prompt=TaskPrompt("Prompt")
        )
        self.storage.dependencies[node] = {DagDependency(node=dep_guide)}
        self.storage.messages[node] = {_make_change("dirty")}
        self.node_cfg.blame_targets_by_node = {node: set()}
        self.runner.outcome = LoopOutcome(
            response=cast(Any, MockResponse(
                is_failed=False,
                is_terminated=True,
                content="Blamed //pkg:unknown_target: Unconfigured blame error",
            )),
            conversation=ModelRequest(messages=[]),
        )

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: WHEN the outcome signals blame attributed to a target failing to match a configured blame target, MUST produce no propagating messages and leave nodes dirty.
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertTrue(self.storage.is_dirty(node))
            self.assertEqual(len(self.storage.get_messages(dep_guide)), 0)

    def test_clean_blame_never_delivered_to_non_feedback_dependencies(self) -> None:
        """CUJ: Blame feedback is strictly delivered to declared feedback dependencies and never non-feedback dependencies."""
        node = _make_dag_node("//pkg:unit", "lib")
        dep_feedback = _make_dag_node("//pkg:feedback_dep", "lib")
        dep_non_feedback = _make_dag_node("//pkg:guide_dep", "lib")
        bf = MockBoundFile(
            relative_path="feedback_dep.py",
            owning_node=dep_feedback,
        )
        self.node_cfg.blame_targets_by_node = {node: {bf}}
        self.storage.definitions[node] = NodeDefinition(
            task_prompt=TaskPrompt("Prompt")
        )
        self.storage.dependencies[node] = {
            DagDependency(node=dep_feedback),
            DagDependency(node=dep_non_feedback),
        }
        self.storage.messages[node] = {_make_change("dirty")}
        self.runner.outcome = LoopOutcome(
            response=cast(Any, MockResponse(
                is_failed=False,
                is_terminated=True,
                content="Blamed //pkg:feedback_dep: Contract violation",
            )),
            conversation=ModelRequest(messages=[]),
        )

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: MUST NOT deliver feedback messages to non-feedback dependencies, guides, or fixed node specifications.
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertIn(dep_feedback, self.storage.messages)
            self.assertEqual(len(self.storage.get_messages(dep_non_feedback)), 0)

    def test_clean_unhandleable_failure_retries_exhausted(self) -> None:
        """CUJ: Retries session phase once upon encountering unexpected failure before propagating."""
        node = _make_dag_node("//pkg:exhaust_unit", "lib")
        self.storage.definitions[node] = NodeDefinition(
            task_prompt=TaskPrompt("Prompt")
        )
        self.storage.messages[node] = {_make_change("dirty")}

        call_count = 0

        def run_always_fails() -> LoopOutcome:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Fatal crash")

        self.runner.run = run_always_fails

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            # Requirement: MUST retry the session phase once upon encountering an unexpected failure before propagating.
            with self.assertRaises(RuntimeError):
                cleaner.clean([node])
            self.assertEqual(call_count, 2)
            self.assertTrue(self.storage.is_dirty(node))

    def test_clean_advancement_without_modifications_no_change_messages(self) -> None:
        """CUJ: Successful session without file modifications clears messages on cleaned node."""
        node = _make_dag_node("//pkg:unit_clean", "lib")
        self.storage.definitions[node] = NodeDefinition(
            task_prompt=TaskPrompt("Prompt")
        )
        self.storage.messages[node] = {_make_change("dirty")}
        self.sandbox.has_modifications = False

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertEqual(len(self.storage.messages.get(node, set())), 0)

    def test_clean_multi_node_session(self) -> None:
        """CUJ: Cleaning multiple nodes sharing a role within a single agent session."""
        node1 = _make_dag_node("//pkg:multi1", "lib")
        node2 = _make_dag_node("//pkg:multi2", "lib")
        self.storage.definitions[node1] = NodeDefinition(
            task_prompt=TaskPrompt("Prompt 1")
        )
        self.storage.definitions[node2] = NodeDefinition(
            task_prompt=TaskPrompt("Prompt 2")
        )
        self.storage.messages[node1] = {_make_change("dirty 1")}
        self.storage.messages[node2] = {_make_change("dirty 2")}

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            cont = cleaner.clean([node1, node2])
            self.assertTrue(cont)

    def test_clean_session_configures_role_on_role_config(self) -> None:
        """Postcondition: Session setup configures RoleConfig.role."""
        node = _make_dag_node("//pkg:role_target", "lib")
        self.storage.definitions[node] = NodeDefinition(
            task_prompt=TaskPrompt("Prompt")
        )
        self.storage.messages[node] = {_make_change("dirty")}
        self.runner.inspect_role = True

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleanerImpl)
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertEqual(self.runner.captured_role, "lib")
            self.assertEqual(self.runner.captured_nodes, [])
            self.assertEqual(self.runner.captured_custom_role, "custom_role")


if __name__ == "__main__":
    unittest.main()
