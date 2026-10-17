# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_coordinator_impl unit tests
# CODE_HASH: 3777a0383a21
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Unit tests for subagent_coordinator_impl."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from typing import Dict, List, Optional, Sequence, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.subagent.lib import subagent_coordinator
from update_with_ai.parts.subagent.lib.subagent_coordinator_impl import (
    SubagentCoordinator,
    __initialize__,
    _resolve_model_parameters,
)
from update_with_ai.parts.tools.lib import workspace_work
from update_with_ai.parts.workspace.lib import (
    workspace_provision,
    workspace_registry,
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
    ) -> workspace_registry.WorkspaceDescriptor:
        self.commissioned.append((role_name, dir_scope))
        ws_dir = custom_dest or f"/repo/cleanroom/.workspaces/{role_name}_{dir_scope}"
        r_def = workspace_registry.RoleDefinition(
            role_name=role_name,
            guide_path=f"guides/{role_name}.md",
            writable_file_patterns=[],
            readonly_file_patterns=[],
            feedback_role_deps=[],
        )
        return workspace_registry.WorkspaceDescriptor(
            workspace_dir=ws_dir,
            main_repository_root="/repo/cleanroom",
            role_definition=r_def,
            directory_scope=dir_scope,
        )


class FakeWorkspaceRegistry:
    """Test double implementing WorkspaceRegistry protocol."""

    tier = agent_session.agent_session

    def __init__(self, roles: Sequence[workspace_registry.RoleDefinition], base_dir: Optional[str] = None) -> None:
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
    ) -> workspace_registry.RoleDefinition:
        clean = role_name_or_address.split(":")[-1].strip().lower()
        if clean in self.role_map:
            return self.role_map[clean]
        raise KeyError(f"Role '{clean}' not found")

    def list_roles(
        self,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Sequence[workspace_registry.RoleDefinition]:
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

    def record_workspace(self, descriptor: workspace_registry.WorkspaceDescriptor, repo_root: Optional[str] = None) -> None:
        pass

    def unregister_workspace(self, workspace_dir: str, repo_root: Optional[str] = None) -> bool:
        return True

    def load_active_workspaces(self, repo_root: Optional[str] = None) -> Sequence[workspace_registry.WorkspaceDescriptor]:
        return ()


class FakeWorkspaceWorkManager:
    """Test double implementing WorkspaceWorkManager protocol."""

    tier = agent_session.agent_session

    def __init__(
        self,
        queue_data: Optional[Dict[str, Tuple[Sequence[workspace_work.WorkQueueItem], Sequence[workspace_work.WorkQueueItem]]]] = None,
    ) -> None:
        self.queue_data = queue_data or {}
        self.pending: Dict[str, List[str]] = {}

    def compute_role_work_queue(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: str,
    ) -> Tuple[Sequence[workspace_work.WorkQueueItem], Sequence[workspace_work.WorkQueueItem]]:
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

    def __init__(self, scripted_results: Optional[Dict[str, subagent_coordinator.RoleTurnResult]] = None) -> None:
        self.scripted_results = scripted_results or {}
        self.dispatches: List[subagent_coordinator.RoleDispatch] = []
        self.interrupted: List[str] = []

    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        self.dispatches.append(dispatch)
        return f"handle_{dispatch.role_name}"

    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        if task_handle in self.scripted_results:
            return self.scripted_results[task_handle]
        role = task_handle.replace("handle_", "")
        return subagent_coordinator.RoleTurnResult(
            role=role,
            status="clean",
            submitted_targets=("target.py",),
            telemetry=subagent_coordinator.TokenUsage(100, 50, 20, 170, 0.001),
        )

    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
        return self.await_role(task_handle)

    def interrupt_role(self, task_handle: str) -> None:
        self.interrupted.append(task_handle)


def _make_item(target_file: str, role_name: str, is_ready: bool = True) -> workspace_work.WorkQueueItem:
    return workspace_work.WorkQueueItem(
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
            keys=[workspace_provision.WorkspaceProvisioner],
            tier=agent_session.agent_session,
        )

        self.spec_role_high = workspace_registry.RoleDefinition(
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
        self.spec_role_low = workspace_registry.RoleDefinition(
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
        self.impl_role_lib = workspace_registry.RoleDefinition(
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
        self.impl_role_test = workspace_registry.RoleDefinition(
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
        self.registry.register_instance(fake_reg, keys=[workspace_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[workspace_work.WorkspaceWorkManager], tier=agent_session.agent_session)

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
        self.registry.register_instance(fake_reg, keys=[workspace_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[workspace_work.WorkspaceWorkManager], tier=agent_session.agent_session)

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
        self.registry.register_instance(fake_reg, keys=[workspace_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[workspace_work.WorkspaceWorkManager], tier=agent_session.agent_session)

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
        self.registry.register_instance(fake_reg, keys=[workspace_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[workspace_work.WorkspaceWorkManager], tier=agent_session.agent_session)

        class ConvergenceHarness(FakeHarnessAdapter):
            def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
                fake_work.queue_data["lib"] = ((), ())
                return super().dispatch_role(dispatch)

        harness = ConvergenceHarness({
            "handle_lib": subagent_coordinator.RoleTurnResult(
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
        """Scenario 5: Execution terminates early when a subagent turn reports failure."""
        fake_reg = FakeWorkspaceRegistry([self.spec_role_high, self.spec_role_low])
        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item("high/unit.md", "high")], ())),
            "low": (([_make_item("low/unit.pyi", "low")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[workspace_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[workspace_work.WorkspaceWorkManager], tier=agent_session.agent_session)

        harness = FakeHarnessAdapter({
            "handle_high": subagent_coordinator.RoleTurnResult(
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
        self.registry.register_instance(fake_reg, keys=[workspace_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[workspace_work.WorkspaceWorkManager], tier=agent_session.agent_session)

        class AggregationHarness(FakeHarnessAdapter):
            def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
                fake_work.queue_data[dispatch.role_name] = ((), ())
                return super().dispatch_role(dispatch)

        harness = AggregationHarness({
            "handle_lib": subagent_coordinator.RoleTurnResult(
                role="lib",
                status="clean",
                submitted_targets=("lib/unit.py",),
                telemetry=subagent_coordinator.TokenUsage(1000, 500, 200, 1700, 0.015),
            ),
            "handle_test": subagent_coordinator.RoleTurnResult(
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
        """Scenario 7: Commissions absent role workspace via workspace_provision before dispatch."""
        fake_reg = FakeWorkspaceRegistry([self.spec_role_high])
        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item("high/unit.md", "high")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[workspace_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[workspace_work.WorkspaceWorkManager], tier=agent_session.agent_session)

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
        self.registry.register_instance(fake_reg, keys=[workspace_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[workspace_work.WorkspaceWorkManager], tier=agent_session.agent_session)

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
            self.registry.register_instance(fake_reg, keys=[workspace_registry.WorkspaceRegistry], tier=agent_session.agent_session)
            self.registry.register_instance(fake_work, keys=[workspace_work.WorkspaceWorkManager], tier=agent_session.agent_session)

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
            self.registry.register_instance(fake_reg, keys=[workspace_registry.WorkspaceRegistry], tier=agent_session.agent_session)
            self.registry.register_instance(fake_work, keys=[workspace_work.WorkspaceWorkManager], tier=agent_session.agent_session)

            class CleanupHarness(FakeHarnessAdapter):
                def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
                    os.makedirs(ws_dir, exist_ok=True)
                    fake_work.queue_data["high"] = ((), ())
                    return "h_high"

            harness = CleanupHarness({
                "h_high": subagent_coordinator.RoleTurnResult(
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
        self.registry.register_instance(fake_reg, keys=[workspace_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[workspace_work.WorkspaceWorkManager], tier=agent_session.agent_session)

        poll_calls = 0

        class PollingHarness(FakeHarnessAdapter):
            def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
                nonlocal poll_calls
                poll_calls += 1
                if poll_calls < 2:
                    return None
                fake_work.queue_data["high"] = ((), ())
                return subagent_coordinator.RoleTurnResult(
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

    def test_orchestrate_halts_upon_consecutive_unproductive_turns(self) -> None:
        """Scenario 10: Halting orchestration upon consecutive unproductive turn impasse."""
        fake_reg = FakeWorkspaceRegistry([self.spec_role_high])
        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item("high/unit.md", "high")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[workspace_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[workspace_work.WorkspaceWorkManager], tier=agent_session.agent_session)

        class UnproductiveHarness(FakeHarnessAdapter):
            def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
                return subagent_coordinator.RoleTurnResult(
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
                max_unproductive_turns=2,
            )
            self.assertFalse(summary.is_converged)
            self.assertIn("made no progress (0 submitted, 0 blamed) for 2 consecutive turns", summary.status_message)
            self.assertEqual(summary.total_waves, 2)

    def test_orchestrate_unproductive_turns_defaults_to_five(self) -> None:
        """Scenario 10: Unconfigured max_unproductive_turns defaults to 5 turns before halting."""
        fake_reg = FakeWorkspaceRegistry([self.spec_role_high])
        fake_work = FakeWorkspaceWorkManager({
            "high": (([_make_item("high/unit.md", "high")], ())),
        })
        self.registry.register_instance(fake_reg, keys=[workspace_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(fake_work, keys=[workspace_work.WorkspaceWorkManager], tier=agent_session.agent_session)

        class UnproductiveHarness(FakeHarnessAdapter):
            def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
                return subagent_coordinator.RoleTurnResult(
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
            self.assertIn("made no progress (0 submitted, 0 blamed) for 5 consecutive turns", summary.status_message)
            self.assertEqual(summary.total_waves, 5)

    def test_resolve_model_parameters_extracts_unproductive_turns(self) -> None:
        """Requirement: MUST resolve batch size, timeout, and max unproductive turns from model configuration."""
        tmp_dir = tempfile.mkdtemp()
        try:
            cfg_file = os.path.join(tmp_dir, "model_configs.toml")
            with open(cfg_file, "w", encoding="utf-8") as f:
                f.write('max_unproductive_turns = 7\n\n[models.moe_model]\nbatch_size = 4\nconversation_max_tokens = 45000\nmax_unproductive_turns = 12\n')

            batch, tokens, unprod = _resolve_model_parameters(tmp_dir, "moe_model")
            self.assertEqual(batch, 4)
            self.assertEqual(tokens, 45000)
            self.assertEqual(unprod, 12)

            # Test top-level fallback
            batch2, tokens2, unprod2 = _resolve_model_parameters(tmp_dir, "unknown_model")
            self.assertIsNone(batch2)
            self.assertIsNone(tokens2)
            self.assertEqual(unprod2, 7)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

