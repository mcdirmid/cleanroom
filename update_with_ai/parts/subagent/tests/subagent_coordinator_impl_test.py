# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:37Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_coordinator_impl unit tests
# CODE_HASH: 11430ed98755
# COVERAGE_AUDIT: 2026-10-12T23:37:37Z
# QA_AUDIT: 2026-10-12T23:37:36Z
# --- END CLEANROOM METADATA ---

"""Unit tests for subagent_coordinator_impl."""

from __future__ import annotations

import unittest
from typing import Dict, List, Optional, Sequence, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.subagent.lib import subagent_coordinator
from update_with_ai.parts.subagent.lib.subagent_coordinator_impl import (
    SubagentCoordinator,
    __initialize__,
)
from update_with_ai.parts.workspace.lib import (
    workspace_provision,
    workspace_registry,
    workspace_work,
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

    def __init__(self, roles: Sequence[workspace_registry.RoleDefinition]) -> None:
        self.roles = list(roles)
        self.role_map = {r.role_name: r for r in self.roles}

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

        harness = FakeHarnessAdapter()

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)

            # In round 1, lib has work; after wave 1, work queue clears
            def mock_run_wave(wave, h):
                fake_work.queue_data["lib"] = ((), ())
                return (subagent_coordinator.RoleTurnResult(
                    role="lib",
                    status="clean",
                    submitted_targets=("lib/unit.py",),
                    telemetry=subagent_coordinator.TokenUsage(100, 20, 50, 170, 0.005),
                ),)

            coord.run_wave = mock_run_wave  # type: ignore

            summary = coord.orchestrate("pkg_a", harness)
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
            summary = coord.orchestrate("pkg_a", harness)
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

        harness = FakeHarnessAdapter({
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

            def mock_run_wave(wave, h):
                fake_work.queue_data["lib"] = ((), ())
                fake_work.queue_data["test"] = ((), ())
                return (
                    h.await_role("handle_lib"),
                    h.await_role("handle_test"),
                )

            coord.run_wave = mock_run_wave  # type: ignore

            summary = coord.orchestrate("pkg_a", harness)
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


if __name__ == "__main__":
    unittest.main()
