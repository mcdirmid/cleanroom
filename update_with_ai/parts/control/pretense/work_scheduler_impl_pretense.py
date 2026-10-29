"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkScheduler."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, cast
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.collections import PretenseDict, PretenseSet
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.control.lib.work_scheduler import (
    ScheduledTask,
    WorkSchedule,
    WorkScheduler,
)
from update_with_ai.parts.dag.lib import dag_storage, subgraph
from update_with_ai.parts.dag.lib.dag_storage import DagNode, FeedbackMessage, RoleAddress, UnitAddress


@dataclass
class WorkSchedulerState:
    """Canonical model state for WorkScheduler."""
    tasks: PretenseDict[DagNode, ScheduledTask] = field(default_factory=PretenseDict)
    role_precedence: PretenseDict[str, int] = field(default_factory=PretenseDict)


class WorkSchedulerStateMachine(StateMachine[WorkSchedulerState]):
    """Pretense StateMachine for WorkScheduler."""

    def __init__(self, state: Optional[WorkSchedulerState] = None):
        super().__init__(state=state or WorkSchedulerState())

    # ==============================================================================
    # 1. Seeding Transitions
    # ==============================================================================

    @transition.seeding()
    def seed_scheduled_task(
        self,
        ctx: TransitionContext[
            None,
            [DagNode, str, Optional[Sequence[str]], Optional[Sequence[FeedbackMessage]]],
            None,
        ],
    ) -> None:
        ctx.arguments(
                    node=Domain(strategy=lambda: DagNode(UnitAddress('target'), RoleAddress('lib'))),
                    task_prompt=Domain(strategy=lambda: 'Task prompt'),
                    dependency_paths=Domain(strategy=lambda: ()),
                    feedback_messages=Domain(strategy=lambda: ()),
                )
        def _consequent(
            res: None,
            node: DagNode = DagNode(UnitAddress("target"), RoleAddress("lib")),
            task_prompt: str = "Task prompt",
            dependency_paths: Optional[Sequence[str]] = None,
            feedback_messages: Optional[Sequence[FeedbackMessage]] = None,
        ) -> None:
            task = ScheduledTask(
                node=node,
                task_prompt=task_prompt,
                dependency_paths=tuple(dependency_paths or ()),
                feedback_messages=tuple(feedback_messages or ()),
            )
            self.state.tasks[node] = task
        ctx.update(_consequent)

    # ==============================================================================
    # 2. WorkScheduler Transitions
    # ==============================================================================

    @transition(WorkScheduler.schedule_work)
    def schedule_work(
        self,
        ctx: TransitionContext[
            WorkScheduler,
            [Optional[subgraph.DagSubgraph], Optional[str], Optional[int]],
            WorkSchedule,
        ],
    ) -> None:
        ctx.arguments(
                    subgraph=Domain(strategy=lambda: None),
                    dir_scope=Domain(strategy=lambda: None),
                    max_batch_size=Domain(strategy=lambda: None),
                )
        def _returns(
            subgraph: Optional[subgraph.DagSubgraph] = None,
            dir_scope: Optional[str] = None,
            max_batch_size: Optional[int] = None,
        ) -> WorkSchedule:
            candidates = list(self.state.tasks.values())
            if max_batch_size is not None and max_batch_size > 0:
                candidates = candidates[:max_batch_size]
            return WorkSchedule(tasks=tuple(candidates))
        ctx.returns(_returns)

    @transition(WorkScheduler.compute_role_precedence)
    def compute_role_precedence(
        self,
        ctx: TransitionContext[
            WorkScheduler,
            [Mapping[str, Sequence[str]]],
            Mapping[str, int],
        ],
    ) -> None:
        ctx.arguments(role_dependencies=Domain(strategy=lambda: {'lib': ['low'], 'test': ['low']}))
        def _returns(role_dependencies: Mapping[str, Sequence[str]] = {"lib": ["low"], "test": ["low"]}) -> Mapping[str, int]:
            precedence: Dict[str, int] = {}
            all_roles = set(role_dependencies.keys())
            for deps in role_dependencies.values():
                all_roles.update(deps)

            in_degree: Dict[str, int] = {r: 0 for r in all_roles}
            for r, deps in role_dependencies.items():
                in_degree[r] = len(deps)

            queue = deque([r for r, deg in in_degree.items() if deg == 0])
            for r in queue:
                precedence[r] = 0

            while queue:
                curr = queue.popleft()
                curr_dist = precedence[curr]
                for dependent, upstreams in role_dependencies.items():
                    if curr in upstreams:
                        precedence[dependent] = max(precedence.get(dependent, 0), curr_dist + 1)
                        in_degree[dependent] -= 1
                        if in_degree[dependent] == 0:
                            queue.append(dependent)

            for r in all_roles:
                if r not in precedence:
                    precedence[r] = 0
            return precedence
        ctx.returns(_returns)

    @transition(WorkScheduler.format_task_prompt)
    def format_task_prompt(
        self,
        ctx: TransitionContext[WorkScheduler, [Sequence[DagNode]], str],
    ) -> None:
        ctx.arguments(nodes=Domain(strategy=lambda: (DagNode(UnitAddress('target'), RoleAddress('lib')),)))
        def _returns(nodes: Sequence[DagNode] = ()) -> str:
            lines = [f"# Task for {len(nodes)} node(s):"]
            for n in nodes:
                lines.append(f"- {n.unit_address} ({n.role_address})")
            return "\n".join(lines)
        ctx.returns(_returns)


