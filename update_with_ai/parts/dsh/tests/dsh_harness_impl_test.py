# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-13T20:00:00Z
# CHANGE: author dsh_harness_impl unit tests
# CODE_HASH: 245befc36e28
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Unit tests for dsh_harness_impl."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Sequence

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.dsh.lib import dsh_asm, dsh_harness
from update_with_ai.parts.dsh.lib.dsh_harness_impl import (
    DshHarnessAdapter,
    DshHarnessManager,
    __initialize__,
)
from update_with_ai.parts.subagent.lib import subagent_coordinator, subagent_harness
from update_with_ai.parts.tools.lib import workspace_work
from update_with_ai.parts.workspace.lib import workspace_registry


class MockHarnessRegistry:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.installed: dict[str, Any] = {}

    def install_harness(self, platform_name: str, factory: Any) -> None:
        self.installed[platform_name] = factory


class FakeWorkspaceRegistry:
    tier = agent_session.agent_session

    def resolve_role_definition(
        self,
        role_name_or_address: str,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> workspace_registry.RoleDefinition:
        clean = role_name_or_address.split(":")[-1].strip().lower()
        if clean in ("qa", "coverage", "spec_qa"):
            return workspace_registry.RoleDefinition(
                role_name=clean,
                guide_path=f"guides/{clean}.md",
                writable_file_patterns=[],
                readonly_file_patterns=[],
                feedback_role_deps=[],
            )
        return workspace_registry.RoleDefinition(
            role_name=clean,
            guide_path=f"guides/{clean}.md",
            writable_file_patterns=[f"{clean}/*"],
            readonly_file_patterns=[],
            feedback_role_deps=[],
        )


class FakeWorkspaceWorkManager:
    """Test double implementing WorkspaceWorkManager for dsh harness tests."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.pending: Dict[str, List[str]] = {}

    def get_pending_work(self, workspace_dir: str) -> List[str]:
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


class DshHarnessImplTest(unittest.TestCase):
    """Test cases for DshTelemetryParser, DshHarnessAdapter, and DshHarnessManager."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        dsh_asm.__initialize__(self.registry)
        self.mock_harness_registry = MockHarnessRegistry()
        self.registry.register_instance(
            self.mock_harness_registry,
            keys=[subagent_harness.HarnessRegistry],
            tier=agent_session.agent_session,
        )
        self.workspace_reg = FakeWorkspaceRegistry()
        self.registry.register_instance(
            self.workspace_reg,
            keys=[workspace_registry.WorkspaceRegistry],
            tier=agent_session.agent_session,
        )
        self.work_mgr = FakeWorkspaceWorkManager()
        self.registry.register_instance(
            self.work_mgr,
            keys=[workspace_work.WorkspaceWorkManager],
            tier=agent_session.agent_session,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)
    def test_dispatch_and_await_clean_turn_in_simulation(self) -> None:
        """Requirement: MUST execute turn and return clean status when work is completed."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=True,
            )

            # Setup pending work before turn
            self.work_mgr.set_pending_work(self.test_dir, ["high/unit_a.md", "high/unit_b.md"])

            dispatch = subagent_coordinator.RoleDispatch(
                role_name="high",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("high/unit_a.md",),
                batch_size=3,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)
            self.assertTrue(handle.startswith("dsh_high_"))

            # Simulate agent submitting target unit_a
            self.work_mgr.remove_pending_target(self.test_dir, "high/unit_a.md")

            result = adapter.await_role(handle)
            self.assertEqual(result.role, "high")
            self.assertEqual(result.status, "clean")
            self.assertEqual(result.submitted_targets, ("high/unit_a.md",))
            self.assertEqual(result.blamed_targets, ())

    def test_dispatch_and_await_blamed_turn_in_simulation(self) -> None:
        """Requirement: MUST return blamed status when blame buffer contains culprits."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=True,
            )

            self.work_mgr.set_pending_work(self.test_dir, ["low/unit_a.pyi"])

            # Write culprit file into blame buffer
            blame_buf = os.path.join(self.test_dir, ".cleanroom_blame_buffer.json")
            with open(blame_buf, "w", encoding="utf-8") as f:
                json.dump(["scenarios/unit_a.md"], f)

            dispatch = subagent_coordinator.RoleDispatch(
                role_name="low",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("low/unit_a.pyi",),
                batch_size=3,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)
            result = adapter.await_role(handle)

            self.assertEqual(result.role, "low")
            self.assertEqual(result.status, "blamed")
            self.assertEqual(result.blamed_targets, ("scenarios/unit_a.md",))

    def test_poll_role_in_simulation(self) -> None:
        """Requirement: MUST return completed turn result immediately in simulation mode."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=True,
            )

            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/unit_a.py",),
                batch_size=3,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)
            res = adapter.poll_role(handle)
            self.assertIsNotNone(res)
            assert res is not None
            self.assertEqual(res.role, "lib")
            self.assertEqual(res.status, "unresolved")

    def test_dsh_harness_manager_singleton(self) -> None:
        """Requirement: MUST construct configured DshHarnessAdapter instances from manager."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            mgr = scope.get_singleton(dsh_harness.DshHarnessManager)
            adapter = mgr.create_harness_adapter(
                model_name="DeepSeek-V41-Flash",
                timeout_seconds=120.0,
            )
            parser = mgr.get_telemetry_parser()
            self.assertIsNotNone(parser)

    def test_format_task_prompt_auditor_versus_author(self) -> None:
        """Requirement: MUST tailor task prompts distinguishing auditor from author roles."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = DshHarnessAdapter(simulation_mode=True)
            auditor_dispatch = subagent_coordinator.RoleDispatch(
                role_name="qa",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/unit_a.py",),
                batch_size=3,
                task_prompt="",
            )
            prompt = adapter._format_task_prompt(auditor_dispatch)
            self.assertIn("Auditor", prompt)
            self.assertIn("DO NOT EDIT FILES", prompt)
            self.assertIn("bin/blame", prompt)
            self.assertNotIn("Edit code or specifications", prompt)

    def test_registering_dsh_harness_factory(self) -> None:
        """Scenario 7: Installs DeepSeek Harness adapter factory into HarnessRegistry."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            mgr = scope.get_singleton(dsh_harness.DshHarnessManager)
            self.assertIn("dsh", self.mock_harness_registry.installed)
            factory = self.mock_harness_registry.installed["dsh"]
            adapter = factory(model_name="DeepSeek-V41-Flash", simulation_mode=True)
            self.assertIsInstance(adapter, DshHarnessAdapter)


if __name__ == "__main__":
    unittest.main()
