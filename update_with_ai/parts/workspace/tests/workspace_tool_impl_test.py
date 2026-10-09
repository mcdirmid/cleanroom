# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:02Z
# LAST_CHANGED: 2026-10-08T12:55:00Z
# CHANGE: remove uncontracted dependencies and use collaborator doubles
# CODE_HASH: c1c91a039dac
# COVERAGE_AUDIT: 2026-10-09T21:19:02Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Unit tests for workspace_tool_impl."""

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from typing import Any, Dict, List, Optional, Sequence, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton
from update_with_ai.parts.control.lib import (
    control_attribution,
    control_submit,
)
from update_with_ai.parts.tools.lib import (
    tool_coverage,
)
from update_with_ai.parts.workspace.lib import (
    workspace_provision,
    workspace_registry,
    workspace_sync,
    workspace_tool,
    workspace_tool_impl,
    workspace_work,
)


class FakeWorkspaceRegistry:
    tier = "agent_session"

    def __init__(self, roles: Sequence[workspace_registry.RoleDefinition]) -> None:
        self.roles = list(roles)

    def discover_repository_root(self, start_dir: Optional[str] = None) -> str:
        return "/fake_repo"

    def list_roles(
        self, repo_root: Optional[str] = None
    ) -> Sequence[workspace_registry.RoleDefinition]:
        return self.roles

    def resolve_role_definition(
        self, role_name_or_address: str, repo_root: Optional[str] = None
    ) -> workspace_registry.RoleDefinition:
        clean = role_name_or_address.split(":")[-1].strip().lower()
        for r in self.roles:
            if r.role_name == clean:
                return r
        raise KeyError(f"Role not found: {role_name_or_address}")


class FakeWorkspaceProvisioner:
    tier = "agent_session"

    def __init__(self, registry: FakeWorkspaceRegistry) -> None:
        self.registry = registry

    def commission(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> workspace_registry.WorkspaceDescriptor:
        ws_dir = os.path.join(repo_root or tempfile.gettempdir(), f"role_{role_name}")
        os.makedirs(ws_dir, exist_ok=True)
        r_def = self.registry.resolve_role_definition(role_name, repo_root)
        role_cfg_path = os.path.join(ws_dir, ".cleanroom_role.json")
        with open(role_cfg_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "role_name": role_name,
                    "dir_scope": dir_scope,
                    "main_workspace_root": repo_root or "",
                },
                f,
            )
        return workspace_registry.WorkspaceDescriptor(
            workspace_dir=ws_dir,
            main_repository_root=repo_root or "",
            directory_scope=dir_scope,
            role_definition=r_def,
        )


class FakeWorkspaceSynchronizer:
    tier = "agent_session"

    def pull(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str = "staging",
        silent: bool = False,
    ) -> None:
        pass

    def refresh_system_files(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str = "staging",
        silent: bool = False,
    ) -> None:
        pass


class FakeWorkspaceWorkManager:
    tier = "agent_session"

    def __init__(self) -> None:
        self.pending: List[str] = []
        self.ready_items: List[workspace_work.WorkQueueItem] = []
        self.blocked_items: List[workspace_work.WorkQueueItem] = []

    def get_pending_work(self, ws_root: str) -> List[str]:
        return list(self.pending)

    def is_pending_target_dirty(self, ws_root: str, target: str) -> bool:
        return True

    def clear_pending_work(self, ws_root: str) -> None:
        self.pending = []

    def set_pending_work(self, ws_root: str, targets: Sequence[str]) -> None:
        self.pending = list(targets)

    def remove_pending_target(self, ws_root: str, target: str) -> None:
        if target in self.pending:
            self.pending.remove(target)

    def compute_role_work_queue(
        self, role_name: str, dir_scope: str, repo_root: str
    ) -> Tuple[Sequence[workspace_work.WorkQueueItem], Sequence[workspace_work.WorkQueueItem]]:
        return self.ready_items, self.blocked_items

    def regenerate_missing_templates(
        self, ws_root: str, role_name: str, main_root: str, dir_scope: str = "staging"
    ) -> None:
        pass