proto = WorkSchedulerStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_work_scheduler_fake(state: Optional[WorkSchedulerState] = None) -> WorkScheduler:
    """Instantiate a synthesized WorkScheduler fake."""
    sm = WorkSchedulerStateMachine(state)
    return sm.as_fake(WorkScheduler)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

from update_with_ai.parts.control.lib import work_scheduler_impl
from update_with_ai.parts.agent.lib import file_alias, node_config
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton
from update_with_ai.parts.agent.lib.session import agent_session
from update_with_ai.parts.dag.lib import dag_storage, subgraph
from update_with_ai.parts.core.lib import file_paths


class MockDagStorageWorkScheduler:
    tier = agent_session

    def __init__(self) -> None:
        self.dependencies: Dict[DagNode, List[Any]] = {}
        self.messages: Dict[DagNode, List[Any]] = {}
        self.dirty_nodes: Set[DagNode] = set()
        self.all_nodes: Set[DagNode] = set()

    def get_dependencies(self, node: DagNode) -> List[Any]:
        return self.dependencies.get(node, [])

    def get_messages(self, node: DagNode) -> List[Any]:
        return self.messages.get(node, [])

    def is_dirty(self, node: DagNode) -> bool:
        return node in self.dirty_nodes


@dataclass
class MockRoleDefItem:
    role_name: str
    src_pattern: str
    role_deps: Sequence[str] = ()
    feedback_role_deps: Sequence[str] = ()
    silent_role_deps: Sequence[str] = ()
    star_role_deps: Sequence[str] = ()
    audit_tag: Optional[str] = None


class MockNodeConfigWorkScheduler:
    tier = agent_session

    def __init__(self) -> None:
        self.guide_file: Optional[Any] = None
        self.read_only_files: List[Any] = []
        self.read_write_files: List[Any] = []
        self.src_file_alias_by_node: Dict[DagNode, str] = {}
        self.blame_targets_by_node: Dict[DagNode, Set[Any]] = {}
        self.is_step_mode: bool = False
        self.guide: Optional[Any] = None
        self.source_pattern: Optional[str] = "{unit_dir}/lib/{unit_name}.py"
        self.role_definitions: Dict[str, Any] = {
            "high": MockRoleDefItem("high", "{unit_dir}/high/{unit_name}.md", ()),
            "low": MockRoleDefItem("low", "{unit_dir}/low/{unit_name}.pyi", ("high",)),
            "lib": MockRoleDefItem("lib", "{unit_dir}/lib/{unit_name}.py", ("low",)),
            "test": MockRoleDefItem("test", "{unit_dir}/tests/{unit_name}_test.py", ("low",)),
        }


class MockRoleConfigWorkScheduler:
    tier = agent_session

    def __init__(self) -> None:
        self.nodes: List[DagNode] = []


class MockSubgraphWorkScheduler:
    def __init__(self, ready_nodes: List[DagNode]) -> None:
        self.ready_nodes = ready_nodes

    def next_ready_batch(self) -> List[DagNode]:
        return self.ready_nodes


@dataclass
class MockDepWS:
    node: DagNode
    is_silent: bool = False


