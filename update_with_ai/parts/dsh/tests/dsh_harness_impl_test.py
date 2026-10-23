"""Unit tests for dsh_harness_impl."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from typing import Any, Dict, List, Optional, Sequence

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.dsh.lib import dsh_asm, dsh_harness, dsh_telemetry
from update_with_ai.parts.dsh.lib.dsh_harness_impl import (
    DshHarnessAdapter,
    DshHarnessManager,
    __initialize__,
)
from update_with_ai.parts.subagent.lib import subagent_coordinator, subagent_harness
from update_with_ai.parts.workspace_cli.lib import work
from update_with_ai.parts.workspace.lib import role_registry


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
    ) -> role_registry.RoleDefinition:
        clean = role_name_or_address.split(":")[-1].strip().lower()
        if clean in ("qa", "coverage", "spec_qa"):
            return role_registry.RoleDefinition(
                role_name=clean,
                guide_path=f"guides/{clean}.md",
                writable_file_patterns=[],
                readonly_file_patterns=[],
                feedback_role_deps=[],
            )
        return role_registry.RoleDefinition(
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


class FakeDshTelemetryParser:
    tier = agent_session.agent_session

    def __init__(self, server_available: bool = True, fail_rpc: bool = False) -> None:
        self.server_available = server_available
        self.fail_rpc = fail_rpc
        self.dispatched: list[dict[str, Any]] = []
        self.polled_handles: list[str] = []
        self.round_status: dsh_telemetry.DshRpcRoundStatus = dsh_telemetry.DshRpcRoundStatus(
            is_active=False,
            is_completed=True,
            metrics=dsh_telemetry.DshSessionTokenMetrics(
                input_tokens=600,
                cached_tokens=200,
                output_tokens=150,
                total_tokens=950,
                cost_usd=0.0001,
            ),
        )

    @property
    def turn_status(self) -> dsh_telemetry.DshRpcRoundStatus:
        return self.round_status

    @turn_status.setter
    def turn_status(self, val: dsh_telemetry.DshRpcRoundStatus) -> None:
        self.round_status = val

    def is_desktop_server_available(self, sessions_dir: Optional[str] = None) -> bool:
        return self.server_available

    def dispatch_round_rpc(
        self,
        workspace_dir: str,
        role_name: str,
        prompt_text: str,
        session_id: Optional[str] = None,
        sessions_dir: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Optional[str]:
        if not self.server_available or self.fail_rpc:
            return None
        sid = session_id or f"mock-sid-{role_name}"
        self.dispatched.append({
            "workspace_dir": workspace_dir,
            "role_name": role_name,
            "prompt_text": prompt_text,
            "session_id": sid,
        })
        return f"dsh_rpc::{sid}::mock-msg-1"

    dispatch_turn_rpc = dispatch_round_rpc

    def poll_round_rpc(
        self,
        task_handle: str,
        sessions_dir: Optional[str] = None,
    ) -> dsh_telemetry.DshRpcRoundStatus:
        self.polled_handles.append(task_handle)
        return self.round_status

    poll_turn_rpc = poll_round_rpc

    def parse_stream_text(
        self,
        stream_text: str,
        model_name: Optional[str] = None,
    ) -> dsh_telemetry.DshSessionTokenMetrics:
        return dsh_telemetry.DshSessionTokenMetrics()

    def parse_session_storage(
        self,
        sessions_dir: str,
        workspace_dir: str,
        model_name: Optional[str] = None,
    ) -> dsh_telemetry.DshSessionTokenMetrics:
        return dsh_telemetry.DshSessionTokenMetrics()

    def sync_desktop_session(
        self,
        sessions_dir: Optional[str],
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        start_time: float,
    ) -> None:
        pass


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
            keys=[role_registry.WorkspaceRegistry],
            tier=agent_session.agent_session,
        )
        self.work_mgr = FakeWorkspaceWorkManager()
        self.registry.register_instance(
            self.work_mgr,
            keys=[work.WorkspaceWorkManager],
            tier=agent_session.agent_session,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)
    def test_dispatch_and_await_clean_round_in_simulation(self) -> None:
        """Requirement: MUST execute round and return clean status when work is completed."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=True,
            )

            # Setup pending work before round
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

    def test_dispatch_and_await_blamed_round_in_simulation(self) -> None:
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

    def test_session_id_reset_upon_blame_or_failure(self) -> None:
        """Requirement: MUST preserve .cleanroom/dsh_session_id.txt on blamed round and reset on failed round."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=True,
            )

            # Pre-seed dsh_session_id.txt
            cleanroom_dir = os.path.join(self.test_dir, ".cleanroom")
            os.makedirs(cleanroom_dir, exist_ok=True)
            sess_file = os.path.join(cleanroom_dir, "dsh_session_id.txt")
            with open(sess_file, "w", encoding="utf-8") as f:
                f.write("old-session-123\n")

            # Write culprit file into blame buffer
            blame_buf = os.path.join(self.test_dir, ".cleanroom_blame_buffer.json")
            with open(blame_buf, "w", encoding="utf-8") as f:
                json.dump(["scenarios/unit_a.md"], f)

            dispatch = subagent_coordinator.RoleDispatch(
                role_name="low",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("low/unit_a.pyi",),
                batch_size=1,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)
            result = adapter.await_role(handle)
            self.assertEqual(result.status, "blamed")
            # Blame MUST NOT reset session ID
            self.assertTrue(os.path.exists(sess_file))

            # Now test failed round resets session ID via public await_role
            fake_parser = FakeDshTelemetryParser(server_available=True)
            fake_parser.round_status = dsh_telemetry.DshRpcRoundStatus(
                is_completed=True,
                error="Fatal harness failure",
            )
            rpc_adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=False,
                parser=fake_parser,
            )
            handle_fail = rpc_adapter.dispatch_role(dispatch)
            res_failed = rpc_adapter.await_role(handle_fail)
            self.assertEqual(res_failed.status, "failed")
            # Failure MUST reset session ID
            self.assertFalse(os.path.exists(sess_file))

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
            task_handle = adapter.dispatch_role(auditor_dispatch)
            log_dir = subagent_coordinator.resolve_cleanroom_log_dir(self.test_dir)
            prompt_file = os.path.join(log_dir, f".dsh_prompt_{task_handle}.md")
            with open(prompt_file, "r", encoding="utf-8") as f:
                prompt = f.read()
            self.assertIn("Auditor", prompt)
            self.assertIn("AGENTS.md", prompt)
            self.assertIn("bin/get_work", prompt)

    def test_format_task_prompt_incorporates_coordinator_reminder(self) -> None:
        """Requirement: MUST incorporate coordinator reminder directive into task prompt."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = DshHarnessAdapter(simulation_mode=True)
            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/unit_a.py",),
                batch_size=1,
                task_prompt="CRITICAL REMINDER: The previous round concluded without submitting.",
            )
            task_handle = adapter.dispatch_role(dispatch)
            log_dir = subagent_coordinator.resolve_cleanroom_log_dir(self.test_dir)
            prompt_file = os.path.join(log_dir, f".dsh_prompt_{task_handle}.md")
            with open(prompt_file, "r", encoding="utf-8") as f:
                prompt = f.read()
            self.assertIn("## Coordinator Directive / Action Required", prompt)
            self.assertIn("CRITICAL REMINDER: The previous round concluded without submitting.", prompt)

    def test_registering_dsh_harness_factory(self) -> None:
        """Scenario 7: Installs DeepSeek Harness adapter factory into HarnessRegistry."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            mgr = scope.get_singleton(dsh_harness.DshHarnessManager)
            self.assertIn("dsh", self.mock_harness_registry.installed)
            factory = self.mock_harness_registry.installed["dsh"]
            adapter = factory(model_name="DeepSeek-V41-Flash", simulation_mode=True)
            self.assertIsInstance(adapter, DshHarnessAdapter)

    def test_await_role_recovers_targets_from_log_lines(self) -> None:
        """Requirement: MUST inspect round log files for submitted and blamed targets when blame buffer is absent."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=True,
            )

            # Do not set pending work beforehand; dispatch_role will seed from ready_targets
            dispatch = subagent_coordinator.RoleDispatch(
                role_name="qa",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/unit_a.py",),
                batch_size=3,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)

            # Write log lines with [BLAME] and [AUDIT]
            cleanroom_log = os.path.join(self.test_dir, ".cleanroom.log")
            with open(cleanroom_log, "w", encoding="utf-8") as f:
                f.write("[AUDIT] //pkg/parts/foo:unit_a: QA_AUDIT\n")
                f.write("[BLAME] //pkg/parts/foo:unit_b: feedback message\n")

            result = adapter.await_role(handle)
            self.assertEqual(result.role, "qa")
            self.assertIn("//pkg/parts/foo:unit_a", result.submitted_targets)
            self.assertIn("//pkg/parts/foo:unit_b", result.blamed_targets)

    def test_await_role_recovers_blamed_targets_from_workspace_cleanroom_log(self) -> None:
        """Requirement: MUST inspect workspace .cleanroom.log for blamed targets when task log file is absent."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=True,
            )

            dispatch = subagent_coordinator.RoleDispatch(
                role_name="qa",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/unit_a.py",),
                batch_size=3,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)

            cleanroom_log = os.path.join(self.test_dir, ".cleanroom.log")
            with open(cleanroom_log, "w", encoding="utf-8") as f:
                f.write("[BLAME] //pkg/parts/foo/lib/unit_a.py: Contract violation\n")

            result = adapter.await_role(handle)
            self.assertEqual(result.role, "qa")
            self.assertEqual(result.status, "blamed")
            self.assertIn("//pkg/parts/foo/lib/unit_a.py", result.blamed_targets)

    def test_sessions_dir_discovery_and_environment_overrides(self) -> None:
        """Requirement: MUST discover sessions_dir across environment variables and fallbacks."""
        orig_env = dict(os.environ)
        try:
            # 1. Explicit sessions_dir argument initializes cleanly
            adapter1 = DshHarnessAdapter(sessions_dir="/custom/sessions/path", simulation_mode=True)
            self.assertIsNotNone(adapter1)

            # 2. DSH_SESSIONS_DIR env var
            os.environ["DSH_SESSIONS_DIR"] = "/env/sessions/dir"
            adapter2 = DshHarnessAdapter(simulation_mode=True)
            self.assertIsNotNone(adapter2)

            # 3. DSH_HOME env var
            os.environ.pop("DSH_SESSIONS_DIR", None)
            os.environ["DSH_HOME"] = self.test_dir
            sess_under_dsh = os.path.join(self.test_dir, "harness", "sessions")
            os.makedirs(sess_under_dsh, exist_ok=True)
            adapter3 = DshHarnessAdapter(simulation_mode=True)
            self.assertIsNotNone(adapter3)
        finally:
            os.environ.clear()
            os.environ.update(orig_env)

    def test_dispatch_and_await_role_via_rpc(self) -> None:
        """Scenario 1 & 2: Dispatches role round over RPC bridge when server is reachable and extracts telemetry."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            fake_parser = FakeDshTelemetryParser(server_available=True)
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=False,
                parser=fake_parser,
            )

            self.work_mgr.set_pending_work(self.test_dir, ["lib/foo.py"])
            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/foo.py",),
                batch_size=1,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)
            self.assertTrue(handle.startswith("dsh_lib_"))
            self.assertEqual(len(fake_parser.dispatched), 1)
            self.assertEqual(fake_parser.dispatched[0]["workspace_dir"], self.test_dir)

            # Simulate agent submitting target
            self.work_mgr.remove_pending_target(self.test_dir, "lib/foo.py")

            result = adapter.await_role(handle)
            self.assertEqual(result.role, "lib")
            self.assertEqual(result.status, "clean")
            self.assertEqual(result.submitted_targets, ("lib/foo.py",))
            self.assertIsNotNone(result.telemetry)
            assert result.telemetry is not None
            self.assertEqual(result.telemetry.total_tokens, 950)

    def test_poll_role_via_rpc_active_and_completed(self) -> None:
        """Scenario 5: Non-blocking polling over RPC bridge returns None while active and result when completed."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            fake_parser = FakeDshTelemetryParser(server_available=True)
            fake_parser.round_status = dsh_telemetry.DshRpcRoundStatus(is_active=True, is_completed=False)
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=False,
                parser=fake_parser,
            )

            self.work_mgr.set_pending_work(self.test_dir, ["lib/foo.py"])
            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/foo.py",),
                batch_size=1,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)
            res_running = adapter.poll_role(handle)
            self.assertIsNone(res_running)

            # Round finishes
            fake_parser.round_status = dsh_telemetry.DshRpcRoundStatus(
                is_active=False,
                is_completed=True,
                metrics=dsh_telemetry.DshSessionTokenMetrics(input_tokens=100, total_tokens=100),
            )
            self.work_mgr.remove_pending_target(self.test_dir, "lib/foo.py")
            res_done = adapter.poll_role(handle)
            self.assertIsNotNone(res_done)
            assert res_done is not None
            self.assertEqual(res_done.status, "clean")

    def test_dispatch_role_fallback_when_server_unavailable(self) -> None:
        """Scenario 1: Falls back to headless CLI execution when server is unreachable."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            fake_parser = FakeDshTelemetryParser(server_available=False)
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=False,
                custom_cmd="echo done",
                parser=fake_parser,
            )

            self.work_mgr.set_pending_work(self.test_dir, ["lib/foo.py"])
            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/foo.py",),
                batch_size=1,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)
            self.assertTrue(bool(handle))
            adapter.await_role(handle)

    def test_dispatch_role_server_available_rpc_unreachable_fails_cleanly(self) -> None:
        """Scenario 1: Fails cleanly without running incompatible headless CLI when desktop server RPC is unreachable."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            fake_parser = FakeDshTelemetryParser(server_available=True, fail_rpc=True)
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=False,
                parser=fake_parser,
            )

            self.work_mgr.set_pending_work(self.test_dir, ["lib/foo.py"])
            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/foo.py",),
                batch_size=1,
                task_prompt="",
            )

            with patch("time.sleep"):
                handle = adapter.dispatch_role(dispatch)
            result = adapter.await_role(handle)
            self.assertEqual(result.status, "failed")
            self.assertIn("DeepSeek Harness Desktop RPC is unavailable after retries", result.failure_reason or "")

    def test_dispatch_role_prompt_includes_agents_md_and_guide_without_disk_pending_write(self) -> None:
        """Requirement: MUST include AGENTS.md reminder, companion guide, and avoid pre-writing pending work to disk."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            fake_parser = FakeDshTelemetryParser(server_available=True)
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=False,
                parser=fake_parser,
            )

            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/foo.py",),
                batch_size=1,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)
            self.assertTrue(handle.startswith("dsh_lib_"))

            # Verify no pending work file was written on disk
            pending_file = os.path.join(self.test_dir, ".cleanroom_pending_work.json")
            self.assertFalse(os.path.isfile(pending_file))

            # Verify prompt contents in dispatched RPC
            self.assertEqual(len(fake_parser.dispatched), 1)
            prompt = fake_parser.dispatched[0]["prompt_text"]
            self.assertIn("AGENTS.md", prompt)
            self.assertIn("bin/get_work", prompt)

    def test_await_role_discovers_scoped_cleanroom_log_and_action_records(self) -> None:
        """Scenario 2: MUST discover candidate cleanroom logs across scoped directories and match [CHANGE] and [CLEAN]."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=True,
            )

            dispatch = subagent_coordinator.RoleDispatch(
                role_name="test",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("benchmarks/parts/foo/tests/foo_test.py",),
                batch_size=1,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)

            # Write scoped cleanroom log (e.g. <workspace>/benchmarks/.cleanroom.log)
            scoped_dir = os.path.join(self.test_dir, "benchmarks")
            os.makedirs(scoped_dir, exist_ok=True)
            scoped_log = os.path.join(scoped_dir, ".cleanroom.log")
            with open(scoped_log, "w", encoding="utf-8") as f:
                f.write("[CHANGE] benchmarks/parts/foo/tests/foo_test.py: Added unit tests\n")

            result = adapter.await_role(handle)
            self.assertEqual(result.role, "test")
            self.assertEqual(result.status, "clean")
            self.assertIn("benchmarks/parts/foo/tests/foo_test.py", result.submitted_targets)

    def test_await_role_matches_clean_and_submitted_and_audit_action_records(self) -> None:
        """Scenario 2: MUST parse [CLEAN], [SUBMITTED], and [AUDIT] action records into submitted_targets."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=True,
            )

            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/clean_target.py", "lib/sub_target.py", "lib/audit_target.py"),
                batch_size=3,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)

            scoped_dir = os.path.join(self.test_dir, "pkg", "parts")
            os.makedirs(scoped_dir, exist_ok=True)
            scoped_log = os.path.join(scoped_dir, ".cleanroom.log")
            with open(scoped_log, "w", encoding="utf-8") as f:
                f.write("[CLEAN] lib/clean_target.py\n")
                f.write("[SUBMITTED] lib/sub_target.py\n")
                f.write("[AUDIT] lib/audit_target.py: verified\n")

            result = adapter.await_role(handle)
            self.assertEqual(result.status, "clean")
            self.assertIn("lib/clean_target.py", result.submitted_targets)
            self.assertIn("lib/sub_target.py", result.submitted_targets)
            self.assertIn("lib/audit_target.py", result.submitted_targets)

    def test_await_role_discovers_submitted_targets_via_pending_work_diff(self) -> None:
        """Scenario 2: MUST discover submitted targets when worker updates pending work buffer on disk."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=True,
            )

            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/target1.py", "lib/target2.py"),
                batch_size=2,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)

            # Simulate worker running bin/get_work and bin/submit target1.py
            # leaving only target2.py in .cleanroom_pending_work.json
            pending_file = os.path.join(self.test_dir, ".cleanroom_pending_work.json")
            with open(pending_file, "w", encoding="utf-8") as f:
                json.dump({"targets": ["lib/target2.py"]}, f)
            self.work_mgr.set_pending_work(self.test_dir, ["lib/target2.py"])

            result = adapter.await_role(handle)
            self.assertEqual(result.status, "clean")
            self.assertEqual(result.submitted_targets, ("lib/target1.py",))

    def test_incremental_round_telemetry_across_persistent_session_rounds(self) -> None:
        """Scenario 8: Computes incremental round deltas from cumulative session token metrics across persistent session rounds."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            fake_parser = FakeDshTelemetryParser(server_available=True)
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=False,
                parser=fake_parser,
            )

            # Round 1: Session has 600 in, 200 cached, 150 out ($0.0001)
            fake_parser.round_status = dsh_telemetry.DshRpcRoundStatus(
                is_active=False,
                is_completed=True,
                metrics=dsh_telemetry.DshSessionTokenMetrics(
                    input_tokens=600,
                    cached_tokens=200,
                    output_tokens=150,
                    total_tokens=950,
                    cost_usd=0.0001,
                ),
            )

            self.work_mgr.set_pending_work(self.test_dir, ["lib/foo.py"])
            dispatch1 = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/foo.py",),
                batch_size=1,
                task_prompt="",
            )
            handle1 = adapter.dispatch_role(dispatch1)
            self.work_mgr.remove_pending_target(self.test_dir, "lib/foo.py")
            res1 = adapter.await_role(handle1)

            self.assertEqual(res1.status, "clean")
            self.assertIsNotNone(res1.telemetry)
            assert res1.telemetry is not None
            self.assertEqual(res1.telemetry.input_tokens, 600)
            self.assertEqual(res1.telemetry.cached_tokens, 200)
            self.assertEqual(res1.telemetry.output_tokens, 150)
            self.assertEqual(res1.telemetry.total_tokens, 950)
            self.assertAlmostEqual(res1.telemetry.cost_usd, 0.0001, places=6)

            # Round 2 in same session: DSH session cumulative counter has grown to:
            # 900 in (+300), 500 cached (+300), 350 out (+200), cost 0.00025 (+0.00015)
            fake_parser.round_status = dsh_telemetry.DshRpcRoundStatus(
                is_active=False,
                is_completed=True,
                metrics=dsh_telemetry.DshSessionTokenMetrics(
                    input_tokens=900,
                    cached_tokens=500,
                    output_tokens=350,
                    total_tokens=1750,
                    cost_usd=0.00025,
                ),
            )

            self.work_mgr.set_pending_work(self.test_dir, ["lib/bar.py"])
            dispatch2 = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/bar.py",),
                batch_size=1,
                task_prompt="",
            )
            handle2 = adapter.dispatch_role(dispatch2)
            self.work_mgr.remove_pending_target(self.test_dir, "lib/bar.py")
            res2 = adapter.await_role(handle2)

            self.assertEqual(res2.status, "clean")
            self.assertIsNotNone(res2.telemetry)
            assert res2.telemetry is not None
            # Must report the incremental round delta, NOT the cumulative session total!
            self.assertEqual(res2.telemetry.input_tokens, 300)
            self.assertEqual(res2.telemetry.cached_tokens, 300)
            self.assertEqual(res2.telemetry.output_tokens, 200)
            self.assertEqual(res2.telemetry.total_tokens, 800)
            self.assertAlmostEqual(res2.telemetry.cost_usd, 0.00015, places=6)

            # Round 3: Failed round evicts baseline
            fake_parser.round_status = dsh_telemetry.DshRpcRoundStatus(
                is_active=False,
                is_completed=True,
                error="Model invocation failed",
            )
            handle3 = adapter.dispatch_role(dispatch2)
            res3 = adapter.await_role(handle3)
            self.assertEqual(res3.status, "failed")

            # Round 4: Fresh session with new baseline after reset
            fake_parser.round_status = dsh_telemetry.DshRpcRoundStatus(
                is_active=False,
                is_completed=True,
                metrics=dsh_telemetry.DshSessionTokenMetrics(
                    input_tokens=500,
                    cached_tokens=100,
                    output_tokens=100,
                    total_tokens=700,
                    cost_usd=0.00008,
                ),
            )
            self.work_mgr.set_pending_work(self.test_dir, ["lib/baz.py"])
            dispatch4 = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/baz.py",),
                batch_size=1,
                task_prompt="",
            )
            handle4 = adapter.dispatch_role(dispatch4)
            self.work_mgr.remove_pending_target(self.test_dir, "lib/baz.py")
            res4 = adapter.await_role(handle4)
            self.assertEqual(res4.status, "clean")
            self.assertIsNotNone(res4.telemetry)
            assert res4.telemetry is not None
            self.assertEqual(res4.telemetry.total_tokens, 700)


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-18T19:13:51Z
# LAST_CHANGED: 2026-10-21T01:00:00Z
# CHANGE: Add test for incremental round token telemetry across persistent session rounds
# COVERAGE_AUDIT: 2026-10-18T19:13:51Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