class FakeSubmissionCoordinator:
    tier = "agent_session"

    def submit_target_file(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> control_submit.SubmissionOutcome:
        msg = f"[CHANGE] {target}: {summary}" if summary else f"[CHANGE] {target}"
        return control_submit.SubmissionOutcome(accepted=True, message=msg)

    def resolve_submit_target(
        self,
        target: str,
        repo_root: str,
        role_name: str,
        dir_scope: str = "staging",
    ) -> Tuple[Optional[str], Optional[str]]:
        if os.path.isfile(target):
            return target, os.path.splitext(os.path.basename(target))[0]
        cand = os.path.join(repo_root, target)
        if os.path.isfile(cand):
            return cand, os.path.splitext(os.path.basename(cand))[0]
        return None, None


class FakeAttributionCoordinator:
    tier = "agent_session"

    def blame_culprit_file(
        self,
        culprit_file: str,
        critique: str,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        caller_role: Optional[str] = None,
    ) -> control_attribution.AttributionOutcome:
        return control_attribution.AttributionOutcome(
            accepted=True,
            message=f"✔ Blamed {culprit_file}: {critique}",
            affected_nodes=(),
        )

    def fail_target_file(
        self,
        target_file: str,
        reason: Optional[str] = None,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
    ) -> control_attribution.AttributionOutcome:
        return control_attribution.AttributionOutcome(
            accepted=True,
            message=f"✔ Marked {target_file} failed: {reason}",
            affected_nodes=(),
        )


class FakeCoverageEvaluator:
    tier = "agent_session"

    def evaluate_target(self, *args: Any, **kwargs: Any) -> Any:
        return None


class WorkspaceToolImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.fake_roles = [
            workspace_registry.RoleDefinition(
                role_name="lib",
                guide_path="guides/lib.md",
                writable_file_patterns=["lib/*.py"],
                readonly_file_patterns=["low/*.pyi"],
                feedback_role_deps=["low"],
                src_pattern="lib/{unit_name}.py",
            ),
            workspace_registry.RoleDefinition(
                role_name="low_qa",
                guide_path="guides/low_qa.md",
                writable_file_patterns=["low/*.pyi"],
                readonly_file_patterns=["high/*.md"],
                feedback_role_deps=["high"],
                audit_tag="LOW_QA_AUDIT",
                src_pattern="low/{unit_name}.pyi",
            ),
            workspace_registry.RoleDefinition(
                role_name="high",
                guide_path="guides/high.md",
                writable_file_patterns=["high/*.md"],
                readonly_file_patterns=[],
                feedback_role_deps=[],
                src_pattern="high/{unit_name}.md",
            ),
        ]
        self.fake_reg = FakeWorkspaceRegistry(self.fake_roles)
        self.fake_prov = FakeWorkspaceProvisioner(self.fake_reg)
        self.fake_sync = FakeWorkspaceSynchronizer()
        self.fake_work = FakeWorkspaceWorkManager()
        self.fake_sub = FakeSubmissionCoordinator()
        self.fake_attr = FakeAttributionCoordinator()
        self.fake_cov = FakeCoverageEvaluator()

        self.registry.register_instance(
            self.fake_reg,
            keys=[workspace_registry.WorkspaceRegistry],
            tier="agent_session",
        )
        self.registry.register_instance(
            self.fake_prov,
            keys=[workspace_provision.WorkspaceProvisioner],
            tier="agent_session",
        )
        self.registry.register_instance(
            self.fake_sync,
            keys=[workspace_sync.WorkspaceSynchronizer],
            tier="agent_session",
        )
        self.registry.register_instance(
            self.fake_work,
            keys=[workspace_work.WorkspaceWorkManager],
            tier="agent_session",
        )
        self.registry.register_instance(
            self.fake_sub,
            keys=[control_submit.SubmissionCoordinator],
            tier="agent_session",
        )
        self.registry.register_instance(
            self.fake_attr,
            keys=[control_attribution.AttributionCoordinator],
            tier="agent_session",
        )
        self.registry.register_instance(
            self.fake_cov,
            keys=[tool_coverage.CoverageEvaluator],
            tier="agent_session",
        )
        workspace_tool_impl.__initialize__(self.registry)
        self.phase_cm = enter_phase("agent_session", registry=self.registry)
        self.phase_cm.__enter__()

        self.test_dir = tempfile.mkdtemp()
        self.fake_repo = os.path.realpath(os.path.join(self.test_dir, "fake_repo"))
        os.makedirs(self.fake_repo, exist_ok=True)
        self.orig_cwd = os.getcwd()

    def tearDown(self) -> None:
        if hasattr(self, "phase_cm"):
            self.phase_cm.__exit__(None, None, None)
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_runner_execute_command_help(self) -> None:
        runner = workspace_tool_impl.WorkspaceToolRunner()
        # Invalid command exits 2 via argparse SystemExit
        with self.assertRaises(SystemExit):
            runner.execute_command(["invalid_cmd"])

    def test_runner_get_work_clean(self) -> None:
        prov = get_singleton(workspace_provision.WorkspaceProvisioner)
        desc = prov.commission("lib", "staging", repo_root=self.fake_repo)
        os.chdir(desc.workspace_dir)

        runner = workspace_tool_impl.WorkspaceToolRunner()
        ret = runner.execute_command(["get_work"])
        self.assertEqual(ret, 0)

    def test_runner_submit_and_blame_workflows(self) -> None:
        prov = get_singleton(workspace_provision.WorkspaceProvisioner)
        desc = prov.commission("low_qa", "staging", repo_root=self.fake_repo)
        os.chdir(desc.workspace_dir)

        runner = workspace_tool_impl.WorkspaceToolRunner()
        ret_blame = runner.execute_command(
            ["blame", "staging/parts/agent/low/config.pyi", "Spec missing parameter"]
        )
        self.assertEqual(ret_blame, 0)

        main_log = os.path.join(self.fake_repo, "staging/.cleanroom.log")
        self.assertTrue(os.path.isfile(main_log))
        with open(main_log, "r", encoding="utf-8") as f:
            log_content = f.read()
        self.assertIn("Spec missing parameter", log_content)

        ret_fb = runner.execute_command(
            ["feedback", "staging/parts/agent/low/config.pyi", "Second critique via feedback"]
        )
        self.assertEqual(ret_fb, 0)
        with open(main_log, "r", encoding="utf-8") as f:
            log_content = f.read()
        self.assertIn("Second critique via feedback", log_content)

    def test_runner_check_files(self) -> None:
        prov = get_singleton(workspace_provision.WorkspaceProvisioner)
        desc = prov.commission("high", "staging", repo_root=self.fake_repo)
        os.chdir(desc.workspace_dir)

        runner = workspace_tool_impl.WorkspaceToolRunner()
        ret_no_targets = runner.execute_command(["check_files"])
        self.assertEqual(ret_no_targets, 0)

        ret_not_found = runner.execute_command(["check_files", "nonexistent_target"])
        self.assertEqual(ret_not_found, 1)

    def test_runner_get_work_with_contracts(self) -> None:
        prov = get_singleton(workspace_provision.WorkspaceProvisioner)
        desc = prov.commission("lib", "staging", repo_root=self.fake_repo)
        os.chdir(desc.workspace_dir)

        self.fake_work.ready_items = [
            workspace_work.WorkQueueItem(
                target_file="staging/parts/agent/lib/config.py",
                role_name="lib",
                dirtiness_reasons=["contract updated"],
                dependency_files=[],
                is_ready=True,
                contract_files=["staging/parts/agent/low/config.pyi"],
            )
        ]

        runner = workspace_tool_impl.WorkspaceToolRunner()
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = runner.execute_command(["get_work"])
        out = buf.getvalue()
        self.assertEqual(ret, 1)
        self.assertIn("Contracts / Specifications to Read:", out)
        self.assertIn("staging/parts/agent/low/config.pyi", out)

    def test_runner_submit_cleanroom_log(self) -> None:
        prov = get_singleton(workspace_provision.WorkspaceProvisioner)
        desc = prov.commission("lib", "staging", repo_root=self.fake_repo)
        os.chdir(desc.workspace_dir)

        runner = workspace_tool_impl.WorkspaceToolRunner()
        ret = runner.execute_command(
            ["submit", "staging/parts/agent/lib/config.py", "Updated config"]
        )
        self.assertEqual(ret, 0)

        main_log = os.path.join(self.fake_repo, "staging/.cleanroom.log")
        self.assertTrue(os.path.isfile(main_log))
        with open(main_log, "r", encoding="utf-8") as f:
            log_content = f.read()
        self.assertIn("[CHANGE] staging/parts/agent/lib/config.py: Updated config", log_content)

    def test_cleanroom_log_resolution_and_append(self) -> None:
        p1 = workspace_tool_impl.resolve_cleanroom_log_path(
            "staging/parts/foo/lib/bar.py", repo_root=self.fake_repo
        )
        self.assertEqual(p1, os.path.join(self.fake_repo, "staging/.cleanroom.log"))

        p2 = workspace_tool_impl.resolve_cleanroom_log_path(
            "update_with_ai/parts/foo/lib/bar.py", repo_root=self.fake_repo
        )
        self.assertEqual(p2, os.path.join(self.fake_repo, "update_with_ai/.cleanroom.log"))

        p3 = workspace_tool_impl.resolve_cleanroom_log_path(
            "parts/foo/lib/bar.py", repo_root=self.fake_repo
        )
        self.assertEqual(p3, os.path.join(self.fake_repo, ".cleanroom.log"))

        written_path = workspace_tool_impl.append_cleanroom_log(
            "staging/parts/foo/lib/bar.py",
            "Test log entry for submit",
            repo_root=self.fake_repo,
        )
        self.assertEqual(written_path, p1)
        with open(written_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Test log entry for submit\n", content)


if __name__ == "__main__":
    unittest.main()
