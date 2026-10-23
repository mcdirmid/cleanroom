"""Unit tests for subagent_harness_impl."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from typing import Any, Optional
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.subagent.lib import (
    subagent_coordinator,
    subagent_harness,
    subagent_harness_impl,
)
from update_with_ai.parts.workspace_cli.lib import work


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
            keys=[work.WorkspaceWorkManager],
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
        """Scenario 5: Installs and resolves harness adapters via dynamic registry."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            registry = scope.get_singleton(subagent_harness.HarnessRegistry)

            def mock_factory(
                model_name: Optional[str] = None,
                timeout_seconds: Optional[float] = None,
                max_context_tokens: Optional[int] = None,
                custom_cmd: Optional[str] = None,
                simulation_mode: bool = False,
                **kwargs: Any,
            ) -> subagent_coordinator.HarnessAdapter:
                return subagent_harness_impl.CommandHarnessAdapter(
                    cmd_template=custom_cmd or "mock_agent {prompt_file}",
                    timeout_seconds=timeout_seconds,
                    max_context_tokens=max_context_tokens,
                    model_name=model_name,
                    simulation_mode=simulation_mode,
                )

            registry.install_harness("mock_platform", mock_factory)
            self.assertIn("mock_platform", registry.installed_harnesses)

            adapter = registry.resolve_harness("mock_platform", model_name="test-model")
            self.assertIsInstance(adapter, subagent_harness_impl.CommandHarnessAdapter)
            assert isinstance(adapter, subagent_harness_impl.CommandHarnessAdapter)
            self.assertEqual(adapter.model_name, "test-model")

            adapter_sim = registry.resolve_harness("simulation")
            self.assertIsInstance(adapter_sim, subagent_harness_impl.CommandHarnessAdapter)
            assert isinstance(adapter_sim, subagent_harness_impl.CommandHarnessAdapter)
            self.assertTrue(adapter_sim.simulation_mode)

            adapter_custom = registry.resolve_harness(
                "any_platform",
                custom_cmd="custom_cmd {prompt_file}",
            )
            self.assertIsInstance(adapter_custom, subagent_harness_impl.CommandHarnessAdapter)
            assert isinstance(adapter_custom, subagent_harness_impl.CommandHarnessAdapter)
            self.assertEqual(adapter_custom.cmd_template, "custom_cmd {prompt_file}")

            with self.assertRaises(ValueError) as ctx:
                registry.resolve_harness("nonexistent_platform")
            self.assertIn("Unknown platform 'nonexistent_platform'", str(ctx.exception))


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
        """Scenario 7: Parses token reporting from round/step logs into normalized token telemetry."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = subagent_harness_impl.CommandHarnessAdapter(simulation_mode=True)
            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="pkg_a",
                ready_targets=("lib/a.py",),
            )
            handle = adapter.dispatch_role(dispatch)

            # Write fake step log
            log_dir = subagent_coordinator.resolve_cleanroom_log_dir(self.test_dir)
            log_path = os.path.join(log_dir, f".cleanroom_round_{handle}.log")
            with open(log_path, "w", encoding="utf-8") as lf:
                lf.write(
                    "[Step 1] Input tokens: 1000\n"
                    "[Step 1] Cached tokens: 500\n"
                    "[Step 1] Output tokens: 200\n"
                    "[Step 2] Model request: 10K tokens, 50% cached\n"
                )

            result = adapter.await_role(handle)
            tel = result.telemetry
            self.assertIsNotNone(tel)
            assert tel is not None
            # Step 1: 1000 in, 500 cached, 200 out
            # Step 2: 10,000 total (50% cached = 5000 cached, 5000 uncached)
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T11:00:00Z
# CHANGE: turn down support for goose, supporting only antigravity and dsh
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
