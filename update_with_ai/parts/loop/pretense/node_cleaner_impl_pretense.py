"""Pretense state machine, fake synthesis, unit tests, and fuzzing for NodeCleaner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Set, Tuple, cast
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system, get_singleton
from update_with_ai.parts.agent.lib.node_config import (
    ExecutionVersion,
    NodeConfig,
    RoleConfig,
    RoleName,
)
from update_with_ai.parts.agent.lib.node_storage import (
    AgentStorage,
    NodeDefinition,
    TaskPrompt,
)
from update_with_ai.parts.dag.lib.dag_storage import (
    ChangeDescription,
    ChangeMessage,
    DagDependency,
    DagMessage,
    DagNode,
    DagStorage,
    FeedbackMessage,
    MessageContent,
    RoleAddress,
    UnitAddress,
)
from update_with_ai.parts.dag.lib.subgraph import DagSubgraph
from update_with_ai.parts.loop.lib import logger, node_cleaner, node_cleaner_impl
from update_with_ai.parts.loop.lib.cleaner import LoopCleaner
from update_with_ai.parts.loop.lib.conversation import (
    Conversation,
    ConversationContent,
    ConversationMessage,
    MessageRole,
    ModelRequest,
    ToolCallId,
)
from update_with_ai.parts.loop.lib.driver import LoopDriver, LoopOutcome
from update_with_ai.parts.loop.lib.node_cleaner import NodeCleaner
from update_with_ai.parts.metadata.lib.src_metadata import SourceMetadataCoordinator


@dataclass
class NodeCleanerState:
    """Canonical model state for NodeCleaner."""
    cleaned_batches: List[Tuple[DagNode, ...]] = field(default_factory=list)
    should_continue: bool = True


proto = StateMachineProto[NodeCleanerState]()


# ==============================================================================
# 1. NodeCleaner Transitions
# ==============================================================================

@proto.transition(NodeCleaner.clean)
def clean(): pass

@clean.arguments
def _(
    state: NodeCleanerState,
    this: Any,
    nodes: Sequence[DagNode] | NotBoundType = NotBound,
) -> Optional[Tuple[Sequence[DagNode]]]:
    if isinstance(nodes, NotBoundType):
        ns = (DagNode(UnitAddress("//pkg:sample"), RoleAddress("lib")),)
    else:
        ns = tuple(nodes)
    return (ns,)

@clean.returns
def _(
    state: NodeCleanerState,
    this: Any,
    nodes: Sequence[DagNode],
    outcome: object = NotBound,
) -> Optional[Outcome[bool]]:
    state.cleaned_batches.append(tuple(nodes))
    res = state.should_continue
    if isinstance(outcome, Value) and outcome.val == res:
        return outcome
    if outcome is NotBound:
        return Value(res)
    return None


def make_cleaner_fake(state: Optional[NodeCleanerState] = None) -> NodeCleaner:
    st = state or NodeCleanerState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(NodeCleaner)


# ==============================================================================
# 2. Comprehensive Non-Fuzz Tests
# ==============================================================================

class TestNodeCleanerUnit(unittest.TestCase):
    """Deterministic unit tests validating state machine and synthesized fake."""

    def test_clean_single_batch(self) -> None:
        state = NodeCleanerState(should_continue=True)
        fake = make_cleaner_fake(state)
        node = DagNode(UnitAddress("//pkg:test"), RoleAddress("lib"))
        result = fake.clean([node])
        self.assertTrue(result)
        self.assertEqual(len(state.cleaned_batches), 1)
        self.assertEqual(state.cleaned_batches[0], (node,))

    def test_clean_halt_on_failure(self) -> None:
        state = NodeCleanerState(should_continue=False)
        fake = make_cleaner_fake(state)
        node = DagNode(UnitAddress("//pkg:test"), RoleAddress("lib"))
        result = fake.clean([node])
        self.assertFalse(result)


@dataclass(frozen=True)
class _MockBoundFile:
    relative_path: str
    owning_node: Optional[DagNode] = None


@dataclass
class _MockResponse:
    content: str = ""
    is_failed: bool = False
    is_terminated: bool = True


def _make_dag_node(unit_address: str, role_address: str = "lib") -> DagNode:
    return DagNode(
        unit_address=UnitAddress(unit_address), role_address=RoleAddress(role_address)
    )


def _make_change(content: str) -> DagMessage:
    return cast(DagMessage, ChangeMessage(content=MessageContent(content)))


class _MockStorage:
    tier = system

    def __init__(self) -> None:
        self.definitions: dict[DagNode, NodeDefinition] = {}
        self.messages: dict[DagNode, Set[DagMessage]] = {}
        self.dependencies: dict[DagNode, Set[DagDependency]] = {}
        self.feedback: dict[DagNode, List[FeedbackMessage]] = {}
        self.cleaned_nodes: List[DagNode] = []
        self.change_descriptions: dict[DagNode, Optional[Any]] = {}
        self.dirty_nodes: Set[DagNode] = set()

    def seed_dirty_node(self, node: DagNode, message: Optional[DagMessage] = None) -> None:
        self.dirty_nodes.add(node)
        if message is not None:
            self.messages.setdefault(node, set()).add(message)

    def get_node_definition(self, node: DagNode) -> Optional[NodeDefinition]:
        return self.definitions.get(node)

    def get_task_prompt(self, node: DagNode) -> TaskPrompt:
        definition = self.definitions.get(node)
        if definition is None:
            return TaskPrompt("")
        return definition.task_prompt

    def get_messages(self, node: DagNode) -> Set[DagMessage]:
        return self.messages.get(node, set())

    def clear_messages(self, node: DagNode) -> None:
        self.messages[node] = set()

    def add_message(self, message: DagMessage, to: DagNode) -> None:
        self.messages.setdefault(to, set()).add(message)

    def add_feedback_message(self, node: DagNode, message: FeedbackMessage) -> None:
        self.feedback.setdefault(node, []).append(message)
        self.messages.setdefault(node, set()).add(message)

    def mark_node_dirty(self, node: DagNode, reason: Optional[str] = None) -> None:
        self.dirty_nodes.add(node)

    def mark_node_clean(
        self, node: DagNode, change_description: Optional[Any] = None
    ) -> None:
        self.cleaned_nodes.append(node)
        self.change_descriptions[node] = change_description
        self.messages[node] = set()
        self.dirty_nodes.discard(node)

    def get_dependencies(self, node: DagNode) -> Set[DagDependency]:
        return self.dependencies.get(node, set())

    def is_dirty(self, node: DagNode) -> bool:
        return node in self.dirty_nodes


class _MockSourceMetadataCoordinator:
    tier = "agent_session"

    def __init__(self) -> None:
        self.has_modifications = False
        self.templates_materialized = False
        self.modified_nodes: Set[DagNode] = set()

    def is_code_modified(self, path: Any) -> bool:
        if isinstance(path, DagNode) and self.modified_nodes:
            return path in self.modified_nodes
        return self.has_modifications

    def is_node_modified(self, node: DagNode) -> bool:
        if self.modified_nodes:
            return node in self.modified_nodes
        return self.has_modifications

    def materialize_startup_templates(self) -> None:
        self.templates_materialized = True


class _MockConversation:
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
        resp_content = tool_response if isinstance(tool_response, str) else str(tool_response)
        self._messages.append(
            ConversationMessage(
                role=MessageRole("tool"),
                content=ConversationContent(resp_content or ""),
                tool_call_id=ToolCallId(tool_call_id) if tool_call_id else None,
                tool_name=cast(Any, tool_name) if tool_name else None,
            )
        )

    def get_model_request(self) -> ModelRequest:
        return ModelRequest(messages=list(self._messages))


class _MockRunner:
    tier = "agent_session"

    def __init__(self) -> None:
        self.outcome = LoopOutcome(
            response=cast(Any, _MockResponse(
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
            role_cfg = get_singleton(RoleConfig)
            self.captured_role = str(role_cfg.role)
            self.captured_nodes = list(role_cfg.nodes)
            role_cfg.set_role(RoleName("custom_role"))
            self.captured_custom_role = str(role_cfg.role)
        return self.outcome


class _MockNodeConfig:
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


class _MockLogger:
    tier = system

    def __init__(self) -> None:
        self.events: List[logger.RunnerLogEvent] = []

    def consume(self, event: logger.RunnerLogEvent) -> None:
        self.events.append(event)


class _MockRoleConfig:
    tier = "agent_session"

    def __init__(self) -> None:
        self.role = RoleName("")
        self.nodes: List[DagNode] = []
        self.version = ExecutionVersion(0)

    def set_role(self, role: RoleName) -> None:
        self.role = role

    def set_nodes(self, nodes: Sequence[DagNode]) -> None:
        self.nodes = list(nodes)
        self.version = ExecutionVersion(int(self.version) + 1)


class _BoolCallable:
    def __init__(self, val: bool) -> None:
        self.val = val

    def __call__(self) -> bool:
        return self.val

    def __bool__(self) -> bool:
        return self.val


class _MockDagSubgraph:
    tier = "system"

    def __init__(self, batches: List[List[DagNode]]) -> None:
        self.target: DagNode | None = None
        self.batches = list(batches)
        self.recorded_visits: List[List[DagNode]] = []
        self._complete_override: Optional[bool] = None

    def set_target(self, root: DagNode) -> None:
        self.target = root

    @property
    def is_complete(self) -> _BoolCallable:
        if self._complete_override is not None:
            return _BoolCallable(self._complete_override)
        return _BoolCallable(len(self.batches) == 0)

    def next_ready_batch(self) -> List[DagNode]:
        if self.batches:
            return self.batches.pop(0)
        return []

    def record_visit(self, batch: Sequence[DagNode]) -> None:
        self.recorded_visits.append(list(batch))


class _MockBatchCleaner:
    def __init__(self, returns_continue: bool = True) -> None:
        self.returns_continue = returns_continue
        self.cleaned_batches: List[List[DagNode]] = []

    def clean(self, batch: Sequence[DagNode]) -> bool:
        self.cleaned_batches.append(list(batch))
        return self.returns_continue


class TestNodeCleanerReal(unittest.TestCase):
    """Direct verification of the real NodeCleaner and LoopCleaner implementations."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        node_cleaner_impl.__initialize__(self.registry)
        self.storage = _MockStorage()
        self.src_metadata = _MockSourceMetadataCoordinator()
        self.sandbox = self.src_metadata
        self.history = _MockConversation()
        self.runner = _MockRunner()
        self.node_cfg = _MockNodeConfig()
        self.logger = _MockLogger()
        self.role_cfg = _MockRoleConfig()

        self.registry.register_instance(
            self.logger, keys=[logger.RunnerLogger], tier=system
        )
        self.registry.register_instance(self.storage, keys=[AgentStorage], tier=system)
        self.registry.register_instance(
            self.role_cfg, keys=[RoleConfig], tier="agent_session"
        )
        self.registry.register_instance(
            self.src_metadata, keys=[SourceMetadataCoordinator], tier="agent_session"
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
        node = _make_dag_node("//pkg:unit", "lib")
        self.storage.definitions[node] = NodeDefinition(task_prompt=TaskPrompt("Prompt"))
        self.storage.seed_dirty_node(node, _make_change("dirty"))
        self.sandbox.has_modifications = True

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleaner)
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertEqual(self.storage.messages.get(node, set()), set())
            self.assertIn(node, self.storage.cleaned_nodes)
            self.assertIsNotNone(self.storage.change_descriptions[node])

    def test_clean_advancement_per_node_modifications(self) -> None:
        node1 = _make_dag_node("//pkg:unit1", "lib")
        node2 = _make_dag_node("//pkg:unit2", "lib")
        self.storage.definitions[node1] = NodeDefinition(task_prompt=TaskPrompt("Prompt 1"))
        self.storage.definitions[node2] = NodeDefinition(task_prompt=TaskPrompt("Prompt 2"))
        self.storage.seed_dirty_node(node1, _make_change("dirty1"))
        self.storage.seed_dirty_node(node2, _make_change("dirty2"))
        self.sandbox.modified_nodes = {node1}

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleaner)
            cont = cleaner.clean([node1, node2])
            self.assertTrue(cont)
            self.assertIn(node1, self.storage.cleaned_nodes)
            self.assertIn(node2, self.storage.cleaned_nodes)
            self.assertIsNotNone(self.storage.change_descriptions[node1])
            self.assertIsNone(self.storage.change_descriptions[node2])

    def test_clean_blame_delivers_feedback(self) -> None:
        node = _make_dag_node("//pkg:unit", "lib")
        dep_blamed = _make_dag_node("//pkg:dep_blamed", "lib")
        bf = _MockBoundFile(relative_path="dep_blamed.py", owning_node=dep_blamed)
        self.node_cfg.blame_targets_by_node = {node: {bf}}
        self.storage.definitions[node] = NodeDefinition(task_prompt=TaskPrompt("Prompt"))
        self.storage.dependencies[node] = {DagDependency(node=dep_blamed)}
        self.storage.seed_dirty_node(node, _make_change("dirty"))
        self.runner.outcome = LoopOutcome(
            response=cast(Any, _MockResponse(
                is_failed=False,
                is_terminated=True,
                content="Blamed //pkg:dep_blamed: Broken API",
            )),
            conversation=ModelRequest(messages=[]),
        )

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleaner)
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertIn(dep_blamed, self.storage.messages)
            msgs = list(self.storage.messages[dep_blamed])
            self.assertEqual(len(msgs), 1)
            self.assertIsInstance(msgs[0], FeedbackMessage)
            assert isinstance(msgs[0], FeedbackMessage)
            self.assertEqual(msgs[0].content, "Broken API")
            self.assertEqual(msgs[0].target, dep_blamed)

    def test_clean_run_failure_leaves_nodes_dirty(self) -> None:
        node = _make_dag_node("//pkg:fail_unit", "lib")
        self.storage.definitions[node] = NodeDefinition(task_prompt=TaskPrompt("Prompt"))
        self.storage.seed_dirty_node(node, _make_change("dirty"))
        self.runner.outcome = LoopOutcome(
            response=cast(Any, _MockResponse(
                is_failed=True,
                is_terminated=True,
                content="Fatal tool failure",
            )),
            conversation=ModelRequest(messages=[]),
        )

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleaner)
            cont = cleaner.clean([node])
            self.assertFalse(cont)
            self.assertTrue(self.storage.is_dirty(node))

    def test_clean_promptless_without_messages(self) -> None:
        node = _make_dag_node("//pkg:pass_thru_no_msg", "lib")
        self.storage.definitions[node] = NodeDefinition(task_prompt=TaskPrompt(""))
        self.storage.dirty_nodes.add(node)

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleaner)
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertIn(node, self.storage.cleaned_nodes)
            self.assertIsNone(self.storage.change_descriptions[node])

    def test_matches_blame_target_coverage(self) -> None:
        node = _make_dag_node("//pkg:unit", "lib")
        dep_blamed = _make_dag_node("//pkg:dep_blamed", "lib")

        @dataclass(frozen=True)
        class WsPath:
            path: str

        @dataclass(frozen=True)
        class BoundFileWithWs:
            relative_path: str
            owning_node: Any
            workspace_path: Any
            short_name: str

        bf = BoundFileWithWs(
            relative_path="parts/pkg/dep_blamed.py",
            owning_node=dep_blamed,
            workspace_path=WsPath("workspace/parts/pkg/dep_blamed.py"),
            short_name="dep_blamed",
        )

        self.node_cfg.blame_targets_by_node = {node: {bf}}
        self.storage.definitions[node] = NodeDefinition(task_prompt=TaskPrompt("Prompt"))
        self.storage.dependencies[node] = {DagDependency(node=dep_blamed)}
        self.storage.seed_dirty_node(node, _make_change("dirty"))

        test_cases = [
            "Blamed `parts/pkg/dep_blamed.py`: Relative path match",
            "Blamed `workspace/parts/pkg/dep_blamed.py`: Ws path match",
            "Blamed `dep_blamed`: Short name match",
            "Blamed `dep_blamed.py`: Basename match",
            "Blamed `...`: Ellipsis blame target",
            "Blamed ``: Empty blame target defaults to single configured",
            "Blamed `.`: Dot blame target",
            "Blamed `extra/dep_blamed.py`: Suffix blame target",
        ]

        # Direct unit test of _matches_blame_target for str bound file and remaining path branches
        self.assertTrue(node_cleaner_impl._matches_blame_target("parts/pkg/dep_blamed.py", "dep_blamed.py"))
        self.assertTrue(node_cleaner_impl._matches_blame_target("parts/pkg/dep_blamed.py", "pkg/dep_blamed.py"))
        self.assertTrue(node_cleaner_impl._matches_blame_target("parts/pkg/dep_blamed.py", "parts/pkg/dep_blamed.py"))
        self.assertFalse(node_cleaner_impl._matches_blame_target("parts/pkg/dep_blamed.py", ""))
        self.assertFalse(node_cleaner_impl._matches_blame_target("parts/pkg/dep_blamed.py", "."))

        for fmt in test_cases:
            self.storage.clear_messages(dep_blamed)
            self.runner.outcome = LoopOutcome(
                response=cast(Any, _MockResponse(
                    is_failed=False,
                    is_terminated=True,
                    content=fmt,
                )),
                conversation=ModelRequest(messages=[]),
            )
            with enter_phase(system, registry=self.registry) as scope:
                cleaner = scope.get_singleton(NodeCleaner)
                cont = cleaner.clean([node])
                self.assertTrue(cont)

    def test_is_node_modified_with_rw_files(self) -> None:
        import tempfile
        node = _make_dag_node("//pkg:unit_rw", "lib")
        self.storage.definitions[node] = NodeDefinition(task_prompt=TaskPrompt("Prompt"))
        self.storage.seed_dirty_node(node, _make_change("dirty"))

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = f"{tmpdir}/file.txt"
            with open(file_path, "w") as f:
                f.write("content")

            @dataclass(frozen=True)
            class WsPath:
                path: str

            @dataclass(frozen=True)
            class RWFile:
                owning_node: Any
                workspace_path: Any

            rw = RWFile(owning_node=node, workspace_path=WsPath(file_path))
            self.node_cfg.read_write_files = {rw}

            # Coordinator reports file modified
            self.sandbox.is_code_modified = lambda path: path == file_path

            with enter_phase(system, registry=self.registry) as scope:
                cleaner = scope.get_singleton(NodeCleaner)
                cont = cleaner.clean([node])
                self.assertTrue(cont)
                self.assertIsNotNone(self.storage.change_descriptions[node])

    def test_clean_with_missing_optional_singletons_and_metadata_exception(self) -> None:
        # A registry without SourceMetadataCoordinator or NodeConfig
        reg = LifecycleRegistry()
        node_cleaner_impl.__initialize__(reg)
        storage = _MockStorage()
        reg.register_instance(storage, keys=[AgentStorage], tier=system)
        reg.register_instance(_MockLogger(), keys=[logger.RunnerLogger], tier=system)
        reg.register_instance(_MockRoleConfig(), keys=[RoleConfig], tier="agent_session")
        reg.register_instance(_MockConversation(), keys=[Conversation], tier="agent_session")
        reg.register_instance(_MockRunner(), keys=[LoopDriver], tier="agent_session")

        node = _make_dag_node("//pkg:unit_no_meta", "lib")
        storage.definitions[node] = NodeDefinition(task_prompt=TaskPrompt("Prompt"))
        storage.seed_dirty_node(node, _make_change("dirty"))

        with enter_phase(system, registry=reg) as scope:
            cleaner = scope.get_singleton(NodeCleaner)
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertIn(node, storage.cleaned_nodes)



    def test_loop_cleaner_empty_batch_breaks(self) -> None:
        root = _make_dag_node("//pkg:root")
        subgraph = _MockDagSubgraph(batches=[])
        # Return complete = False, but batch = []
        subgraph._complete_override = False
        cleaner = _MockBatchCleaner(returns_continue=True)

        self.registry.register_instance(subgraph, keys=[DagSubgraph], tier="system")

        with enter_phase("system", registry=self.registry) as scope:
            loop_cleaner_svc = scope.get_singleton(LoopCleaner)
            result = loop_cleaner_svc.clean(root, cast(Any, cleaner))
            self.assertFalse(result)

        node = _make_dag_node("//pkg:pass_thru", "lib")
        self.storage.definitions[node] = NodeDefinition(task_prompt=TaskPrompt(""))
        self.storage.seed_dirty_node(node, _make_change("upstream change"))

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleaner)
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertEqual(self.runner.run_count, 0)
            self.assertEqual(self.storage.messages.get(node, set()), set())
            self.assertIn(node, self.storage.cleaned_nodes)
            self.assertIsNotNone(self.storage.change_descriptions[node])

    def test_clean_retries_on_unexpected_failure(self) -> None:
        node = _make_dag_node("//pkg:retry_unit", "lib")
        self.storage.definitions[node] = NodeDefinition(task_prompt=TaskPrompt("Prompt"))
        self.storage.seed_dirty_node(node, _make_change("dirty"))

        attempts = 0

        def run_flaky() -> LoopOutcome:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("Transient crash")
            return LoopOutcome(
                response=cast(Any, _MockResponse(
                    is_failed=False,
                    is_terminated=True,
                    content="Success",
                )),
                conversation=ModelRequest(messages=[]),
            )

        self.runner.run = run_flaky

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleaner)
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertEqual(attempts, 2)

    def test_clean_blame_parsing_formats(self) -> None:
        node = _make_dag_node("//pkg:unit", "lib")
        dep_blamed = _make_dag_node("//pkg:dep_blamed", "lib")
        bf = _MockBoundFile(relative_path="dep_blamed.py", owning_node=dep_blamed)
        self.node_cfg.blame_targets_by_node = {node: {bf}}
        self.storage.definitions[node] = NodeDefinition(task_prompt=TaskPrompt("Prompt"))
        self.storage.dependencies[node] = {DagDependency(node=dep_blamed)}
        self.storage.seed_dirty_node(node, _make_change("dirty"))

        blame_formats = [
            "Blamed `//pkg:dep_blamed`: Spec contract defect",
            "Blamed `dep_blamed.py`: Method signature mismatch",
            "Blamed //pkg:dep_blamed: Error: invalid argument",
            "Blamed //pkg/sub/dir:dep_blamed: Upstream defect",
        ]

        for fmt in blame_formats:
            self.storage.clear_messages(dep_blamed)
            self.runner.outcome = LoopOutcome(
                response=cast(Any, _MockResponse(
                    is_failed=False,
                    is_terminated=True,
                    content=fmt,
                )),
                conversation=ModelRequest(messages=[]),
            )
            with enter_phase(system, registry=self.registry) as scope:
                cleaner = scope.get_singleton(NodeCleaner)
                cont = cleaner.clean([node])
                self.assertTrue(cont)
                self.assertIn(dep_blamed, self.storage.messages)

    def test_clean_blame_unconfigured_target_leaves_nodes_dirty(self) -> None:
        node = _make_dag_node("//pkg:unit", "lib")
        dep_guide = _make_dag_node("//pkg:dep_guide", "lib")
        self.storage.definitions[node] = NodeDefinition(task_prompt=TaskPrompt("Prompt"))
        self.storage.dependencies[node] = {DagDependency(node=dep_guide)}
        self.storage.seed_dirty_node(node, _make_change("dirty"))
        self.node_cfg.blame_targets_by_node = {node: set()}
        self.runner.outcome = LoopOutcome(
            response=cast(Any, _MockResponse(
                is_failed=False,
                is_terminated=True,
                content="Blamed //pkg:unknown_target: Unconfigured blame error",
            )),
            conversation=ModelRequest(messages=[]),
        )

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleaner)
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertTrue(self.storage.is_dirty(node))
            self.assertEqual(len(self.storage.get_messages(dep_guide)), 0)

    def test_clean_blame_never_delivered_to_non_feedback_dependencies(self) -> None:
        node = _make_dag_node("//pkg:unit", "lib")
        dep_feedback = _make_dag_node("//pkg:feedback_dep", "lib")
        dep_non_feedback = _make_dag_node("//pkg:guide_dep", "lib")
        bf = _MockBoundFile(relative_path="feedback_dep.py", owning_node=dep_feedback)
        self.node_cfg.blame_targets_by_node = {node: {bf}}
        self.storage.definitions[node] = NodeDefinition(task_prompt=TaskPrompt("Prompt"))
        self.storage.dependencies[node] = {
            DagDependency(node=dep_feedback),
            DagDependency(node=dep_non_feedback),
        }
        self.storage.seed_dirty_node(node, _make_change("dirty"))
        self.runner.outcome = LoopOutcome(
            response=cast(Any, _MockResponse(
                is_failed=False,
                is_terminated=True,
                content="Blamed //pkg:feedback_dep: Contract violation",
            )),
            conversation=ModelRequest(messages=[]),
        )

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleaner)
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertIn(dep_feedback, self.storage.messages)
            self.assertEqual(len(self.storage.get_messages(dep_non_feedback)), 0)

    def test_clean_unhandleable_failure_retries_exhausted(self) -> None:
        node = _make_dag_node("//pkg:exhaust_unit", "lib")
        self.storage.definitions[node] = NodeDefinition(task_prompt=TaskPrompt("Prompt"))
        self.storage.seed_dirty_node(node, _make_change("dirty"))

        call_count = 0

        def run_always_fails() -> LoopOutcome:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Fatal crash")

        self.runner.run = run_always_fails

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleaner)
            with self.assertRaises(RuntimeError):
                cleaner.clean([node])
            self.assertEqual(call_count, 2)
            self.assertTrue(self.storage.is_dirty(node))

    def test_clean_advancement_without_modifications_no_change_messages(self) -> None:
        node = _make_dag_node("//pkg:unit_clean", "lib")
        self.storage.definitions[node] = NodeDefinition(task_prompt=TaskPrompt("Prompt"))
        self.storage.seed_dirty_node(node, _make_change("dirty"))
        self.sandbox.has_modifications = False

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleaner)
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertEqual(len(self.storage.messages.get(node, set())), 0)
            self.assertIn(node, self.storage.cleaned_nodes)
            self.assertIsNone(self.storage.change_descriptions[node])

    def test_clean_multi_node_session(self) -> None:
        node1 = _make_dag_node("//pkg:multi1", "lib")
        node2 = _make_dag_node("//pkg:multi2", "lib")
        self.storage.definitions[node1] = NodeDefinition(task_prompt=TaskPrompt("Prompt 1"))
        self.storage.definitions[node2] = NodeDefinition(task_prompt=TaskPrompt("Prompt 2"))
        self.storage.seed_dirty_node(node1, _make_change("dirty 1"))
        self.storage.seed_dirty_node(node2, _make_change("dirty 2"))

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleaner)
            cont = cleaner.clean([node1, node2])
            self.assertTrue(cont)
            self.assertIn(node1, self.storage.cleaned_nodes)
            self.assertIn(node2, self.storage.cleaned_nodes)

    def test_clean_session_configures_role_on_role_config(self) -> None:
        node = _make_dag_node("//pkg:role_target", "lib")
        self.storage.definitions[node] = NodeDefinition(task_prompt=TaskPrompt("Prompt"))
        self.storage.seed_dirty_node(node, _make_change("dirty"))
        self.runner.inspect_role = True

        with enter_phase(system, registry=self.registry) as scope:
            cleaner = scope.get_singleton(NodeCleaner)
            cont = cleaner.clean([node])
            self.assertTrue(cont)
            self.assertEqual(self.runner.captured_role, "lib")
            self.assertEqual(self.runner.captured_nodes, [])
            self.assertEqual(self.runner.captured_custom_role, "custom_role")

    def test_loop_cleaner_success(self) -> None:
        root = _make_dag_node("//pkg:root")
        node_b = _make_dag_node("//pkg:dep")
        subgraph = _MockDagSubgraph(batches=[[node_b], [root]])
        cleaner = _MockBatchCleaner(returns_continue=True)

        self.registry.register_instance(subgraph, keys=[DagSubgraph], tier="system")

        with enter_phase("system", registry=self.registry) as scope:
            loop_cleaner_svc = scope.get_singleton(LoopCleaner)
            result = loop_cleaner_svc.clean(root, cast(Any, cleaner))

            self.assertTrue(result)
            self.assertEqual(subgraph.target, root)
            self.assertEqual(cleaner.cleaned_batches, [[node_b], [root]])
            self.assertEqual(subgraph.recorded_visits, [[node_b], [root]])
            self.assertTrue(subgraph.is_complete())

    def test_loop_cleaner_halts_when_cleaner_cannot_continue(self) -> None:
        root = _make_dag_node("//pkg:root")
        node_b = _make_dag_node("//pkg:dep")
        subgraph = _MockDagSubgraph(batches=[[node_b], [root]])
        cleaner = _MockBatchCleaner(returns_continue=False)

        self.registry.register_instance(subgraph, keys=[DagSubgraph], tier="system")

        with enter_phase("system", registry=self.registry) as scope:
            loop_cleaner_svc = scope.get_singleton(LoopCleaner)
            result = loop_cleaner_svc.clean(root, cast(Any, cleaner))

            self.assertFalse(result)
            self.assertEqual(cleaner.cleaned_batches, [[node_b]])
            self.assertFalse(subgraph.is_complete())

    def test_loop_cleaner_already_complete(self) -> None:
        root = _make_dag_node("//pkg:root")
        subgraph = _MockDagSubgraph(batches=[])
        cleaner = _MockBatchCleaner(returns_continue=True)

        self.registry.register_instance(subgraph, keys=[DagSubgraph], tier="system")

        with enter_phase("system", registry=self.registry) as scope:
            loop_cleaner_svc = scope.get_singleton(LoopCleaner)
            result = loop_cleaner_svc.clean(root, cast(Any, cleaner))

            self.assertTrue(result)
            self.assertEqual(subgraph.target, root)
            self.assertEqual(len(cleaner.cleaned_batches), 0)

    def test_role_config_default_implementation(self) -> None:
        role_cfg = node_cleaner_impl._RoleConfig()
        self.assertEqual(str(role_cfg.role), "")
        self.assertEqual(list(role_cfg.nodes), [])
        self.assertEqual(int(role_cfg.version), 0)
        node = _make_dag_node("//pkg:test", "custom")
        role_cfg.set_nodes([node])
        self.assertEqual(str(role_cfg.role), "custom")
        self.assertEqual(list(role_cfg.nodes), [node])
        self.assertEqual(int(role_cfg.version), 1)
        role_cfg.set_role(RoleName("manual"))
        self.assertEqual(str(role_cfg.role), "manual")


# ==============================================================================
# 3. Hypothesis Property & Fuzz Test
# ==============================================================================

class TestNodeCleanerFuzz(unittest.TestCase):
    """Property fuzz testing for NodeCleaner."""

    @settings(max_examples=25)
    @given(st.lists(st.text(min_size=1, max_size=10), max_size=5))
    def test_node_cleaner_property(self, names: list[str]) -> None:
        state = NodeCleanerState()
        fake = make_cleaner_fake(state)
        nodes = [_make_dag_node(f"//pkg:{name}") for name in names]
        result = fake.clean(nodes)
        self.assertTrue(result)

