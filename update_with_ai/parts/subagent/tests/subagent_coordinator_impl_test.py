"""Unit tests for subagent_coordinator_impl."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Sequence, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.subagent.lib import subagent_coordinator
from update_with_ai.parts.subagent.lib.subagent_coordinator_impl import (
    SubagentCoordinator,
    __initialize__,
    resolve_model_parameters,
)
from update_with_ai.parts.workspace_cli.lib import work
from update_with_ai.parts.workspace.lib import (
    provision,
    role_registry,
)


class FakeWorkspaceProvisioner:
    """Test double implementing WorkspaceProvisioner protocol."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.commissioned: List[Tuple[str, str]] = []

    def commission(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        reset: bool = False,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> role_registry.WorkspaceDescriptor:
        self.commissioned.append((role_name, dir_scope))
        ws_dir = custom_dest or f"/repo/cleanroom/.workspaces/{role_name}_{dir_scope}"
        r_def = role_registry.RoleDefinition(
            role_name=role_name,
            guide_path=f"guides/{role_name}.md",
            writable_file_patterns=[],
            readonly_file_patterns=[],
            feedback_role_deps=[],
        )
        return role_registry.WorkspaceDescriptor(
            workspace_dir=ws_dir,
            main_repository_root="/repo/cleanroom",
            role_definition=r_def,
            directory_scope=dir_scope,
        )


class FakeWorkspaceRegistry:
    """Test double implementing WorkspaceRegistry protocol."""

    tier = agent_session.agent_session

    def __init__(self, roles: Sequence[role_registry.RoleDefinition], base_dir: Optional[str] = None) -> None:
        self.roles = list(roles)
        self.role_map = {r.role_name: r for r in self.roles}
        self.base_dir = base_dir

    def discover_repository_root(self, start_dir: Optional[str] = None) -> str:
        return "/repo/cleanroom"

    def resolve_role_definition(
        self,
        role_name_or_address: str,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> role_registry.RoleDefinition:
        clean = role_name_or_address.split(":")[-1].strip().lower()
        if clean in self.role_map:
            return self.role_map[clean]
        raise KeyError(f"Role '{clean}' not found")

    def list_roles(
        self,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Sequence[role_registry.RoleDefinition]:
        return list(self.roles)

    def compute_workspace_dir(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> str:
        if custom_dest:
            return custom_dest
        if self.base_dir:
            return os.path.join(self.base_dir, f"{role_name}_{dir_scope}")
        return f"/repo/cleanroom/.workspaces/{role_name}_{dir_scope}"

    def record_workspace(self, descriptor: role_registry.WorkspaceDescriptor, repo_root: Optional[str] = None) -> None:
        pass

    def unregister_workspace(self, workspace_dir: str, repo_root: Optional[str] = None) -> bool:
        return True

    def load_active_workspaces(self, repo_root: Optional[str] = None) -> Sequence[role_registry.WorkspaceDescriptor]:
        return ()


class FakeWorkspaceWorkManager:
    """Test double implementing WorkspaceWorkManager protocol."""

    tier = agent_session.agent_session

    def __init__(
        self,
        queue_data: Optional[Dict[str, Tuple[Sequence[work.WorkQueueItem], Sequence[work.WorkQueueItem]]]] = None,
    ) -> None:
        self.queue_data = queue_data or {}
        self.pending: Dict[str, List[str]] = {}

    def compute_role_work_queue(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: str,
        target_unit: Optional[str] = None,
    ) -> Tuple[Sequence[work.WorkQueueItem], Sequence[work.WorkQueueItem]]:
        self.last_target_unit = target_unit
        return self.queue_data.get(role_name, ((), ()))

    def get_pending_work(self, workspace_dir: str) -> Sequence[str]:
        return list(self.pending.get(workspace_dir, []))

    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None:
        self.pending[workspace_dir] = list(targets)

    def clear_pending_work(self, workspace_dir: str) -> None:
        self.pending.pop(workspace_dir, None)

    def remove_pending_target(self, workspace_dir: str, target: str) -> bool:
        items = self.pending.get(workspace_dir, [])
        if target in items:
            items.remove(target)
            return True
        return False


class FakeHarnessAdapter:
    """Test double implementing HarnessAdapter protocol."""

    def __init__(self, scripted_results: Optional[Dict[str, subagent_coordinator.RoleRoundResult]] = None) -> None:
        self.scripted_results = scripted_results or {}
        self.dispatches: List[subagent_coordinator.RoleDispatch] = []
        self.interrupted: List[str] = []

    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        self.dispatches.append(dispatch)
        return f"handle_{dispatch.role_name}"

    def await_role(self, task_handle: str) -> subagent_coordinator.RoleRoundResult:
        if task_handle in self.scripted_results:
            return self.scripted_results[task_handle]
        role = task_handle.replace("handle_", "")
        return subagent_coordinator.RoleRoundResult(
            role=role,
            status="clean",
            submitted_targets=("target.py",),
            telemetry=subagent_coordinator.TokenUsage(100, 50, 20, 170, 0.001),
        )

    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleRoundResult]:
        return self.await_role(task_handle)

    def interrupt_role(self, task_handle: str) -> None:
        self.interrupted.append(task_handle)


def _make_item(target_file: str, role_name: str, is_ready: bool = True) -> work.WorkQueueItem:
    return work.WorkQueueItem(
        target_file=target_file,
        role_name=role_name,
        dirtiness_reasons=("modified",),
        dependency_files=(),
        is_ready=is_ready,
        blocked_reasons=() if is_ready else ("upstream dirty",),
        contract_files=(),
    )


class SubagentCoordinatorImplTest(unittest.TestCase):
    """Test cases for SubagentCoordinator implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.fake_provisioner = FakeWorkspaceProvisioner()
        self.registry.register_instance(
            self.fake_provisioner,
            keys=[provision.WorkspaceProvisioner],
            tier=agent_session.agent_session,
        )

        self.spec_role_high = role_registry.RoleDefinition(
            role_name="high",
            guide_path="guides/high.md",
            writable_file_patterns=["high/*.md"],
            readonly_file_patterns=[],
            feedback_role_deps=[],
            role_deps=[],
            star_role_deps=["high"],
            stub_role_deps=[],
            src_pattern="{unit_dir}/high/{unit_name}.md",
        )
        self.spec_role_low = role_registry.RoleDefinition(
            role_name="low",
            guide_path="guides/low.md",
            writable_file_patterns=["low/*.pyi"],
            readonly_file_patterns=["high/*.md"],
            feedback_role_deps=["high"],
            role_deps=["high"],
            star_role_deps=["low"],
            stub_role_deps=[],
            src_pattern="{unit_dir}/low/{unit_name}.pyi",
        )
        self.impl_role_lib = role_registry.RoleDefinition(
            role_name="lib",
            guide_path="guides/lib.md",
            writable_file_patterns=["lib/*.py"],
            readonly_file_patterns=["low/*.pyi"],
            feedback_role_deps=["low"],
            role_deps=["low"],
            star_role_deps=["low"],
            stub_role_deps=["low"],
            src_pattern="{unit_dir}/lib/{unit_name}.py",
        )
        self.impl_role_test = role_registry.RoleDefinition(
            role_name="test",
            guide_path="guides/test.md",
            writable_file_patterns=["tests/*.py"],
            readonly_file_patterns=["low/*.pyi"],
            feedback_role_deps=["low"],
            role_deps=["low"],
            star_role_deps=["low"],
            stub_role_deps=["low"],
            src_pattern="{unit_dir}/tests/{unit_name}_test.py",
        )
        self.spec_role_planning = role_registry.RoleDefinition(
            role_name="planning",
            guide_path="guides/planning.md",
            writable_file_patterns=["planning/*.md"],
            readonly_file_patterns=["high/*.md"],
            feedback_role_deps=["high"],
            role_deps=["high"],
            star_role_deps=["planning"],
            stub_role_deps=[],
            src_pattern="{unit_dir}/planning/{unit_name}.md",
        )
        self.role_qa = role_registry.RoleDefinition(
            role_name="qa",
            guide_path="guides/qa.md",
            writable_file_patterns=["qa/*.md"],
            readonly_file_patterns=["lib/*.py", "tests/*.py"],
            feedback_role_deps=["lib", "test"],
            role_deps=["lib", "test"],
            star_role_deps=["qa"],
            stub_role_deps=[],
            src_pattern="{unit_dir}/qa/{unit_name}.md",
        )

    def test_partitioning_dirty_roles_into_topological_waves(self) -> None:
        """Scenario 1: Evaluates DAG queues and partitions unblocked dirty roles."""
        fake_reg = FakeWorkspaceRegistry([
            self.spec_role_high,
            self.spec_role_low,
            self.impl_role_lib,
            self.impl_role_test,
        ])
        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item("high/unit.md", "high")], ())),
            "low": (((), ([_make_item("low/unit.pyi", "low", is_ready=False)]))),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            waves = coord.compute_execution_waves("pkg_a")
            self.assertEqual(len(waves), 1)
            self.assertEqual(len(waves[0]), 1)
            self.assertEqual(waves[0][0].role_name, "high")
            self.assertEqual(waves[0][0].ready_targets, ("high/unit.md",))

    def test_separating_specification_roles_into_single_role_waves(self) -> None:
        """Scenario 2: Separates sequential specification roles into single-role waves."""
        fake_reg = FakeWorkspaceRegistry([
            self.spec_role_high,
            self.spec_role_low,
        ])
        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item("high/unit.md", "high")], ())),
            "low": (([_make_item("low/unit.pyi", "low")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            waves = coord.compute_execution_waves("pkg_a")
            self.assertEqual(len(waves), 2)
            # High is dependency of low, so wave 0 is high and wave 1 is low
            self.assertEqual(waves[0][0].role_name, "high")
            self.assertEqual(waves[1][0].role_name, "low")

    def test_grouping_independent_implementation_roles_into_parallel_waves(self) -> None:
        """Scenario 3: Groups unblocked implementation roles with stub dependencies into a parallel wave."""
        fake_reg = FakeWorkspaceRegistry([
            self.impl_role_lib,
            self.impl_role_test,
        ])
        fake_work = FakeWorkspaceWorkManager({
            "lib": (([_make_item("lib/unit.py", "lib")], ())),
            "test": (([_make_item("tests/unit_test.py", "test")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            waves = coord.compute_execution_waves("pkg_a")
            self.assertEqual(len(waves), 1)
            # Both lib and test clustered into wave 0
            roles_in_wave = {d.role_name for d in waves[0]}
            self.assertEqual(roles_in_wave, {"lib", "test"})

    def test_iterative_wave_execution_until_dag_convergence(self) -> None:
        """Scenario 4: Waves execute iteratively until all units evaluate clean."""
        fake_reg = FakeWorkspaceRegistry([self.impl_role_lib])
        fake_work = FakeWorkspaceWorkManager({
            "lib": (([_make_item("lib/unit.py", "lib")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        class ConvergenceHarness(FakeHarnessAdapter):
            def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
                fake_work.queue_data["lib"] = ((), ())
                return super().dispatch_role(dispatch)

        harness = ConvergenceHarness({
            "handle_lib": subagent_coordinator.RoleRoundResult(
                role="lib",
                status="clean",
                submitted_targets=("lib/unit.py",),
                telemetry=subagent_coordinator.TokenUsage(100, 20, 50, 170, 0.005),
            ),
        })

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            summary = coord.orchestrate("pkg_a", harness, poll_interval=0.001)
            self.assertTrue(summary.is_converged)
            self.assertEqual(summary.total_waves, 1)
            self.assertEqual(summary.submitted_count, 1)
            self.assertEqual(summary.blamed_count, 0)
            self.assertEqual(summary.total_telemetry.total_tokens, 170)
            self.assertAlmostEqual(summary.total_telemetry.cost_usd, 0.005)

    def test_early_termination_upon_role_failure(self) -> None:
        """Scenario 5: Execution terminates early when a subagent round reports failure."""
        fake_reg = FakeWorkspaceRegistry([self.spec_role_high, self.spec_role_low])
        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item("high/unit.md", "high")], ())),
            "low": (([_make_item("low/unit.pyi", "low")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        harness = FakeHarnessAdapter({
            "handle_high": subagent_coordinator.RoleRoundResult(
                role="high",
                status="failed",
                failure_reason="Syntax error in spec",
            )
        })

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            summary = coord.orchestrate("pkg_a", harness, poll_interval=0.001)
            self.assertFalse(summary.is_converged)
            self.assertEqual(summary.total_waves, 1)
            self.assertIn("Syntax error in spec", summary.status_message)

    def test_cumulative_token_telemetry_aggregation(self) -> None:
        """Scenario 6: Aggregates total token usage into cumulative financial expenditure."""
        fake_reg = FakeWorkspaceRegistry([self.impl_role_lib, self.impl_role_test])
        fake_work = FakeWorkspaceWorkManager({
            "lib": (([_make_item("lib/unit.py", "lib")], ())),
            "test": (([_make_item("tests/unit_test.py", "test")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        class AggregationHarness(FakeHarnessAdapter):
            def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
                fake_work.queue_data[dispatch.role_name] = ((), ())
                return super().dispatch_role(dispatch)

        harness = AggregationHarness({
            "handle_lib": subagent_coordinator.RoleRoundResult(
                role="lib",
                status="clean",
                submitted_targets=("lib/unit.py",),
                telemetry=subagent_coordinator.TokenUsage(1000, 500, 200, 1700, 0.015),
            ),
            "handle_test": subagent_coordinator.RoleRoundResult(
                role="test",
                status="clean",
                submitted_targets=("tests/unit_test.py",),
                telemetry=subagent_coordinator.TokenUsage(2000, 1000, 400, 3400, 0.030),
            ),
        })

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            summary = coord.orchestrate("pkg_a", harness, poll_interval=0.001)
            self.assertTrue(summary.is_converged)
            self.assertEqual(summary.total_telemetry.input_tokens, 3000)
            self.assertEqual(summary.total_telemetry.cached_tokens, 1500)
            self.assertEqual(summary.total_telemetry.output_tokens, 600)
            self.assertEqual(summary.total_telemetry.total_tokens, 5100)
            self.assertAlmostEqual(summary.total_telemetry.cost_usd, 0.045)

    def test_auto_commissioning_absent_role_workspaces_before_dispatch(self) -> None:
        """Scenario 7: Commissions absent role workspace via provision before dispatch."""
        fake_reg = FakeWorkspaceRegistry([self.spec_role_high])
        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item("high/unit.md", "high")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            waves = coord.compute_execution_waves("pkg_a")
            self.assertEqual(len(waves), 1)
            self.assertIn(("high", "pkg_a"), self.fake_provisioner.commissioned)

    def test_target_role_boundary_filtering(self) -> None:
        """Scenario 8: Restricts execution waves up to target role boundary."""
        fake_reg = FakeWorkspaceRegistry([
            self.spec_role_high,
            self.spec_role_low,
            self.impl_role_lib,
            self.impl_role_test,
        ])
        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item("high/unit.md", "high")], ())),
            "low": (([_make_item("low/unit.pyi", "low")], ())),
            "lib": (([_make_item("lib/unit.py", "lib")], ())),
            "test": (([_make_item("tests/unit_test.py", "test")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            waves = coord.compute_execution_waves("pkg_a", target_role="low")
            role_names = [d.role_name for wave in waves for d in wave]
            self.assertIn("high", role_names)
            self.assertIn("low", role_names)
            self.assertNotIn("lib", role_names)
            self.assertNotIn("test", role_names)

    def test_orchestrate_resets_preexisting_workspaces_on_startup(self) -> None:
        """Scenario 9: Resets preexisting role workspace directories on orchestration startup."""
        tmp_dir = tempfile.mkdtemp()
        try:
            fake_reg = FakeWorkspaceRegistry([self.spec_role_high], base_dir=tmp_dir)
            ws_dir = os.path.join(tmp_dir, "high_pkg_a")
            os.makedirs(ws_dir, exist_ok=True)
            stale_file = os.path.join(ws_dir, "stale.txt")
            with open(stale_file, "w") as f:
                f.write("stale")
            self.assertTrue(os.path.isfile(stale_file))

            fake_work = FakeWorkspaceWorkManager({
                "high": ((), ()),
            })
            self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
            self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

            harness = FakeHarnessAdapter({})

            with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
                coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
                summary = coord.orchestrate("pkg_a", harness)
                self.assertTrue(summary.is_converged)
                self.assertFalse(os.path.exists(ws_dir))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_orchestrate_deletes_workspaces_on_clean_convergence(self) -> None:
        """Scenario 10: Automatically deletes provisioned role workspaces upon clean convergence."""
        tmp_dir = tempfile.mkdtemp()
        try:
            fake_reg = FakeWorkspaceRegistry([self.spec_role_high], base_dir=tmp_dir)
            ws_dir = os.path.join(tmp_dir, "high_pkg_a")
            fake_work = FakeWorkspaceWorkManager({
                "high": (([_make_item("high/unit.md", "high")], ())),
            })
            self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
            self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

            class CleanupHarness(FakeHarnessAdapter):
                def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
                    os.makedirs(ws_dir, exist_ok=True)
                    fake_work.queue_data["high"] = ((), ())
                    return "h_high"

            harness = CleanupHarness({
                "h_high": subagent_coordinator.RoleRoundResult(
                    role="high",
                    status="clean",
                    submitted_targets=("high/unit.md",),
                ),
            })

            with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
                coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
                summary = coord.orchestrate("pkg_a", harness, poll_interval=0.001)
                self.assertTrue(summary.is_converged)
                self.assertFalse(os.path.exists(ws_dir))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_dynamic_polling_with_delayed_worker(self) -> None:
        """Scenario 4: Continuous non-blocking polling and dynamic supervisor loop."""
        fake_reg = FakeWorkspaceRegistry([self.spec_role_high])
        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item("high/unit.md", "high")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        poll_calls = 0

        class PollingHarness(FakeHarnessAdapter):
            def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleRoundResult]:
                nonlocal poll_calls
                poll_calls += 1
                if poll_calls < 2:
                    return None
                fake_work.queue_data["high"] = ((), ())
                return subagent_coordinator.RoleRoundResult(
                    role="high",
                    status="clean",
                    submitted_targets=("high/unit.md",),
                )

        harness = PollingHarness()

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            summary = coord.orchestrate("pkg_a", harness, poll_interval=0.001)
            self.assertTrue(summary.is_converged)
            self.assertGreaterEqual(poll_calls, 2)
            self.assertEqual(summary.submitted_count, 1)

    def test_orchestrate_restricts_to_target_node_boundary(self) -> None:
        """Scenario 10: Restricting execution to a target unit and its transitive dependencies."""
        fake_reg = FakeWorkspaceRegistry([self.spec_role_high])
        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item("high/unit.md", "high")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        class SingleRoundHarness(FakeHarnessAdapter):
            def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleRoundResult]:
                fake_work.queue_data["high"] = ((), ())
                return subagent_coordinator.RoleRoundResult(
                    role="high",
                    status="clean",
                    submitted_targets=("high/unit.md",),
                )

        harness = SingleRoundHarness()

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            summary = coord.orchestrate("pkg_a", harness, poll_interval=0.001, target_node="//pkg_a/parts/mod:unit#high")
            self.assertTrue(summary.is_converged)
            self.assertEqual(fake_work.last_target_unit, "//pkg_a/parts/mod:unit#high")

    def test_orchestrate_halts_upon_consecutive_unproductive_rounds(self) -> None:
        """Scenario 10: Halting orchestration upon consecutive unproductive round impasse."""
        fake_reg = FakeWorkspaceRegistry([self.spec_role_high])
        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item("high/unit.md", "high")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        class UnproductiveHarness(FakeHarnessAdapter):
            def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleRoundResult]:
                return subagent_coordinator.RoleRoundResult(
                    role="high",
                    status="unresolved",
                    submitted_targets=(),
                    blamed_targets=(),
                )

        harness = UnproductiveHarness()

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            summary = coord.orchestrate(
                "pkg_a",
                harness,
                poll_interval=0.001,
                max_unproductive_rounds=2,
            )
            self.assertFalse(summary.is_converged)
            self.assertIn("made no progress (0 submitted, 0 blamed) for 2 consecutive rounds", summary.status_message)
            self.assertEqual(summary.total_waves, 2)
            self.assertEqual(harness.dispatches[0].task_prompt, "")
            self.assertIn("CRITICAL REMINDER", harness.dispatches[1].task_prompt)

    def test_orchestrate_unproductive_rounds_defaults_to_five(self) -> None:
        """Scenario 10: Unconfigured max_unproductive_rounds defaults to 5 rounds before halting."""
        fake_reg = FakeWorkspaceRegistry([self.spec_role_high])
        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item("high/unit.md", "high")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        class UnproductiveHarness(FakeHarnessAdapter):
            def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleRoundResult]:
                return subagent_coordinator.RoleRoundResult(
                    role="high",
                    status="unresolved",
                    submitted_targets=(),
                    blamed_targets=(),
                )

        harness = UnproductiveHarness()

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            summary = coord.orchestrate(
                "pkg_a",
                harness,
                poll_interval=0.001,
            )
            self.assertFalse(summary.is_converged)
            self.assertIn("made no progress (0 submitted, 0 blamed) for 5 consecutive rounds", summary.status_message)
            self.assertEqual(summary.total_waves, 5)

    def test_orchestrate_unproductive_rounds_suppressed_when_targets_resolved(self) -> None:
        """Scenario 10 & 12: MUST suppress unproductive rounds and scolding reminders when assigned targets are resolved in repository."""
        fake_reg = FakeWorkspaceRegistry([self.spec_role_high])
        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item("high/unit.md", "high")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        class ResolvingUnproductiveHarness(FakeHarnessAdapter):
            def __init__(self, work_mgr: FakeWorkspaceWorkManager) -> None:
                super().__init__()
                self.work_mgr = work_mgr

            def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleRoundResult]:
                # Simulate harness failing to recognize submission (0 submitted, 0 blamed),
                # but target was actually cleaned/resolved in the repository during the round
                self.work_mgr.queue_data["high"] = ((), ())
                return subagent_coordinator.RoleRoundResult(
                    role="high",
                    status="unresolved",
                    submitted_targets=(),
                    blamed_targets=(),
                )

        harness = ResolvingUnproductiveHarness(fake_work)

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            summary = coord.orchestrate(
                "pkg_a",
                harness,
                poll_interval=0.001,
                max_unproductive_rounds=2,
            )
            self.assertTrue(summary.is_converged)
            self.assertEqual(summary.total_waves, 1)
            self.assertEqual(harness.dispatches[0].task_prompt, "")

    def test_orchestrate_unproductive_rounds_resets_and_omits_reminder_when_resolved(self) -> None:
        """Scenario 10 & 12: MUST reset unproductive count and omit reminder on subsequent dispatch when resolved."""
        fake_reg = FakeWorkspaceRegistry([self.spec_role_high])
        fake_work = FakeWorkspaceWorkManager({
            "high": ([_make_item("high/unit_a.md", "high")], ()),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        call_count = [0]

        class MultiRoundResolvingHarness(FakeHarnessAdapter):
            def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleRoundResult]:
                call_count[0] += 1
                if call_count[0] == 1:
                    # Unit A was resolved, now Unit B is ready
                    fake_work.queue_data["high"] = ([_make_item("high/unit_b.md", "high")], ())
                    return subagent_coordinator.RoleRoundResult(
                        role="high",
                        status="unresolved",
                        submitted_targets=(),
                        blamed_targets=(),
                    )
                else:
                    # Unit B is submitted
                    fake_work.queue_data["high"] = ((), ())
                    return subagent_coordinator.RoleRoundResult(
                        role="high",
                        status="clean",
                        submitted_targets=("high/unit_b.md",),
                        blamed_targets=(),
                    )

        harness = MultiRoundResolvingHarness()

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            summary = coord.orchestrate(
                "pkg_a",
                harness,
                poll_interval=0.001,
                max_unproductive_rounds=2,
            )
            self.assertTrue(summary.is_converged)
            self.assertEqual(summary.total_waves, 2)
            # Dispatch 2 must NOT have the critical reminder scolding directive
            self.assertEqual(harness.dispatches[0].task_prompt, "")
            self.assertEqual(harness.dispatches[1].task_prompt, "")

    def test_resolve_model_parameters_extracts_unproductive_rounds(self) -> None:
        """Requirement: MUST resolve batch size, timeout, and max unproductive rounds from model configuration."""
        tmp_dir = tempfile.mkdtemp()
        try:
            cfg_file = os.path.join(tmp_dir, "model_configs.toml")
            with open(cfg_file, "w", encoding="utf-8") as f:
                f.write('max_unproductive_rounds = 7\n\n[models.moe_model]\nbatch_size = 4\nconversation_max_tokens = 45000\nmax_unproductive_rounds = 12\n')

            batch, tokens, unprod = resolve_model_parameters(tmp_dir, "moe_model")
            self.assertEqual(batch, 4)
            self.assertEqual(tokens, 45000)
            self.assertEqual(unprod, 12)

            # Test top-level fallback
            batch2, tokens2, unprod2 = resolve_model_parameters(tmp_dir, "unknown_model")
            self.assertIsNone(batch2)
            self.assertIsNone(tokens2)
            self.assertEqual(unprod2, 7)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_resolve_model_parameters_falls_back_to_candidate_config(self) -> None:
        """Requirement: MUST resolve model configuration from candidate path when absent in repo root."""
        tmp_dir = tempfile.mkdtemp()
        cand_dir = tempfile.mkdtemp()
        old_env = os.environ.get("CLEANROOM_MODEL_CONFIG_FILE")
        try:
            cand_cfg = os.path.join(cand_dir, "model_configs.toml")
            with open(cand_cfg, "w", encoding="utf-8") as f:
                f.write('[models.qwen_test]\nsubagent_batch_size = 3\nconversation_max_tokens = 96000\nmax_unproductive_rounds = 3\n')
            os.environ["CLEANROOM_MODEL_CONFIG_FILE"] = cand_cfg

            batch, tokens, unprod = resolve_model_parameters(tmp_dir, "qwen_test")
            self.assertEqual(batch, 3)
            self.assertEqual(tokens, 96000)
            self.assertEqual(unprod, 3)
        finally:
            if old_env is not None:
                os.environ["CLEANROOM_MODEL_CONFIG_FILE"] = old_env
            else:
                os.environ.pop("CLEANROOM_MODEL_CONFIG_FILE", None)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            shutil.rmtree(cand_dir, ignore_errors=True)

    def test_stress_multi_wave_deep_diamond_and_star_dependency_hierarchy(self) -> None:
        """Requirement: MUST iterate through multi-wave deep diamond and star dependency hierarchies until convergence."""
        fake_reg = FakeWorkspaceRegistry([
            self.spec_role_high,
            self.spec_role_planning,
            self.spec_role_low,
            self.impl_role_lib,
            self.impl_role_test,
            self.role_qa,
        ])

        # 13 targets total across 5 roles
        high_targets = ("high/core.md", "high/utils.md")
        planning_targets = ("planning/core.md", "planning/utils.md", "planning/aggregator.md")
        low_targets = ("low/core.pyi", "low/utils.pyi", "low/aggregator.pyi")
        lib_targets = ("lib/core.py", "lib/utils.py", "lib/aggregator.py")
        test_targets = ("tests/core_test.py", "tests/utils_test.py", "tests/aggregator_test.py")
        qa_targets = ("qa/report.md",)

        # Initial queue: high is ready; all downstream are blocked
        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item(t, "high") for t in high_targets], ())),
            "planning": (((), [_make_item(t, "planning", is_ready=False) for t in planning_targets])),
            "low": (((), [_make_item(t, "low", is_ready=False) for t in low_targets])),
            "lib": (((), [_make_item(t, "lib", is_ready=False) for t in lib_targets])),
            "test": (((), [_make_item(t, "test", is_ready=False) for t in test_targets])),
            "qa": (((), [_make_item(t, "qa", is_ready=False) for t in qa_targets])),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        dispatched_order: List[str] = []

        class StressMultiWaveHarness(FakeHarnessAdapter):
            def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
                dispatched_order.append(dispatch.role_name)
                return f"h_{dispatch.role_name}"

            def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleRoundResult]:
                role = task_handle.replace("h_", "")
                if role == "high":
                    fake_work.queue_data["high"] = ((), ())
                    fake_work.queue_data["planning"] = (([_make_item(t, "planning") for t in planning_targets], ()))
                    return subagent_coordinator.RoleRoundResult(
                        role="high",
                        status="clean",
                        submitted_targets=high_targets,
                        telemetry=subagent_coordinator.TokenUsage(100, 20, 30, 150, 0.002),
                    )
                elif role == "planning":
                    fake_work.queue_data["planning"] = ((), ())
                    fake_work.queue_data["low"] = (([_make_item(t, "low") for t in low_targets], ()))
                    return subagent_coordinator.RoleRoundResult(
                        role="planning",
                        status="clean",
                        submitted_targets=planning_targets,
                        telemetry=subagent_coordinator.TokenUsage(200, 50, 60, 310, 0.004),
                    )
                elif role == "low":
                    fake_work.queue_data["low"] = ((), ())
                    fake_work.queue_data["lib"] = (([_make_item(t, "lib") for t in lib_targets], ()))
                    fake_work.queue_data["test"] = (([_make_item(t, "test") for t in test_targets], ()))
                    return subagent_coordinator.RoleRoundResult(
                        role="low",
                        status="clean",
                        submitted_targets=low_targets,
                        telemetry=subagent_coordinator.TokenUsage(300, 80, 90, 470, 0.006),
                    )
                elif role == "lib":
                    fake_work.queue_data["lib"] = ((), ())
                    # QA remains blocked until test also completes
                    if not fake_work.queue_data["test"][0]:
                        fake_work.queue_data["qa"] = (([_make_item(t, "qa") for t in qa_targets], ()))
                    return subagent_coordinator.RoleRoundResult(
                        role="lib",
                        status="clean",
                        submitted_targets=lib_targets,
                        telemetry=subagent_coordinator.TokenUsage(400, 100, 120, 620, 0.008),
                    )
                elif role == "test":
                    fake_work.queue_data["test"] = ((), ())
                    # QA unblocks when lib is also clean
                    if not fake_work.queue_data["lib"][0]:
                        fake_work.queue_data["qa"] = (([_make_item(t, "qa") for t in qa_targets], ()))
                    return subagent_coordinator.RoleRoundResult(
                        role="test",
                        status="clean",
                        submitted_targets=test_targets,
                        telemetry=subagent_coordinator.TokenUsage(400, 100, 120, 620, 0.008),
                    )
                elif role == "qa":
                    fake_work.queue_data["qa"] = ((), ())
                    return subagent_coordinator.RoleRoundResult(
                        role="qa",
                        status="clean",
                        submitted_targets=qa_targets,
                        telemetry=subagent_coordinator.TokenUsage(150, 30, 40, 220, 0.003),
                    )
                return None

        harness = StressMultiWaveHarness()

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            summary = coord.orchestrate("pkg_a", harness, poll_interval=0.001)

            self.assertTrue(summary.is_converged)
            self.assertEqual(summary.submitted_count, 15)
            self.assertEqual(summary.blamed_count, 0)
            self.assertEqual(summary.total_waves, 5)
            # High was dispatched first, then planning, then low, then lib & test concurrently, then qa
            self.assertEqual(dispatched_order[0], "high")
            self.assertEqual(dispatched_order[1], "planning")
            self.assertEqual(dispatched_order[2], "low")
            self.assertIn("lib", dispatched_order[3:5])
            self.assertIn("test", dispatched_order[3:5])
            self.assertEqual(dispatched_order[5], "qa")
            self.assertGreater(summary.total_telemetry.total_tokens, 0)
            self.assertGreater(summary.total_telemetry.cost_usd, 0.0)

    def test_stress_upstream_blame_feedback_propagation_across_wave_barriers(self) -> None:
        """Requirement: MUST propagate blame defects across wave barriers, blocking dependents until fixed."""
        fake_reg = FakeWorkspaceRegistry([
            self.spec_role_high,
            self.spec_role_low,
            self.impl_role_lib,
        ])

        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item("high/core.md", "high")], ())),
            "low": (((), [_make_item("low/core.pyi", "low", is_ready=False)])),
            "lib": (((), [_make_item("lib/core.py", "lib", is_ready=False)])),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        lib_rounds = 0
        low_rounds = 0

        class BlameHarness(FakeHarnessAdapter):
            def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleRoundResult]:
                nonlocal lib_rounds, low_rounds
                role = task_handle.replace("handle_", "")
                if role == "high":
                    fake_work.queue_data["high"] = ((), ())
                    fake_work.queue_data["low"] = (([_make_item("low/core.pyi", "low")], ()))
                    return subagent_coordinator.RoleRoundResult(
                        role="high",
                        status="clean",
                        submitted_targets=("high/core.md",),
                    )
                elif role == "low":
                    low_rounds += 1
                    fake_work.queue_data["low"] = ((), ())
                    fake_work.queue_data["lib"] = (([_make_item("lib/core.py", "lib")], ()))
                    return subagent_coordinator.RoleRoundResult(
                        role="low",
                        status="clean",
                        submitted_targets=("low/core.pyi",),
                    )
                elif role == "lib":
                    lib_rounds += 1
                    if lib_rounds == 1:
                        # Round 1 blames low for missing contract specification
                        fake_work.queue_data["lib"] = (((), [_make_item("lib/core.py", "lib", is_ready=False)]))
                        fake_work.queue_data["low"] = (([_make_item("low/core.pyi", "low")], ()))
                        return subagent_coordinator.RoleRoundResult(
                            role="lib",
                            status="blamed",
                            submitted_targets=(),
                            blamed_targets=("low/core.pyi",),
                        )
                    else:
                        # Round 2 completes cleanly after low has been fixed
                        fake_work.queue_data["lib"] = ((), ())
                        return subagent_coordinator.RoleRoundResult(
                            role="lib",
                            status="clean",
                            submitted_targets=("lib/core.py",),
                        )
                return None

        harness = BlameHarness()

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            summary = coord.orchestrate("pkg_a", harness, poll_interval=0.001)

            self.assertTrue(summary.is_converged)
            self.assertEqual(summary.blamed_count, 1)
            self.assertEqual(summary.submitted_count, 4)  # high (1), low (1), low fix (1), lib clean (1)
            self.assertEqual(low_rounds, 2)  # low ran initially and then ran again to fix blame
            self.assertEqual(lib_rounds, 2)  # lib ran, blamed, then ran again to submit

    def test_stress_wave_barriers_block_downstream_until_all_parallel_prerequisites_succeed(self) -> None:
        """Requirement: MUST enforce wave barriers preventing downstream execution until all parallel dependencies succeed."""
        fake_reg = FakeWorkspaceRegistry([
            self.impl_role_lib,
            self.impl_role_test,
            self.role_qa,
        ])

        fake_work = FakeWorkspaceWorkManager({
            "lib": (([_make_item("lib/unit.py", "lib")], ())),
            "test": (([_make_item("tests/unit_test.py", "test")], ())),
            "qa": (((), [_make_item("qa/report.md", "qa", is_ready=False)])),
        })
        self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        test_poll_count = 0
        qa_dispatched_too_early = False

        class BarrierHarness(FakeHarnessAdapter):
            def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
                nonlocal qa_dispatched_too_early
                if dispatch.role_name == "qa":
                    # If qa is dispatched while test is still not finished, barrier was violated
                    if fake_work.queue_data["test"][0] or test_poll_count < 2:
                        qa_dispatched_too_early = True
                return super().dispatch_role(dispatch)

            def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleRoundResult]:
                nonlocal test_poll_count
                role = task_handle.replace("handle_", "")
                if role == "lib":
                    fake_work.queue_data["lib"] = ((), ())
                    return subagent_coordinator.RoleRoundResult(
                        role="lib",
                        status="clean",
                        submitted_targets=("lib/unit.py",),
                    )
                elif role == "test":
                    test_poll_count += 1
                    if test_poll_count < 2:
                        # test still executing during first poll
                        return None
                    fake_work.queue_data["test"] = ((), ())
                    fake_work.queue_data["qa"] = (([_make_item("qa/report.md", "qa")], ()))
                    return subagent_coordinator.RoleRoundResult(
                        role="test",
                        status="clean",
                        submitted_targets=("tests/unit_test.py",),
                    )
                elif role == "qa":
                    fake_work.queue_data["qa"] = ((), ())
                    return subagent_coordinator.RoleRoundResult(
                        role="qa",
                        status="clean",
                        submitted_targets=("qa/report.md",),
                    )
                return None

        harness = BarrierHarness()

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            summary = coord.orchestrate("pkg_a", harness, poll_interval=0.001)

            self.assertTrue(summary.is_converged)
            self.assertFalse(qa_dispatched_too_early)
            self.assertEqual(summary.submitted_count, 3)

    def test_stress_orphan_workspaces_decommissioned_and_workers_interrupted_on_cancellation(self) -> None:
        """Requirement: MUST interrupt active workers and delete provisioned workspaces when cancelled."""
        tmp_dir = tempfile.mkdtemp()
        try:
            ws_high = os.path.join(tmp_dir, "high_pkg_a")
            ws_low = os.path.join(tmp_dir, "low_pkg_a")
            os.makedirs(ws_high, exist_ok=True)
            os.makedirs(ws_low, exist_ok=True)

            fake_reg = FakeWorkspaceRegistry(
                [self.spec_role_high, self.spec_role_low],
                base_dir=tmp_dir,
            )
            fake_work = FakeWorkspaceWorkManager({
                "high": (([_make_item("high/core.md", "high")], ())),
                "low": (((), [_make_item("low/core.pyi", "low", is_ready=False)])),
            })
            self.registry.register_instance(fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
            self.registry.register_instance(fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

            class CancelHarness(FakeHarnessAdapter):
                def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleRoundResult]:
                    # Re-create ws_low as if provisioned during execution
                    os.makedirs(ws_low, exist_ok=True)
                    # Simulate user cancellation via SIGINT (KeyboardInterrupt)
                    raise KeyboardInterrupt("Simulated Ctrl+C cancellation")

            harness = CancelHarness()

            with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
                coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
                with self.assertRaises(KeyboardInterrupt):
                    coord.orchestrate("pkg_a", harness, poll_interval=0.001, repo_root=tmp_dir)

            # Assert running worker was interrupted
            self.assertIn("handle_high", harness.interrupted)
            # Assert orphan workspaces were cleanly decommissioned from disk
            self.assertFalse(os.path.exists(ws_high))
            self.assertFalse(os.path.exists(ws_low))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-18T19:13:51Z
# LAST_CHANGED: 2026-10-20T23:50:00Z
# CHANGE: Test suppression of unproductive rounds and scolding reminders when assigned targets are resolved
# COVERAGE_AUDIT: 2026-10-18T19:13:51Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
