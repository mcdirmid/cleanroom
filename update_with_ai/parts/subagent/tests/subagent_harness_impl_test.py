# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_harness_impl unit tests
# CODE_HASH: c1212e7ed311
# COVERAGE_AUDIT: 2026-10-13T20:42:16Z
# QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Unit tests for subagent_harness_impl."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.subagent.lib import (
    subagent_coordinator,
    subagent_harness,
    subagent_harness_impl,
)
from update_with_ai.parts.workspace.lib import workspace_work


class FakeWorkspaceWorkManager:
    """Test double implementing WorkspaceWorkManager for harness tests."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.pending: dict[str, list[str]] = {}

    def get_pending_work(self, workspace_dir: str):
        return list(self.pending.get(workspace_dir, []))

    def set_pending_work(self, workspace_dir: str, targets) -> None:
        self.pending[workspace_dir] = list(targets)

    def clear_pending_work(self, workspace_dir: str) -> None:
        self.pending.pop(workspace_dir, None)

    def remove_pending_target(self, workspace_dir: str, target: str) -> bool:
        items = self.pending.get(workspace_dir, [])
        if target in items:
            items.remove(target)
            return True
        return False


class SubagentHarnessImplTest(unittest.TestCase):
    """Test cases for CommandHarnessAdapter and HarnessResolver."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        subagent_harness_impl.__initialize__(self.registry)
        self.work_mgr = FakeWorkspaceWorkManager()
        self.registry.register_instance(
            self.work_mgr,
            keys=[workspace_work.WorkspaceWorkManager],
            tier=agent_session.agent_session,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_formatting_instructional_task_prompts(self) -> None:
        """Scenario 1: Formats instructional task prompt detailing role, scope, targets, and commands."""
        adapter = subagent_harness_impl.CommandHarnessAdapter(simulation_mode=True)
        dispatch = subagent_coordinator.RoleDispatch(
            role_name="lib",
            workspace_dir=self.test_dir,
            dir_scope="pkg_a",
            ready_targets=("lib/module.py",),
        )
        prompt = adapter.format_task_prompt(dispatch)
        self.assertIn("Role: lib", prompt)
        self.assertIn("Scope: pkg_a", prompt)
        self.assertIn("Workspace: " + self.test_dir, prompt)
        self.assertIn("- lib/module.py", prompt)
        self.assertIn("check_files", prompt)
        self.assertIn("submit", prompt)
        self.assertIn("blame", prompt)
        self.assertIn("fail", prompt)

    def test_detecting_submitted_files_from_pending_work_diffs(self) -> None:
        """Scenario 2: Detects submitted targets by diffing pre-execution and post-execution pending targets."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = subagent_harness_impl.CommandHarnessAdapter(simulation_mode=True)
            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="pkg_a",
                ready_targets=("lib/a.py", "lib/b.py"),
            )
            handle = adapter.dispatch_role(dispatch)

            # Simulate subagent submitting lib/a.py (so only lib/b.py remains in pending work)
            self.work_mgr.set_pending_work(self.test_dir, ["lib/b.py"])

            result = adapter.await_role(handle)
            self.assertEqual(result.status, "clean")
            self.assertEqual(result.submitted_targets, ("lib/a.py",))
            self.assertEqual(result.blamed_targets, ())

    def test_detecting_defect_blame_from_the_blame_buffer(self) -> None:
        """Scenario 3: Reads blame buffer records and marks status as blamed."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = subagent_harness_impl.CommandHarnessAdapter(simulation_mode=True)
            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="pkg_a",
                ready_targets=("lib/a.py",),
            )
            handle = adapter.dispatch_role(dispatch)

            # Write blame buffer
            blame_file = os.path.join(self.test_dir, ".cleanroom_blame_buffer.json")
            with open(blame_file, "w", encoding="utf-8") as f:
                json.dump([{"culprit_target": "low/a.pyi", "reason": "Missing contract"}], f)

            result = adapter.await_role(handle)
            self.assertEqual(result.status, "blamed")
            self.assertEqual(result.blamed_targets, ("low/a.pyi",))

    def test_handling_subagent_process_execution_failure(self) -> None:
        """Scenario 4: External process crashing or exiting non-zero returns failed status."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = subagent_harness_impl.CommandHarnessAdapter(
                cmd_template="exit 42",
                simulation_mode=False,
            )
            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="pkg_a",
                ready_targets=("lib/a.py",),
            )
            handle = adapter.dispatch_role(dispatch)
            result = adapter.await_role(handle)
            self.assertEqual(result.status, "failed")
            self.assertIsNotNone(result.failure_reason)
            self.assertIn("42", str(result.failure_reason))

    def test_resolving_platform_command_templates(self) -> None:
        """Scenario 5: Resolves platform templates for Antigravity, Goose, DSH, and simulation."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            resolver = scope.get_singleton(subagent_harness.HarnessResolver)

            adapter_agy = resolver.resolve_harness("antigravity")
            self.assertIsInstance(adapter_agy, subagent_harness_impl.CommandHarnessAdapter)
            assert isinstance(adapter_agy, subagent_harness_impl.CommandHarnessAdapter)
            self.assertIn("agy", adapter_agy.cmd_template)

            adapter_goose = resolver.resolve_harness("goose")
            self.assertIsInstance(adapter_goose, subagent_harness_impl.CommandHarnessAdapter)
            assert isinstance(adapter_goose, subagent_harness_impl.CommandHarnessAdapter)
            self.assertIn("goose", adapter_goose.cmd_template)

            adapter_dsh = resolver.resolve_harness("dsh")
            self.assertIsInstance(adapter_dsh, subagent_harness_impl.CommandHarnessAdapter)
            assert isinstance(adapter_dsh, subagent_harness_impl.CommandHarnessAdapter)
            self.assertIn("dsh", adapter_dsh.cmd_template)

            adapter_sim = resolver.resolve_harness("simulation")
            self.assertIsInstance(adapter_sim, subagent_harness_impl.CommandHarnessAdapter)
            assert isinstance(adapter_sim, subagent_harness_impl.CommandHarnessAdapter)
            self.assertTrue(adapter_sim.simulation_mode)

            with self.assertRaises(ValueError):
                resolver.resolve_harness("nonexistent_platform")


    def test_enforcing_execution_timeouts(self) -> None:
        """Scenario 6: Terminates runaway subagent process when timeout expires."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = subagent_harness_impl.CommandHarnessAdapter(
                cmd_template="sleep 5",
                timeout_seconds=0.1,
                simulation_mode=False,
            )
            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="pkg_a",
                ready_targets=("lib/a.py",),
            )
            handle = adapter.dispatch_role(dispatch)
            result = adapter.await_role(handle)
            self.assertEqual(result.status, "failed")
            self.assertIsNotNone(result.failure_reason)
            self.assertIn("timed out", str(result.failure_reason))

    def test_parsing_token_metrics_from_execution_logs(self) -> None:
        """Scenario 7: Parses token reporting from turn logs into normalized token telemetry."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = subagent_harness_impl.CommandHarnessAdapter(simulation_mode=True)
            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="pkg_a",
                ready_targets=("lib/a.py",),
            )
            handle = adapter.dispatch_role(dispatch)

            # Write fake turn log
            log_path = os.path.join(self.test_dir, f".cleanroom_turn_{handle}.log")
            with open(log_path, "w", encoding="utf-8") as lf:
                lf.write(
                    "[Turn 1] Input tokens: 1000\n"
                    "[Turn 1] Cached tokens: 500\n"
                    "[Turn 1] Output tokens: 200\n"
                    "[Turn 2] Model request: 10K tokens, 50% cached\n"
                )

            result = adapter.await_role(handle)
            tel = result.telemetry
            self.assertIsNotNone(tel)
            assert tel is not None
            # Turn 1: 1000 in, 500 cached, 200 out
            # Turn 2: 10,000 total (50% cached = 5000 cached, 5000 uncached)
            # Total in: 1000 + 5000 = 6000
            # Total cached: 500 + 5000 = 5500
            # Total out: 200
            self.assertEqual(tel.input_tokens, 6000)
            self.assertEqual(tel.cached_tokens, 5500)
            self.assertEqual(tel.output_tokens, 200)
            self.assertEqual(tel.total_tokens, 11700)
            self.assertGreater(tel.cost_usd, 0.0)


if __name__ == "__main__":
    unittest.main()