class TestWorkSchedulerReal(unittest.TestCase):
    """Direct unit tests for work_scheduler_impl.WorkScheduler."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        work_scheduler_impl.__initialize__(self.registry)

        self.mock_storage = MockDagStorageWorkScheduler()
        self.mock_node_cfg = MockNodeConfigWorkScheduler()
        self.mock_role_cfg = MockRoleConfigWorkScheduler()

        self.registry.register_instance(self.mock_storage, keys=[dag_storage.DagStorage], tier=agent_session)
        self.registry.register_instance(self.mock_node_cfg, keys=[node_config.NodeConfig], tier=agent_session)
        self.registry.register_instance(self.mock_role_cfg, keys=[node_config.RoleConfig], tier=agent_session)

        self.node_lib = DagNode(UnitAddress("pkg:calc"), RoleAddress("lib"))
        self.node_test = DagNode(UnitAddress("pkg:calc"), RoleAddress("test"))
        self.node_low = DagNode(UnitAddress("pkg:calc"), RoleAddress("low"))

    def test_compute_role_precedence(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            scheduler = scope.get_singleton(work_scheduler_impl.WorkScheduler)
            deps = {
                "lib": ["low"],
                "test": ["low"],
                "low": ["planning"],
                "planning": ["high"],
                "high": [],
            }
            ranks = scheduler.compute_role_precedence(deps)
            self.assertEqual(ranks["high"], 0)
            self.assertEqual(ranks["planning"], 1)
            self.assertEqual(ranks["low"], 2)
            self.assertEqual(ranks["lib"], 3)
            self.assertEqual(ranks["test"], 3)

    def test_schedule_work_subgraph(self) -> None:
        sub = MockSubgraphWorkScheduler([self.node_lib, self.node_low])
        fb_msg = dag_storage.FeedbackMessage(
            content=dag_storage.MessageContent("Syntax error in calculation"),
            target=self.node_low,
        )
        self.mock_storage.messages[self.node_low] = [fb_msg]

        with enter_phase(agent_session, registry=self.registry) as scope:
            scheduler = scope.get_singleton(work_scheduler_impl.WorkScheduler)

            # Unlimited
            sched = scheduler.schedule_work(subgraph=sub)  # type: ignore
            self.assertEqual(len(sched.tasks), 2)
            # node_low has rank 2, node_lib has rank 3 -> node_low should be first!
            self.assertEqual(sched.tasks[0].node, self.node_low)
            self.assertEqual(sched.tasks[1].node, self.node_lib)
            self.assertEqual(sched.tasks[0].feedback_messages, [fb_msg])

            # Batch limit
            sched_lim = scheduler.schedule_work(subgraph=sub, max_batch_size=1)  # type: ignore
            self.assertEqual(len(sched_lim.tasks), 1)
            self.assertEqual(sched_lim.tasks[0].node, self.node_low)

    def test_schedule_work_dir_scope(self) -> None:
        self.mock_storage.all_nodes = {self.node_lib, self.node_low}
        self.mock_storage.dirty_nodes = {self.node_lib, self.node_low}
        # node_lib depends on node_low (which is dirty) -> node_lib is NOT ready
        self.mock_storage.dependencies[self.node_lib] = [MockDepWS(node=self.node_low)]

        with enter_phase(agent_session, registry=self.registry) as scope:
            scheduler = scope.get_singleton(work_scheduler_impl.WorkScheduler)
            sched = scheduler.schedule_work(dir_scope="pkg")
            # Only node_low is ready because its deps are clean
            self.assertEqual(len(sched.tasks), 1)
            self.assertEqual(sched.tasks[0].node, self.node_low)

    def test_resolve_grounding_file(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            scheduler = scope.get_singleton(work_scheduler_impl.WorkScheduler)

            # 1. Log file -> .pyi
            g1 = scheduler._resolve_grounding_file(self.node_lib, "logs/calc_qa.log", cast(Any, self.mock_node_cfg))
            self.assertTrue(g1.endswith(".pyi"))

            # 2. Test file -> low/*.pyi
            g2 = scheduler._resolve_grounding_file(self.node_test, "pkg/tests/calc_test.py", cast(Any, self.mock_node_cfg))
            self.assertEqual(g2, "pkg/low/calc.pyi")

            # 3. Lib file -> low/*.pyi
            g3 = scheduler._resolve_grounding_file(self.node_lib, "pkg/lib/calc.py", cast(Any, self.mock_node_cfg))
            self.assertEqual(g3, "pkg/low/calc.pyi")

            # 4. Low file -> high/*.md
            g4 = scheduler._resolve_grounding_file(self.node_low, "pkg/low/calc.pyi", cast(Any, self.mock_node_cfg))
            self.assertEqual(g4, "high/calc.md")

    def test_format_task_prompt(self) -> None:
        change_msg = dag_storage.ChangeMessage(
            content=dag_storage.MessageContent("Updated API specification"),
        )
        fb_msg = dag_storage.FeedbackMessage(
            content=dag_storage.MessageContent("Fix return type"),
            target=self.node_lib,
        )
        self.mock_storage.messages[self.node_lib] = [change_msg, fb_msg]

        with enter_phase(agent_session, registry=self.registry) as scope:
            scheduler = scope.get_singleton(work_scheduler_impl.WorkScheduler)

            # 1. Standard single producer node
            prompt1 = scheduler.format_task_prompt([self.node_lib])
            self.assertIn("aligned", prompt1.lower())
            self.assertIn("Fix return type", prompt1)
            self.assertIn("Incoming change", prompt1)
            self.assertIn("target parameter may be omitted", prompt1)

            # 2. Step mode
            self.mock_node_cfg.is_step_mode = True
            prompt_step = scheduler.format_task_prompt([self.node_lib])
            self.assertIn("Call advance() when done", prompt_step)

            # 3. Auditor session
            self.mock_node_cfg.is_step_mode = False
            node_qa = DagNode(UnitAddress("pkg:calc"), RoleAddress("qa"))
            prompt_audit = scheduler.format_task_prompt([node_qa])
            self.assertIn("CRITICAL: All files in this workspace are strictly read-only", prompt_audit)

            # 4. Multi-node session
            prompt_multi = scheduler.format_task_prompt([self.node_lib, self.node_test])
            self.assertIn("When submitting or failing completed units, specify target", prompt_multi)


class TestWorkSchedulerUnit(unittest.TestCase):
    """Unit tests for synthesized WorkScheduler fake."""

    def setUp(self) -> None:
        self.state = WorkSchedulerState()
        self.sm = WorkSchedulerStateMachine(self.state)
        self.node1 = DagNode(UnitAddress("core"), RoleAddress("lib"))
        self.node2 = DagNode(UnitAddress("core"), RoleAddress("test"))
        self.sm.seed_scheduled_task(self.node1, "Implement core lib")
        self.sm.seed_scheduled_task(self.node2, "Implement core test")
        self.fake: WorkScheduler = self.sm.as_fake(WorkScheduler)

    def test_schedule_work_unlimited(self) -> None:
        schedule = self.fake.schedule_work()
        self.assertEqual(len(schedule.tasks), 2)
        self.assertEqual(schedule.tasks[0].node, self.node1)

    def test_schedule_work_batch_size_limit(self) -> None:
        schedule = self.fake.schedule_work(max_batch_size=1)
        self.assertEqual(len(schedule.tasks), 1)
        self.assertEqual(schedule.tasks[0].node, self.node1)

    def test_compute_role_precedence(self) -> None:
        role_deps = {
            "planning": ["high"],
            "low": ["planning"],
            "lib": ["low"],
            "test": ["low"],
        }
        precedence = self.fake.compute_role_precedence(role_deps)
        self.assertEqual(precedence["high"], 0)
        self.assertEqual(precedence["planning"], 1)
        self.assertEqual(precedence["low"], 2)
        self.assertEqual(precedence["lib"], 3)
        self.assertEqual(precedence["test"], 3)


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestWorkSchedulerFuzz(unittest.TestCase):
    """Property fuzz tests for WorkScheduler."""

    @settings(max_examples=30)
    @given(
        num_tasks=st.integers(min_value=1, max_value=10),
        batch_limit=st.integers(min_value=1, max_value=5),
    )
    def test_batch_limit_invariant(self, num_tasks: int, batch_limit: int) -> None:
        state = WorkSchedulerState()
        sm = WorkSchedulerStateMachine(state)
        for i in range(num_tasks):
            node = DagNode(UnitAddress(f"unit_{i}"), RoleAddress("lib"))
            sm.seed_scheduled_task(node, f"Task {i}")

        fake = sm.as_fake(WorkScheduler)
        schedule = fake.schedule_work(max_batch_size=batch_limit)
        self.assertLessEqual(len(schedule.tasks), batch_limit)
        self.assertEqual(len(schedule.tasks), min(num_tasks, batch_limit))
