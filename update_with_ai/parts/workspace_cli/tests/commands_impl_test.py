"""Unit tests for commands_impl aligned with low-level specifications."""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from typing import Any, Dict, List, Optional, Sequence, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.control.lib import (
    attribution,
    submit,
)
from update_with_ai.parts.workspace_cli.lib import (
    coverage,
    check,
    commands,
    commands_impl,
    pending,
    work,
)
from update_with_ai.parts.workspace.lib import (
    provision,
    role_registry,
    sync,
)


class FakeWorkspaceRegistry:
    tier = "agent_session"

    def __init__(
        self,
        roles: Sequence[role_registry.RoleDefinition],
        repo_root: Optional[str] = None,
    ) -> None:
        self.roles = list(roles)
        self.repo_root = repo_root

    def discover_repository_root(self, start_dir: Optional[str] = None) -> str:
        if self.repo_root:
            return self.repo_root
        if start_dir:
            parent = os.path.dirname(start_dir)
            if os.path.basename(start_dir).startswith("role_"):
                return parent
            return start_dir
        return "/fake_repo"

    def list_roles(
        self, repo_root: Optional[str] = None, dir_scope: Optional[str] = None
    ) -> Sequence[role_registry.RoleDefinition]:
        return self.roles

    def resolve_role_definition(
        self, role_name: str, repo_root: Optional[str] = None, dir_scope: Optional[str] = None
    ) -> role_registry.RoleDefinition:
        clean = role_name.split(":")[-1].strip().lower()
        for r in self.roles:
            if r.role_name == clean:
                return r
        return role_registry.RoleDefinition(
            role_name=clean,
            guide_path=f"guides/{clean}.md",
            writable_file_patterns=[f"{clean}/*"],
            readonly_file_patterns=[],
            feedback_role_deps=[],
            src_pattern=f"{clean}/{{unit_name}}.py",
        )

    def load_active_workspaces(
        self, repo_root: Optional[str] = None
    ) -> Sequence[role_registry.WorkspaceDescriptor]:
        return []


class FakeWorkspaceProvisioner:
    tier = "agent_session"

    def __init__(self, reg: FakeWorkspaceRegistry) -> None:
        self.reg = reg
        self.commissioned: List[Tuple[str, str, Optional[str]]] = []

    def commission(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        reset: bool = False,
        model: Optional[str] = None,
    ) -> role_registry.WorkspaceDescriptor:
        self.commissioned.append((role_name, dir_scope, custom_dest))
        r_def = self.reg.resolve_role_definition(role_name, repo_root=repo_root)
        dest = custom_dest or f"/fake_dest/{role_name}"
        return role_registry.WorkspaceDescriptor(
            role_definition=r_def,
            workspace_dir=dest,
            main_repository_root=repo_root or "/fake_repo",
            directory_scope=dir_scope,
        )

    def copy_file_with_permissions(
        self,
        src: str,
        dst: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


class FakeWorkspaceSynchronizer:
    tier = "agent_session"

    def __init__(self) -> None:
        self.pulled: List[Tuple[str, str, str, str]] = []
        self.refreshed: List[Tuple[str, str, str, str]] = []

    def pull(
        self,
        workspace_dir: str,
        repo_root: str,
        role_name: str,
        dir_scope: str = "staging",
        silent: bool = False,
    ) -> None:
        self.pulled.append((workspace_dir, repo_root, role_name, dir_scope))

    def refresh_system_files(
        self,
        workspace_dir: str,
        repo_root: str,
        role_name: str,
        dir_scope: str = "staging",
        silent: bool = False,
    ) -> None:
        self.refreshed.append((workspace_dir, repo_root, role_name, dir_scope))


class FakePendingManager:
    tier = "agent_session"

    def __init__(self) -> None:
        self.pending: List[str] = []

    def get_pending_work(self, ws_root: str) -> Sequence[str]:
        return list(self.pending)

    def is_pending_target_dirty(
        self, pt: str, ws_root: str, main_root: Optional[str] = None, role_name: Optional[str] = None
    ) -> bool:
        return True

    def clear_pending_work(self, ws_root: str) -> None:
        self.pending = []

    def set_pending_work(self, ws_root: str, targets: Sequence[str]) -> None:
        self.pending = list(targets)

    def remove_pending_target(self, ws_root: str, target: str) -> None:
        if target in self.pending:
            self.pending.remove(target)
            return
        def _norm(s: str) -> str:
            stem = os.path.splitext(os.path.basename(s.replace("\\", "/")))[0]
            changed = True
            while changed:
                changed = False
                for sfx in ("_pretense", "_test", "_impl"):
                    if stem.endswith(sfx):
                        stem = stem[: -len(sfx)]
                        changed = True
                        break
            return stem
        norm_t = _norm(target)
        for p in list(self.pending):
            if _norm(p) == norm_t:
                self.pending.remove(p)


class FakeWorkspaceWorkManager:
    tier = "agent_session"

    def __init__(self) -> None:
        self.ready_items: List[work.WorkQueueItem] = []
        self.blocked_items: List[work.WorkQueueItem] = []

    def compute_role_work_queue(
        self, role_name: str, dir_scope: str, repo_root: str
    ) -> Tuple[Sequence[work.WorkQueueItem], Sequence[work.WorkQueueItem]]:
        return self.ready_items, self.blocked_items

    def resolve_contract_files(
        self, target_file: str, workspace_root: str, role_name: Optional[str] = None
    ) -> Sequence[str]:
        return ()


class FakeSubmissionCoordinator:
    tier = "agent_session"

    def submit_target_file(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> submit.SubmissionOutcome:
        msg = f"[CHANGE] {target}: {summary}" if summary else f"[CHANGE] {target}"
        return submit.SubmissionOutcome(accepted=True, message=msg)

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

    def parse_unit_from_file_path(
        self, file_path: str, repo_root: str
    ) -> Tuple[str, str, str]:
        rel = (
            os.path.relpath(file_path, repo_root).replace("\\", "/")
            if file_path.startswith(repo_root)
            else file_path.replace("\\", "/")
        )
        fname = os.path.basename(rel)
        stem = os.path.splitext(fname)[0]
        if stem.endswith("_test"):
            stem = stem[:-5]
        part_dir = os.path.dirname(os.path.dirname(rel))
        return part_dir, stem, ""


class FakeAttributionCoordinator:
    tier = "agent_session"

    def blame_culprit_file(
        self,
        culprit_file: str,
        critique: str,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        caller_role: Optional[str] = None,
    ) -> attribution.AttributionOutcome:
        return attribution.AttributionOutcome(
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
    ) -> attribution.AttributionOutcome:
        return attribution.AttributionOutcome(
            accepted=True,
            message=f"✔ Failed {target_file}: {reason}",
            affected_nodes=(),
        )


class FakeCoverageEvaluator:
    tier = "agent_session"

    def evaluate_coverage(
        self,
        target_or_impl: str,
        test_path: Optional[str] = None,
        repo_root: Optional[str] = None,
        threshold: float = 0.0,
        update_log: Optional[str] = None,
        max_spans: Optional[int] = None,
    ) -> coverage.ModuleCoverage:
        return coverage.ModuleCoverage(
            module_name="foo",
            test_name="foo_test",
            file_path="lib/foo.py",
            test_path="tests/foo_test.py",
            total_executable=10,
            covered=10,
            missed=0,
            coverage_pct=100.0,
            missing_lines=[],
            missing_ranges="",
            missing_spans=[],
            test_passed=True,
        )

    def format_coverage_report(
        self, cov: coverage.ModuleCoverage, threshold: float = 0.0, max_spans: Optional[int] = None
    ) -> str:
        return f"Coverage report: {cov.coverage_pct}%"


class FakeWorkspaceChecker:
    tier = "agent_session"

    def __init__(self) -> None:
        self.checked: set[str] = set()

    def run_get_work(
        self,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        force: bool = False,
        batch_size: Optional[int] = None,
    ) -> int:
        return 0

    def run_check_files(
        self,
        target: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        if target:
            self.checked.add(os.path.realpath(target))
            self.checked.add(target)
        return 0

    def record_check_executed(
        self,
        ws_root: str,
        target_path: str,
        passed: bool,
    ) -> None:
        self.checked.add(os.path.realpath(target_path))
        self.checked.add(target_path)

    def is_checked_since_modification(
        self,
        ws_root: str,
        target_path: str,
    ) -> bool:
        return os.path.realpath(target_path) in self.checked or target_path in self.checked


class WorkspaceCommandsImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.fake_roles = [
            role_registry.RoleDefinition(
                role_name="lib",
                guide_path="guides/lib.md",
                writable_file_patterns=["lib/*.py"],
                readonly_file_patterns=["low/*.pyi"],
                feedback_role_deps=["low"],
                src_pattern="lib/{unit_name}.py",
            ),
        ]
        self.fake_reg = FakeWorkspaceRegistry(self.fake_roles)
        self.fake_prov = FakeWorkspaceProvisioner(self.fake_reg)
        self.fake_sync = FakeWorkspaceSynchronizer()
        self.fake_work = FakeWorkspaceWorkManager()
        self.fake_pending = FakePendingManager()
        self.fake_sub = FakeSubmissionCoordinator()
        self.fake_attr = FakeAttributionCoordinator()
        self.fake_cov = FakeCoverageEvaluator()
        self.fake_check = FakeWorkspaceChecker()

        self.registry.register_instance(
            self.fake_reg,
            keys=[role_registry.WorkspaceRegistry],
            tier="agent_session",
        )
        self.registry.register_instance(
            self.fake_prov,
            keys=[provision.WorkspaceProvisioner],
            tier="agent_session",
        )
        self.registry.register_instance(
            self.fake_sync,
            keys=[sync.WorkspaceSynchronizer],
            tier="agent_session",
        )
        self.registry.register_instance(
            self.fake_work,
            keys=[work.WorkspaceWorkManager],
            tier="agent_session",
        )
        self.registry.register_instance(
            self.fake_pending,
            keys=[pending.WorkspacePendingManager],
            tier="agent_session",
        )
        self.registry.register_instance(
            self.fake_sub,
            keys=[submit.SubmissionCoordinator],
            tier="agent_session",
        )
        self.registry.register_instance(
            self.fake_attr,
            keys=[attribution.AttributionCoordinator],
            tier="agent_session",
        )
        self.registry.register_instance(
            self.fake_cov,
            keys=[coverage.CoverageEvaluator],
            tier="agent_session",
        )
        self.registry.register_instance(
            self.fake_check,
            keys=[check.WorkspaceChecker],
            tier="agent_session",
        )

        self.cmd_handler = commands_impl.WorkspaceCommandHandler()
        self.registry.register_instance(
            self.cmd_handler,
            keys=[
                commands.WorkspaceCommandHandler,
                commands_impl.WorkspaceCommandHandler,
            ],
            tier="agent_session",
        )
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.phase_cm.__enter__()
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        with open(os.path.join(self.test_dir, ".cleanroom_role.json"), "w", encoding="utf-8") as f:
            json.dump({"role_name": "lib", "dir_scope": "pkg", "parts_dir": "pkg"}, f)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)
        self.phase_cm.__exit__(None, None, None)

    def test_run_get_work_clean(self) -> None:
        ret = self.cmd_handler.run_get_work(dir_scope="pkg")
        self.assertEqual(ret, 0)

    def test_run_submit(self) -> None:
        target_file = os.path.join(self.test_dir, "lib", "foo.py")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w") as f:
            f.write("# sample\n")
        self.fake_pending.pending = [target_file]

        # Rejected without no_verify when modified without running check_files
        ret_no_check = self.cmd_handler.run_submit(target_file, summary="test change")
        self.assertEqual(ret_no_check, 1)

        # Bypassed with no_verify=True
        ret = self.cmd_handler.run_submit(target_file, summary="test change", no_verify=True)
        self.assertEqual(ret, 0)
        self.assertNotIn(target_file, self.fake_pending.pending)

    def test_run_submit_verified_after_modification(self) -> None:
        target_file = os.path.join(self.test_dir, "lib", "foo.py")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w") as f:
            f.write("# sample\n")
        self.fake_pending.pending = [target_file]

        self.fake_check.record_check_executed(self.test_dir, target_file, passed=True)
        ret = self.cmd_handler.run_submit(target_file, summary="test change")
        self.assertEqual(ret, 0)
        self.assertNotIn(target_file, self.fake_pending.pending)

    def test_run_blame(self) -> None:
        culprit = os.path.join(self.test_dir, "low", "foo.pyi")
        os.makedirs(os.path.dirname(culprit), exist_ok=True)
        with open(culprit, "w") as f:
            f.write("# spec\n")
        self.fake_pending.pending = [culprit]

        ret = self.cmd_handler.run_blame(culprit, "Contract mismatch error")
        self.assertEqual(ret, 0)
        self.assertNotIn(culprit, self.fake_pending.pending)

        buf_path = os.path.join(self.test_dir, commands_impl.BLAME_BUFFER_FILE)
        self.assertTrue(os.path.isfile(buf_path))
        with open(buf_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        self.assertTrue(any(e.get("target") == culprit.lstrip("/") for e in entries))

    def test_run_blame_clears_pending_library_target_when_pretense_blamed(self) -> None:
        r_def = role_registry.RoleDefinition(
            role_name="pretense_qa",
            guide_path="guides/pretense_qa.md",
            writable_file_patterns=[],
            readonly_file_patterns=[],
            feedback_role_deps=["lib", "pretense"],
            src_pattern="",
            audit_tag="PRETEST_QA_AUDIT",
        )
        self.fake_reg.roles.append(r_def)
        with open(
            os.path.join(self.test_dir, ".cleanroom_role.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(
                {"role_name": "pretense_qa", "dir_scope": "pkg", "parts_dir": "pkg"},
                f,
            )

        lib_target = os.path.join(self.test_dir, "lib", "dag_engine_lite_impl.py")
        culprit = os.path.join(
            self.test_dir, "pretense", "dag_engine_lite_impl_pretense.py"
        )
        os.makedirs(os.path.dirname(lib_target), exist_ok=True)
        os.makedirs(os.path.dirname(culprit), exist_ok=True)
        with open(lib_target, "w") as f:
            f.write("# lib code\n")
        with open(culprit, "w") as f:
            f.write("# pretense suite\n")

        # Auditor has lib_target in pending work
        self.fake_pending.pending = [lib_target]

        ret = self.cmd_handler.run_blame(culprit, "Recursion in pretense aggregate")
        self.assertEqual(ret, 0)
        # lib_target must be cleared from pending work
        self.assertNotIn(lib_target, self.fake_pending.pending)
        self.assertEqual(self.fake_pending.pending, [])

    def test_run_blame_clears_single_pending_target_on_cross_unit_blame(self) -> None:
        my_target = os.path.join(self.test_dir, "lib", "my_unit.py")
        culprit = os.path.join(self.test_dir, "lib", "external_dep.py")
        os.makedirs(os.path.dirname(my_target), exist_ok=True)
        os.makedirs(os.path.dirname(culprit), exist_ok=True)
        with open(my_target, "w") as f:
            f.write("# unit\n")
        with open(culprit, "w") as f:
            f.write("# dep\n")

        # Worker or auditor has single pending target
        self.fake_pending.pending = [my_target]
        self.fake_check.record_check_executed(self.test_dir, my_target, passed=False)

        ret = self.cmd_handler.run_blame(culprit, "External dependency defect")
        self.assertEqual(ret, 0)
        # my_target must be resolved because exactly one pending target was being worked on
        self.assertNotIn(my_target, self.fake_pending.pending)
        self.assertEqual(self.fake_pending.pending, [])

    def test_run_blame_gated_when_workspace_modified(self) -> None:
        culprit = os.path.join(self.test_dir, "low", "foo.pyi")
        os.makedirs(os.path.dirname(culprit), exist_ok=True)
        with open(culprit, "w") as f:
            f.write("# spec\n")

        my_target = os.path.join(self.test_dir, "lib", "foo.py")
        os.makedirs(os.path.dirname(my_target), exist_ok=True)
        with open(my_target, "w") as f:
            f.write("# modified code\n")
        self.fake_pending.pending = [culprit, my_target]

        # Rejects blame while local modified target has not been checked
        ret_blocked = self.cmd_handler.run_blame(culprit, "Contract mismatch error")
        self.assertEqual(ret_blocked, 1)

        # After check_files is run on local target, blame succeeds
        self.fake_check.record_check_executed(self.test_dir, my_target, passed=False)
        ret_ok = self.cmd_handler.run_blame(culprit, "Contract mismatch error")
        self.assertEqual(ret_ok, 0)

    def test_run_fail(self) -> None:
        target_file = os.path.join(self.test_dir, "lib", "foo.py")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w") as f:
            f.write("# sample\n")
        self.fake_pending.pending = [target_file]

        # Rejects fail when modified without running check_files
        ret_blocked = self.cmd_handler.run_fail(target_file, reason="Verification error")
        self.assertEqual(ret_blocked, 1)

        # Once checked via check_files, fail succeeds
        self.fake_check.record_check_executed(self.test_dir, target_file, passed=False)
        ret = self.cmd_handler.run_fail(target_file, reason="Verification error")
        self.assertEqual(ret, 0)
        self.assertNotIn(target_file, self.fake_pending.pending)

    def test_run_coverage(self) -> None:
        ret = self.cmd_handler.run_coverage(target="lib/foo.py")
        self.assertEqual(ret, 0)

    def test_run_commission(self) -> None:
        ret = self.cmd_handler.run_commission(role_name="lib", dir_scope="pkg")
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_prov.commissioned), 1)

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:50:00Z
# CHANGE: Unit tests for commands_impl
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
