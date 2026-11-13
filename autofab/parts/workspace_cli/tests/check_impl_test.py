"""Unit tests for check_impl aligned with low-level specifications."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Sequence, Tuple

from support.lib.lifecycle import LifecycleTestCase, enter_phase
from autofab.parts.agent.lib import session as agent_session
from autofab.parts.control.lib import submit
from support.lib import app_info
from autofab.parts.workspace_cli.lib import (
    check,
    check_impl,
    pending,
    work,
)
from autofab.parts.workspace.lib import (
    provision,
    role_registry,
    sync,
)


class FakeWorkspaceRegistry:
    tier = agent_session.agent_session

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
        return os.getcwd()

    def resolve_role_definition(
        self, role_name: str, repo_root: Optional[str] = None
    ) -> role_registry.RoleDefinition:
        clean = role_name.split(":")[-1].strip().lower()
        for r in self.roles:
            if r.role_name == clean:
                return r
        return role_registry.RoleDefinition(
            role_name=clean,
            guide_path="guides/default.md",
            writable_file_patterns=[],
            readonly_file_patterns=[],
            feedback_role_deps=[],
            src_pattern="{unit_dir}/lib/{unit_name}.py",
            role_deps=[],
            verify_template="",
            verification_success_message="",
            active_component_types=["interface", "implementation"],
        )

    def list_roles(
        self, repo_root: Optional[str] = None
    ) -> Sequence[role_registry.RoleDefinition]:
        return self.roles


class FakeWorkspaceWorkManager:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.ready_items: List[Dict[str, Any]] = []
        self.blocked_items: List[Dict[str, Any]] = []

    def compute_role_work_queue(
        self,
        role_name: str,
        parts_dir: str,
        eval_root: str,
        force: bool = False,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return list(self.ready_items), list(self.blocked_items)

    def resolve_contract_files(
        self,
        target_file: str,
        eval_root: str,
        role_name: str = "",
    ) -> List[str]:
        return []


class FakeWorkspacePendingManager:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.pending: List[str] = []

    def get_pending_work(self, ws_root: str) -> List[str]:
        return list(self.pending)

    def set_pending_work(self, ws_root: str, items: Sequence[str]) -> None:
        self.pending = list(items)

    def clear_pending_work(self, ws_root: str) -> None:
        self.pending.clear()

    def remove_pending_target(self, ws_root: str, submitted_target: str) -> None:
        if submitted_target in self.pending:
            self.pending.remove(submitted_target)

    def is_pending_target_dirty(
        self,
        target: str,
        ws_root: str,
        main_root: Optional[str] = None,
        role_name: str = "",
    ) -> bool:
        return target in self.pending

    def get_pending_target_reasons(
        self,
        target: str,
        ws_root: str,
        main_root: Optional[str] = None,
        role_name: str = "",
    ) -> Sequence[str]:
        return (
            [f"Unacted feedback in {target}: Test feedback"]
            if target in self.pending
            else ()
        )


class FakeWorkspaceSynchronizer:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.pulled: List[Tuple[str, str, str]] = []
        self.refreshed: List[Tuple[str, str, str]] = []

    def pull(
        self,
        ws_root: str,
        main_root: str,
        role_name: str,
        dir_scope: str = "",
        silent: bool = False,
        delete_missing: bool = True,
    ) -> None:
        self.pulled.append((ws_root, main_root, role_name))

    def refresh_system_files(
        self,
        ws_root: str,
        main_root: str,
        role_name: str,
        dir_scope: str = "",
        silent: bool = False,
    ) -> None:
        self.refreshed.append((ws_root, main_root, role_name))


class FakeSubmissionCoordinator:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.submitted: List[Tuple[str, Optional[str]]] = []

    def submit_target_file(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> submit.SubmissionOutcome:
        self.submitted.append((target, role_name))
        return submit.SubmissionOutcome(accepted=True, message=f"✔ Stamped {target}")

    def resolve_submit_target(
        self,
        target: str,
        root: str,
        role_name: str,
        parts_dir: str,
    ) -> Tuple[str, str]:
        path = os.path.join(root, target) if not os.path.isabs(target) else target
        return path, os.path.splitext(os.path.basename(target))[0]

    def parse_unit_from_file_path(
        self, file_path: str, repo_root: str
    ) -> Tuple[str, str, str]:
        rel = os.path.relpath(file_path, repo_root)
        parts = rel.split(os.sep)
        unit = os.path.splitext(parts[-1])[0] if parts else ""
        return "parts/test_pkg", unit, "lib"


class FakeWorkspaceProvisioner:
    tier = agent_session.agent_session

    def copy_file_with_permissions(
        self,
        src: str,
        dst: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

    def unlock_workspace_directories(self, workspace_dir: str) -> None:
        pass

    def lock_workspace_directories(
        self,
        workspace_dir: str,
        role_name: Optional[str] = None,
        dir_scope: str = "",
        repo_root: Optional[str] = None,
    ) -> None:
        pass


class WorkspaceCheckImplTest(LifecycleTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.phase_cm.__enter__()

        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)

        with open(
            os.path.join(self.test_dir, app_info.DEFAULT_ROLE_DESCRIPTOR),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump({"role_name": "lib", "dir_scope": "pkg", "parts_dir": "pkg"}, f)

        self.role_lib = role_registry.RoleDefinition(
            role_name="lib",
            guide_path="guides/lib.md",
            writable_file_patterns=["*/lib/*.py"],
            readonly_file_patterns=[],
            feedback_role_deps=[],
            src_pattern="{unit_dir}/lib/{unit_name}.py",
            role_deps=["low"],
            verify_template="# noop",
            verification_success_message="Verified {unit_name}",
            active_component_types=["interface", "implementation"],
        )

        self.fake_reg = FakeWorkspaceRegistry([self.role_lib], repo_root=self.test_dir)
        self.fake_work = FakeWorkspaceWorkManager()
        self.fake_pending = FakeWorkspacePendingManager()
        self.fake_sync = FakeWorkspaceSynchronizer()
        self.fake_submit = FakeSubmissionCoordinator()
        self.fake_prov = FakeWorkspaceProvisioner()

        self.registry.register_instance(
            self.fake_reg,
            keys=[role_registry.WorkspaceRegistry],
            tier=agent_session.agent_session,
        )
        self.registry.register_instance(
            self.fake_work,
            keys=[work.WorkspaceWorkManager],
            tier=agent_session.agent_session,
        )
        self.registry.register_instance(
            self.fake_pending,
            keys=[pending.WorkspacePendingManager],
            tier=agent_session.agent_session,
        )
        self.registry.register_instance(
            self.fake_sync,
            keys=[sync.WorkspaceSynchronizer],
            tier=agent_session.agent_session,
        )
        self.registry.register_instance(
            self.fake_submit,
            keys=[submit.SubmissionCoordinator],
            tier=agent_session.agent_session,
        )
        self.registry.register_instance(
            self.fake_prov,
            keys=[provision.WorkspaceProvisioner],
            tier=agent_session.agent_session,
        )

        self.checker = check_impl.WorkspaceChecker()
        self.registry.register_instance(
            self.checker,
            keys=[check.WorkspaceChecker],
            tier=agent_session.agent_session,
        )

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)
        self.phase_cm.__exit__(None, None, None)

    def test_run_get_work_clean(self) -> None:
        import io
        from unittest.mock import patch

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            ret = self.checker.run_get_work(dir_scope="pkg")
            out = mock_out.getvalue()
        self.assertEqual(ret, 0)
        self.assertIn("[ROUND CONCLUSION DIRECTIVE]", out)
        self.assertIn("You have 0 ready targets", out)

    def test_run_get_work_ready_items(self) -> None:
        self.fake_work.ready_items = [
            {
                "role": "lib",
                "target_file": "pkg/parts/foo/lib/foo.py",
                "contract_files": [],
                "reasons": ["spec changed"],
            }
        ]
        import io
        from unittest.mock import patch

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            ret = self.checker.run_get_work(dir_scope="pkg")
            out = mock_out.getvalue()
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_pending.pending), 1)
        self.assertIn("Companion Guide to Follow:", out)
        self.assertIn("guides/lib.md", out)

    def test_run_get_work_pending_displays_dirty_reasons(self) -> None:
        self.fake_pending.pending = ["pkg/parts/foo/lib/foo.py"]
        import io
        from unittest.mock import patch

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            ret = self.checker.run_get_work(dir_scope="pkg")
            out = mock_out.getvalue()
        self.assertEqual(ret, 0)
        self.assertIn("READY FOR EXECUTION (Prerequisites satisfied):", out)
        self.assertIn("pkg/parts/foo/lib/foo.py", out)
        self.assertIn("Dirty Reasons:", out)
        self.assertIn(
            "Unacted feedback in pkg/parts/foo/lib/foo.py: Test feedback", out
        )
        self.assertIn("ACTIONABLE NEXT STEP:", out)
        self.assertNotIn("Error: Cannot call get_work", out)

    def test_extract_unacted_feedback_autofab_metadata(self) -> None:
        from autofab.parts.workspace_cli.lib.check_impl import _extract_unacted_feedback

        test_file = os.path.join(self.test_dir, "autofab_meta.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(
                "# --- AUTOFAB METADATA ---\n"
                "# LAST_CLEANED: 2026-10-10T12:00:00Z\n"
                "# FEEDBACK:\n"
                "# - [pretense_qa]: Fix off-by-one error in buffer indexing\n"
                "# --- END AUTOFAB METADATA ---\n"
            )
        fb = _extract_unacted_feedback(test_file)
        self.assertEqual(fb, ["Fix off-by-one error in buffer indexing"])

    def test_run_get_work_blocked_items_directs_round_conclusion(self) -> None:
        self.fake_work.ready_items = []
        self.fake_work.blocked_items = [
            {
                "role": "lib",
                "target_file": "pkg/parts/foo/lib/foo.py",
                "contract_files": [],
                "reasons": ["waiting on upstream"],
                "blocked_reasons": ["low specification missing"],
            }
        ]
        import io
        from unittest.mock import patch

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            ret = self.checker.run_get_work(dir_scope="pkg")
            out = mock_out.getvalue()
        self.assertEqual(ret, 0)
        self.assertIn("BLOCKED (Waiting on prerequisites):", out)
        self.assertIn("[ROUND CONCLUSION DIRECTIVE]", out)
        self.assertIn("All targets are blocked waiting on upstream prerequisites", out)

    def test_run_check_files_no_targets(self) -> None:
        ret = self.checker.run_check_files()
        self.assertEqual(ret, 0)

    def test_run_check_files_rejected_when_no_pending_work_and_empty_queue(
        self,
    ) -> None:
        unowned_file = os.path.join(
            self.test_dir, "pkg", "parts", "foo", "tests", "foo_test.py"
        )
        os.makedirs(os.path.dirname(unowned_file), exist_ok=True)
        with open(unowned_file, "w", encoding="utf-8") as f:
            f.write("# sample test\n")
        self.fake_pending.pending = []
        self.fake_work.ready_items = []
        self.checker.run_get_work(dir_scope="pkg")
        # Rejected when no target specified
        ret_no_tgt = self.checker.run_check_files()
        self.assertEqual(ret_no_tgt, 1)
        # Rejected when target not owned by active role
        ret = self.checker.run_check_files(target=unowned_file)
        self.assertEqual(ret, 1)

    def test_run_check_files_with_target(self) -> None:
        target_file = os.path.join(
            self.test_dir, "pkg", "parts", "foo", "lib", "foo.py"
        )
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# sample implementation\n")

        self.fake_pending.pending = [target_file]
        ret = self.checker.run_check_files(target=target_file)
        self.assertEqual(ret, 0)
        self.assertTrue(
            self.checker.is_checked_since_modification(self.test_dir, target_file)
        )

    def test_run_check_files_omits_redundant_feedback_on_pass(self) -> None:
        """Requirement: MUST omit repeating feedback on check_files when checks pass."""
        import io
        from contextlib import redirect_stdout

        target_file = os.path.join(
            self.test_dir, "pkg", "parts", "foo", "lib", "foo.py"
        )
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(
                "# --- AUTOFAB METADATA ---\n"
                "# FEEDBACK:\n"
                "# - [qa]: Fix edge case in cycle check\n"
                "# --- END AUTOFAB METADATA ---\n"
                "def test_fn(): pass\n"
            )
        self.fake_pending.pending = [target_file]
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = self.checker.run_check_files(target=target_file)
        out = buf.getvalue()
        self.assertEqual(ret, 0)
        self.assertIn("[PASSED] All local verification checks passed", out)
        self.assertIn(
            "Other checks to verify feedback or changes resolution will be performed after bin/submit is called.",
            out,
        )
        self.assertNotIn("[ATTENTION]", out)
        self.assertNotIn("pending feedback item", out)
        self.assertNotIn("Fix edge case in cycle check", out)

    def test_run_check_files_auditor_omits_post_submit_notice(self) -> None:
        """Requirement: Auditor roles MUST omit the post-submit checks notice upon check_files pass."""
        import io
        from contextlib import redirect_stdout

        self.fake_reg.roles.append(
            role_registry.RoleDefinition(
                role_name="qa",
                guide_path="guides/qa.md",
                writable_file_patterns=[],
                readonly_file_patterns=[],
                feedback_role_deps=[],
                audit_tag="QA_AUDIT",
                verify_template="echo 'OK'",
                src_pattern="",
            )
        )
        meta_file = os.path.join(self.test_dir, ".autofab_role.json")
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({"role": "qa", "parts_dir": "parts/test_pkg"}, f)

        target_file = os.path.join(self.test_dir, "parts", "test_pkg", "lib", "foo.py")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# sample file\n")
        self.fake_pending.pending = [target_file]
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = self.checker.run_check_files(target=target_file)
        out = buf.getvalue()
        self.assertEqual(ret, 0)
        self.assertIn("[PASSED] All verification checks passed", out)
        self.assertNotIn("Other checks to verify feedback or changes resolution", out)

    def test_run_check_files_rejected_when_target_not_pending_and_unowned(self) -> None:
        unowned_file = os.path.join(
            self.test_dir, "pkg", "parts", "foo", "tests", "foo_test.py"
        )
        os.makedirs(os.path.dirname(unowned_file), exist_ok=True)
        with open(unowned_file, "w", encoding="utf-8") as f:
            f.write("# sample test\n")
        self.fake_pending.pending = ["pkg/parts/other/lib/other.py"]
        ret = self.checker.run_check_files(target=unowned_file)
        self.assertEqual(ret, 1)

    def test_run_check_files_accepted_when_unassigned_target_owned_by_role(
        self,
    ) -> None:
        target_file = os.path.join(
            self.test_dir, "pkg", "parts", "foo", "lib", "foo.py"
        )
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# sample implementation\n")
        # Target not in pending work
        self.fake_pending.pending = ["pkg/parts/other/lib/other.py"]
        ret = self.checker.run_check_files(target=target_file)
        self.assertEqual(ret, 0)
        self.assertTrue(
            self.checker.is_checked_since_modification(self.test_dir, target_file)
        )

        # Target accepted even when queue is empty and .no_pending_work is set
        self.fake_pending.pending = []
        self.fake_work.ready_items = []
        self.checker.run_get_work(dir_scope="pkg")
        ret_empty = self.checker.run_check_files(target=target_file)
        self.assertEqual(ret_empty, 0)

    def test_run_check_files_pulls_before_check(self) -> None:
        main_repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, main_repo)
        target_file = os.path.join(
            self.test_dir, "pkg", "parts", "foo", "lib", "foo.py"
        )
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# sample implementation\n")
        self.fake_pending.pending = [target_file]
        ret = self.checker.run_check_files(target=target_file, repo_root=main_repo)
        self.assertEqual(ret, 0)
        self.assertTrue(len(self.fake_sync.pulled) > 0)

    def test_run_check_files_prioritizes_workspace_pythonpath(self) -> None:
        target_file = os.path.join(
            self.test_dir, "pkg", "parts", "foo", "lib", "foo.py"
        )
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# sample implementation\n")

        self.fake_pending.pending = [target_file]

        self.role_lib = role_registry.RoleDefinition(
            role_name="lib",
            guide_path="guides/lib.md",
            writable_file_patterns=["*/lib/*.py"],
            readonly_file_patterns=[],
            feedback_role_deps=[],
            src_pattern="{unit_dir}/lib/{unit_name}.py",
            role_deps=["low"],
            verify_template="echo OK",
            verification_success_message="Verified {unit_name}",
            active_component_types=["interface", "implementation"],
        )
        self.fake_reg.roles = [self.role_lib]
        fake_main_root = os.path.join(self.test_dir, "canonical_main")
        os.makedirs(fake_main_root, exist_ok=True)
        self.fake_reg.repo_root = fake_main_root

        captured_env: dict[str, str] = {}
        original_run = subprocess.run

        def mock_run(cmd, **kwargs):
            if "env" in kwargs:
                captured_env.update(kwargs["env"])
            return original_run("echo OK", shell=True, capture_output=True, text=True)

        from unittest.mock import patch

        with patch("subprocess.run", side_effect=mock_run):
            ret = self.checker.run_check_files(target=target_file)

        self.assertEqual(ret, 0)
        self.assertIn("PYTHONPATH", captured_env)
        pypaths = [
            os.path.realpath(p) for p in captured_env["PYTHONPATH"].split(os.pathsep)
        ]
        ws_real = os.path.realpath(self.test_dir)
        main_real = os.path.realpath(fake_main_root)
        self.assertIn(ws_real, pypaths)
        self.assertNotIn(main_real, pypaths)

    def test_run_check_files_propagates_max_failures_for_local_model(self) -> None:
        target_file = os.path.join(
            self.test_dir, "pkg", "parts", "foo", "lib", "foo.py"
        )
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# sample implementation\n")
        self.fake_pending.pending = [target_file]

        cfg_path = os.path.join(self.test_dir, "model_configs.toml")
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(
                'default = "qwen-moe-q6"\n'
                "[models.qwen-moe-q6]\n"
                'model = "Qwen3.6-35B-A3B-oQ6-mtp"\n'
                "tier = 1\n"
                "max_failures = 5\n"
            )

        role_lib = role_registry.RoleDefinition(
            role_name="lib",
            guide_path="guides/lib.md",
            writable_file_patterns=["*/lib/*.py"],
            readonly_file_patterns=[],
            feedback_role_deps=[],
            src_pattern="{unit_dir}/lib/{unit_name}.py",
            role_deps=["low"],
            verify_template="uv run pytest {unit_dir}/tests/{unit_name}_test.py",
            verification_success_message="Verified {unit_name}",
            active_component_types=["interface", "implementation"],
        )
        self.fake_reg.roles = [role_lib]

        captured_env: dict[str, str] = {}
        original_run = subprocess.run

        def mock_run(cmd: Any, **kwargs: Any) -> Any:
            if "env" in kwargs:
                captured_env.update(kwargs["env"])
            return original_run("echo OK", shell=True, capture_output=True, text=True)

        from unittest.mock import patch

        with patch("subprocess.run", side_effect=mock_run):
            ret = self.checker.run_check_files(target=target_file)

        self.assertEqual(ret, 0)
        self.assertIn("PYTEST_ADDOPTS", captured_env)
        self.assertIn("--maxfail=5", captured_env["PYTEST_ADDOPTS"])

    def test_run_check_files_defaults_max_failures_for_cloud_model(self) -> None:
        target_file = os.path.join(
            self.test_dir, "pkg", "parts", "foo", "lib", "foo.py"
        )
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# sample implementation\n")
        self.fake_pending.pending = [target_file]

        cfg_path = os.path.join(self.test_dir, "model_configs.toml")
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(
                'default = "cloud-model"\n'
                "[models.cloud-model]\n"
                'model = "cloud-model"\n'
                "tier = 2\n"
            )

        role_lib = role_registry.RoleDefinition(
            role_name="lib",
            guide_path="guides/lib.md",
            writable_file_patterns=["*/lib/*.py"],
            readonly_file_patterns=[],
            feedback_role_deps=[],
            src_pattern="{unit_dir}/lib/{unit_name}.py",
            role_deps=["low"],
            verify_template="uv run pytest {unit_dir}/tests/{unit_name}_test.py",
            verification_success_message="Verified {unit_name}",
            active_component_types=["interface", "implementation"],
        )
        self.fake_reg.roles = [role_lib]

        captured_env: dict[str, str] = {}
        original_run = subprocess.run

        def mock_run(cmd: Any, **kwargs: Any) -> Any:
            if "env" in kwargs:
                captured_env.update(kwargs["env"])
            return original_run("echo OK", shell=True, capture_output=True, text=True)

        from unittest.mock import patch

        with patch("subprocess.run", side_effect=mock_run):
            ret = self.checker.run_check_files(target=target_file)

        self.assertEqual(ret, 0)
        self.assertIn("PYTEST_ADDOPTS", captured_env)
        self.assertIn("--maxfail=100", captured_env["PYTEST_ADDOPTS"])

    def test_run_check_files_times_out(self) -> None:
        """CUJ: Check files handles verification command timeout gracefully."""
        target_file = os.path.join(
            self.test_dir, "pkg", "parts", "foo", "lib", "foo.py"
        )
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# sample implementation\n")
        self.fake_pending.pending = [target_file]

        role_lib = role_registry.RoleDefinition(
            role_name="lib",
            guide_path="guides/lib.md",
            writable_file_patterns=["*/lib/*.py"],
            readonly_file_patterns=[],
            feedback_role_deps=[],
            src_pattern="{unit_dir}/lib/{unit_name}.py",
            role_deps=["low"],
            verify_template="sleep 100",
            verification_success_message="Verified {unit_name}",
            active_component_types=["interface", "implementation"],
        )
        self.fake_reg.roles = [role_lib]

        from unittest.mock import patch

        def mock_timeout(cmd: Any, **kwargs: Any) -> Any:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=1.0)

        with patch("subprocess.run", side_effect=mock_timeout):
            ret = self.checker.run_check_files(target=target_file)

        self.assertEqual(ret, 1)
        rec_file = os.path.join(
            self.test_dir, app_info.DEFAULT_STATE_DIR, ".last_check_files.json"
        )
        self.assertTrue(os.path.isfile(rec_file))
        with open(rec_file, "r", encoding="utf-8") as f:
            records = json.load(f)
        self.assertFalse(records[os.path.realpath(target_file)]["passed"])

    def test_run_get_work_resolves_workspace_relative_guide_path(self) -> None:
        self.fake_reg.roles = [
            role_registry.RoleDefinition(
                role_name="lib",
                guide_path="autofab_py/guides/lib.md",
                writable_file_patterns=["lib/*.py"],
                readonly_file_patterns=["low/*.pyi"],
                feedback_role_deps=[],
            )
        ]
        self.fake_work.ready_items = [
            {
                "role": "lib",
                "target_file": "pkg/parts/foo/lib/foo.py",
                "contract_files": [],
                "reasons": ["spec changed"],
            }
        ]
        import io
        from unittest.mock import patch

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            ret = self.checker.run_get_work(dir_scope="pkg")
            out = mock_out.getvalue()
        self.assertIn("Companion Guide to Follow:", out)
        self.assertIn("guides/lib.md", out)
        self.assertNotIn("autofab_py/guides/lib.md", out)

    def test_run_get_work_fails_when_gemini_argon_mismatched_in_antigravity(
        self,
    ) -> None:
        with open(
            os.path.join(self.test_dir, app_info.DEFAULT_ROLE_DESCRIPTOR),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                {
                    "role": "lib",
                    "parts_dir": "pkg/parts",
                    "dir_scope": "pkg",
                    "model": "gemini-argon",
                    "harness": "antigravity",
                },
                f,
            )
        ag_root = os.path.join(self.test_dir, "fake_ag")
        cid = "00000000-1111-2222-3333-444444444444"
        logs_dir = os.path.join(ag_root, "brain", cid, ".system_generated", "logs")
        conv_dir = os.path.join(ag_root, "conversations")
        os.makedirs(logs_dir, exist_ok=True)
        os.makedirs(conv_dir, exist_ok=True)
        with open(
            os.path.join(logs_dir, "transcript.jsonl"), "w", encoding="utf-8"
        ) as f:
            f.write(
                json.dumps(
                    {
                        "content": f"assigned role workspace directory is '{self.test_dir}'"
                    }
                )
                + "\n"
            )

        import sqlite3

        db_path = os.path.join(conv_dir, f"{cid}.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE gen_metadata (idx INTEGER PRIMARY KEY, data BLOB)")
        conn.execute(
            "INSERT INTO gen_metadata (idx, data) VALUES (1, ?)",
            (b"model: gemini-3.8-flash",),
        )
        conn.commit()
        conn.close()

        import io
        from unittest.mock import patch

        with (
            patch.dict(os.environ, {"ANTIGRAVITY_BRAIN_DIR": ag_root}),
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            ret = self.checker.run_get_work(dir_scope="pkg")
            out = mock_out.getvalue()

        self.assertEqual(ret, 1)
        self.assertIn("Gemini Argon", out)

    def test_run_get_work_fails_when_gemini_carbon_mismatched_in_antigravity(
        self,
    ) -> None:
        with open(
            os.path.join(self.test_dir, app_info.DEFAULT_ROLE_DESCRIPTOR),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                {
                    "role": "lib",
                    "parts_dir": "pkg/parts",
                    "dir_scope": "pkg",
                    "model": "gemini-carbon",
                    "harness": "antigravity",
                },
                f,
            )
        ag_root = os.path.join(self.test_dir, "fake_ag_carbon")
        cid = "00000000-1111-2222-3333-555555555555"
        logs_dir = os.path.join(ag_root, "brain", cid, ".system_generated", "logs")
        conv_dir = os.path.join(ag_root, "conversations")
        os.makedirs(logs_dir, exist_ok=True)
        os.makedirs(conv_dir, exist_ok=True)
        with open(
            os.path.join(logs_dir, "transcript.jsonl"), "w", encoding="utf-8"
        ) as f:
            f.write(
                json.dumps(
                    {
                        "content": f"assigned role workspace directory is '{self.test_dir}'"
                    }
                )
                + "\n"
            )

        import sqlite3

        db_path = os.path.join(conv_dir, f"{cid}.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE gen_metadata (idx INTEGER PRIMARY KEY, data BLOB)")
        conn.execute(
            "INSERT INTO gen_metadata (idx, data) VALUES (1, ?)",
            (b"model: gemini-3.8-flash",),
        )
        conn.commit()
        conn.close()

        import io
        from unittest.mock import patch

        with (
            patch.dict(os.environ, {"ANTIGRAVITY_BRAIN_DIR": ag_root}),
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            ret = self.checker.run_get_work(dir_scope="pkg")
            out = mock_out.getvalue()

        self.assertEqual(ret, 1)
        self.assertIn("Gemini Carbon", out)
        self.assertIn("gemini-3.8-flash", out)

    def test_resolve_common_spec_files(self) -> None:
        role_low = role_registry.RoleDefinition(
            role_name="low",
            guide_path="guides/low.md",
            writable_file_patterns=["*/low/*.pyi"],
            readonly_file_patterns=[],
            feedback_role_deps=[],
            src_pattern="{unit_dir}/low/{unit_name}.pyi",
            role_deps=[],
            verify_template="# noop",
            verification_success_message="",
            active_component_types=["interface", "implementation"],
        )
        role_qa = role_registry.RoleDefinition(
            role_name="qa",
            guide_path="guides/qa.md",
            writable_file_patterns=[],
            readonly_file_patterns=[],
            feedback_role_deps=[],
            src_pattern="",
            role_deps=["lib", "test"],
            common_spec_roles=["low"],
            audit_tag="QA_AUDIT",
            verify_template="# noop",
            verification_success_message="",
            active_component_types=["interface", "implementation"],
        )
        self.fake_reg.roles = [self.role_lib, role_low, role_qa]

        spec_file = os.path.join(self.test_dir, "pkg", "parts", "foo", "low", "foo.pyi")
        os.makedirs(os.path.dirname(spec_file), exist_ok=True)
        with open(spec_file, "w", encoding="utf-8") as f:
            f.write("# low spec\n")

        resolved = check_impl.resolve_common_spec_files(
            role_name="qa",
            part_dir="pkg/parts/foo",
            unit_name="foo_impl",
            ws_root=self.test_dir,
            repo_root=self.test_dir,
        )
        self.assertEqual(resolved, ["pkg/parts/foo/low/foo.pyi"])

    def test_resolve_feedback_targets(self) -> None:
        role_pretense = role_registry.RoleDefinition(
            role_name="pretense",
            guide_path="guides/pretense.md",
            writable_file_patterns=["*/pretense/*_pretense.py"],
            readonly_file_patterns=[],
            feedback_role_deps=[],
            src_pattern="{unit_dir}/pretense/{unit_name}_pretense.py",
            role_deps=[],
            verify_template="# noop",
            verification_success_message="",
            active_component_types=["interface", "implementation"],
        )
        role_pretense_qa = role_registry.RoleDefinition(
            role_name="pretense_qa",
            guide_path="guides/pretense_qa.md",
            writable_file_patterns=[],
            readonly_file_patterns=[],
            feedback_role_deps=["lib", "pretense"],
            src_pattern="",
            role_deps=[],
            audit_tag="PRETENSE_QA_AUDIT",
            verify_template="# noop",
            verification_success_message="",
            active_component_types=["implementation"],
        )
        self.fake_reg.roles = [self.role_lib, role_pretense, role_pretense_qa]

        lib_file = os.path.join(
            self.test_dir, "pkg", "parts", "foo", "lib", "foo_impl.py"
        )
        pretense_file = os.path.join(
            self.test_dir, "pkg", "parts", "foo", "pretense", "foo_impl_pretense.py"
        )
        os.makedirs(os.path.dirname(lib_file), exist_ok=True)
        os.makedirs(os.path.dirname(pretense_file), exist_ok=True)
        with open(lib_file, "w") as f:
            f.write("# lib\n")
        with open(pretense_file, "w") as f:
            f.write("# pretense\n")

        fb = check_impl.resolve_feedback_targets(
            role_name="pretense_qa",
            part_dir="pkg/parts/foo",
            unit_name="foo_impl",
            ws_root=self.test_dir,
            repo_root=self.test_dir,
        )
        self.assertEqual(len(fb), 2)
        self.assertEqual(fb[0], "pkg/parts/foo/lib/foo_impl.py")
        self.assertEqual(fb[1], "pkg/parts/foo/pretense/foo_impl_pretense.py")

    def test_run_check_files_auditor_spec_reminder_upon_failure(self) -> None:
        role_low = role_registry.RoleDefinition(
            role_name="low",
            guide_path="guides/low.md",
            writable_file_patterns=["*/low/*.pyi"],
            readonly_file_patterns=[],
            feedback_role_deps=[],
            src_pattern="{unit_dir}/low/{unit_name}.pyi",
            role_deps=[],
            verify_template="# noop",
            verification_success_message="",
            active_component_types=["interface", "implementation"],
        )
        role_qa = role_registry.RoleDefinition(
            role_name="qa",
            guide_path="guides/qa.md",
            writable_file_patterns=[],
            readonly_file_patterns=[],
            feedback_role_deps=[],
            src_pattern="",
            role_deps=["lib", "test"],
            common_spec_roles=["low"],
            audit_tag="QA_AUDIT",
            verify_template="echo 'Assertion failed: expected 42 got 0' && exit 1",
            verification_success_message="",
            active_component_types=["interface", "implementation"],
        )
        self.fake_reg.roles = [self.role_lib, role_low, role_qa]

        with open(
            os.path.join(self.test_dir, app_info.DEFAULT_ROLE_DESCRIPTOR),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                {
                    "role_name": "qa",
                    "dir_scope": "pkg",
                    "parts_dir": "pkg/parts",
                    "common_spec_roles": ["low"],
                },
                f,
            )

        spec_file = os.path.join(self.test_dir, "parts", "test_pkg", "low", "foo.pyi")
        os.makedirs(os.path.dirname(spec_file), exist_ok=True)
        with open(spec_file, "w", encoding="utf-8") as f:
            f.write("# low spec\n")

        target_file = os.path.join(
            self.test_dir, "pkg", "parts", "foo", "lib", "foo.py"
        )
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# target file\n# CHANGE: Add base calculation logic\n")
        self.fake_pending.pending = [target_file]

        import io
        from unittest.mock import patch

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            ret = self.checker.run_check_files(target=target_file)
            out = mock_out.getvalue()

        self.assertNotEqual(ret, 0)
        self.assertIn(f"{app_info.get_app_title()} Triage Summary", out)
        self.assertIn('Author\'s Latest # CHANGE: "Add base calculation logic"', out)
        self.assertIn("Primary Failure: Assertion failed: expected 42 got 0", out)
        self.assertIn("ACTION REQUIRED:", out)
        self.assertIn(
            "You are an AUDITOR, not an author. Do NOT write debug scripts.", out
        )
        self.assertIn(
            'Stage blame attribution via: bin/blame <culprit_file> "<critique>"', out
        )
        self.assertIn(
            "Commit blame and conclude the target via: bin/submit <target>", out
        )
        self.assertIn(
            "After submitting, run 'bin/get_work' to inspect remaining units and conclude.",
            out,
        )
        self.assertIn(
            "[QA ARBITER REMINDER - EXPLAIN DEFECTS IN TERMS OF SPECIFICATION]", out
        )
        self.assertIn("parts/test_pkg/low/foo.pyi", out)
        self.assertIn(
            "Blame feedback MUST be provided in terms of how the file being blamed is not compliant with the common source of truth specification",
            out,
        )
        self.assertIn(
            "Line numbers MAY be mentioned ONLY IF they reference the file being blamed",
            out,
        )
        self.assertIn(
            "DO NOT expose details (line numbers, code snippets, or internal symbols) of other files",
            out,
        )
        self.assertNotIn("# pragma: no cover", out)
        self.assertNotIn("names starting with '_'", out)

    def test_run_check_files_milestone_git_checkpoint(self) -> None:
        import subprocess

        role_low = role_registry.RoleDefinition(
            role_name="low",
            guide_path="guides/low.md",
            writable_file_patterns=["*/low/*.pyi"],
            readonly_file_patterns=[],
            feedback_role_deps=[],
            src_pattern="{unit_dir}/low/{unit_name}.pyi",
            role_deps=[],
            verify_template="# noop",
            verification_success_message="Verification passed!",
            active_component_types=["interface", "implementation"],
        )
        self.fake_reg.roles.append(role_low)

        target_file = os.path.join(self.test_dir, "parts", "test_pkg", "low", "foo.pyi")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w") as f:
            f.write("# low spec\n")

        subprocess.run(
            ["git", "init"], cwd=self.test_dir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test Worker"],
            cwd=self.test_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", f"test@{app_info.APP_NAME}.local"],
            cwd=self.test_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "add", "-A"], cwd=self.test_dir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.test_dir,
            check=True,
            capture_output=True,
        )

        with open(target_file, "a") as f:
            f.write("# verified modification\n")
        self.fake_pending.pending = [target_file]

        ret = self.checker.run_check_files(target=target_file)
        self.assertEqual(ret, 0)

        git_log = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=self.test_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("Checkpoint: verified", git_log.stdout)

    def test_run_check_files_auditor_omits_git_checkpoint(self) -> None:
        import subprocess

        role_qa = role_registry.RoleDefinition(
            role_name="qa",
            guide_path="guides/qa.md",
            writable_file_patterns=[],
            readonly_file_patterns=["*/low/*.pyi"],
            feedback_role_deps=["lib"],
            audit_tag="QA_AUDIT",
            src_pattern="",
            role_deps=[],
            verify_template="# noop",
            verification_success_message="Verification passed!",
            active_component_types=["interface", "implementation"],
        )
        self.fake_reg.roles.append(role_qa)
        with open(
            os.path.join(self.test_dir, app_info.DEFAULT_ROLE_DESCRIPTOR),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                {"role_name": "qa", "dir_scope": "pkg", "parts_dir": "pkg/parts"}, f
            )

        target_file = os.path.join(self.test_dir, "parts", "test_pkg", "low", "foo.pyi")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w") as f:
            f.write("# low spec\n")

        subprocess.run(
            ["git", "init"], cwd=self.test_dir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test Worker"],
            cwd=self.test_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", f"test@{app_info.APP_NAME}.local"],
            cwd=self.test_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "add", "-A"], cwd=self.test_dir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.test_dir,
            check=True,
            capture_output=True,
        )

        with open(target_file, "a") as f:
            f.write("# some uncommitted edit\n")
        self.fake_pending.pending = [target_file]

        ret = self.checker.run_check_files(target=target_file)
        self.assertEqual(ret, 0)

        git_log = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=self.test_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual("Initial commit", git_log.stdout.strip())

    def test_run_check_files_fails_and_reverts_when_init_py_modified(self) -> None:
        main_repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, main_repo)

        main_init = os.path.join(main_repo, "parts", "test_pkg", "__init__.py")
        os.makedirs(os.path.dirname(main_init), exist_ok=True)
        with open(main_init, "w", encoding="utf-8") as f:
            f.write("# canonical empty init\n")

        ws_init = os.path.join(self.test_dir, "parts", "test_pkg", "__init__.py")
        os.makedirs(os.path.dirname(ws_init), exist_ok=True)
        with open(ws_init, "w", encoding="utf-8") as f:
            f.write("from .lib.foo import BufferEmptyError\n")

        target_file = os.path.join(self.test_dir, "parts", "test_pkg", "lib", "foo.py")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# impl\n")
        self.fake_pending.pending = [target_file]

        ret = self.checker.run_check_files(target=target_file, repo_root=main_repo)
        self.assertEqual(ret, 1)

        # Verify ws_init was reverted to canonical content
        with open(ws_init, "r", encoding="utf-8") as f:
            reverted_content = f.read()
        self.assertEqual(reverted_content, "# canonical empty init\n")

    def test_check_files_deduplicates_arbiter_reminders(self) -> None:
        self.fake_reg.roles.append(
            role_registry.RoleDefinition(
                role_name="qa",
                guide_path="guides/qa.md",
                writable_file_patterns=[],
                readonly_file_patterns=[],
                feedback_role_deps=[],
                verify_template="echo '[QA ARBITER REMINDER - EXPLAIN DEFECTS IN TERMS OF SPECIFICATION]\n• Blame feedback MUST be provided\nAssertionError: failed' && exit 1",
                audit_tag="QA_AUDIT",
                src_pattern="",
            )
        )
        meta_file = os.path.join(self.test_dir, ".autofab_role.json")
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({"role": "qa", "parts_dir": "parts/test_pkg"}, f)

        target_file = os.path.join(self.test_dir, "parts", "test_pkg", "lib", "foo.py")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# impl\n")
        self.fake_pending.pending = [target_file]

        import io
        from unittest.mock import patch

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            ret = self.checker.run_check_files(target=target_file)
            out = mock_out.getvalue()
        self.assertEqual(ret, 1)
        # The reminder should appear exactly once, not twice
        reminder_count = out.count(
            "[QA ARBITER REMINDER - EXPLAIN DEFECTS IN TERMS OF SPECIFICATION]"
        )
        self.assertEqual(reminder_count, 1)

    def test_check_files_scrubs_workspace_paths(self) -> None:
        self.fake_reg.roles.append(
            role_registry.RoleDefinition(
                role_name="qa",
                guide_path="guides/qa.md",
                writable_file_patterns=[],
                readonly_file_patterns=[],
                feedback_role_deps=[],
                verify_template=f"echo 'File \"{self.test_dir}/parts/test_pkg/lib/foo.py\", line 12' && exit 1",
                audit_tag="QA_AUDIT",
                src_pattern="",
            )
        )
        meta_file = os.path.join(self.test_dir, ".autofab_role.json")
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({"role": "qa", "parts_dir": "parts/test_pkg"}, f)

        target_file = os.path.join(self.test_dir, "parts", "test_pkg", "lib", "foo.py")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# impl\n")
        self.fake_pending.pending = [target_file]

        import io
        from unittest.mock import patch

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            ret = self.checker.run_check_files(target=target_file)
            out = mock_out.getvalue()
        self.assertEqual(ret, 1)
        self.assertIn('File "parts/test_pkg/lib/foo.py", line 12', out)
        self.assertNotIn(self.test_dir, out)

    def test_check_files_pretense_qa_reminder_and_deduplication(self) -> None:
        self.fake_reg.roles.append(
            role_registry.RoleDefinition(
                role_name="pretense_qa",
                guide_path="guides/pretense_qa.md",
                writable_file_patterns=[],
                readonly_file_patterns=[],
                feedback_role_deps=[],
                verify_template="echo '[PRETENSE QA ARBITER REMINDER - RULES ON ERRORS AND PRECONDITIONS]\n• Blame feedback MUST be provided\nAssertionError: failed' && exit 1",
                audit_tag="PRETENSE_QA_AUDIT",
                src_pattern="",
            )
        )
        meta_file = os.path.join(self.test_dir, ".autofab_role.json")
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({"role": "pretense_qa", "parts_dir": "parts/test_pkg"}, f)

        target_file = os.path.join(
            self.test_dir, "parts", "test_pkg", "lib", "foo_impl.py"
        )
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# impl\n")
        self.fake_pending.pending = [target_file]

        import io
        from unittest.mock import patch

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            ret = self.checker.run_check_files(target=target_file)
            out = mock_out.getvalue()
        self.assertEqual(ret, 1)
        reminder_count = out.count(
            "[PRETENSE QA ARBITER REMINDER - RULES ON ERRORS AND PRECONDITIONS]"
        )
        self.assertEqual(reminder_count, 1)
        self.assertIn("An unhandled *Error or test failure can indicate:", out)
        self.assertIn("Candidate Culprit Files:", out)
        self.assertIn("Candidate Files That Can Receive Feedback:", out)
        self.assertIn(
            "BLAME ROUTING (DETERMINE CULPRIT FROM SPECIFICATION & FEEDBACK TARGET SOURCE CODE):",
            out,
        )
        self.assertIn(
            "Look at the specification contracts and the source code of the candidate feedback files above.",
            out,
        )

    def test_print_triage_summary_lifecycle_resolution_error_routing_note(self) -> None:
        import io
        from unittest.mock import patch
        from autofab.parts.workspace_cli.lib.check_impl import _print_triage_summary

        with tempfile.TemporaryDirectory() as td:
            target_file = os.path.join(td, "parts", "pkg", "lib", "pkg_impl.py")
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            with open(target_file, "w", encoding="utf-8") as f:
                f.write("# CHANGE: Initial\n")

            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                _print_triage_summary(
                    target_path=target_file,
                    ws_root=td,
                    main_root=td,
                    role_name="pretense_qa",
                    part_dir="parts/pkg",
                    active_unit="pkg_impl",
                    stdout="LifecycleResolutionError: No singleton registered for RangeEngine",
                    stderr="",
                )
                out = mock_out.getvalue()

        self.assertIn("[COLLABORATOR LIFECYCLE ROUTING NOTE]", out)
        self.assertIn("MUST NEVER import sibling *_impl modules directly", out)

    def test_run_get_work_auditor_auto_submits_passing_targets(self) -> None:
        self.fake_reg.roles.append(
            role_registry.RoleDefinition(
                role_name="qa",
                guide_path="guides/qa.md",
                writable_file_patterns=[],
                readonly_file_patterns=[],
                feedback_role_deps=[],
                verify_template="echo 'OK'",
                audit_tag="QA_AUDIT",
                src_pattern="",
            )
        )
        meta_file = os.path.join(self.test_dir, ".autofab_role.json")
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({"role": "qa", "parts_dir": "parts/test_pkg"}, f)

        target_file = os.path.join(self.test_dir, "parts", "test_pkg", "lib", "foo.py")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# impl\n")

        self.fake_work.ready_items = [
            {
                "role": "qa",
                "target_file": target_file,
                "contract_files": [],
                "reasons": ["lib updated"],
            }
        ]

        import io
        from unittest.mock import patch

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            ret = self.checker.run_get_work(dir_scope="test_pkg")
            out = mock_out.getvalue()
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_submit.submitted), 1)
        self.assertEqual(self.fake_submit.submitted[0][0], target_file)
        self.assertIn("[AUTO-SUBMIT]", out)
        self.assertIn("[ROUND CONCLUSION DIRECTIVE]", out)
        self.assertEqual(len(self.fake_pending.pending), 0)

    def test_run_get_work_auditor_presents_failing_targets(self) -> None:
        self.fake_reg.roles.append(
            role_registry.RoleDefinition(
                role_name="qa",
                guide_path="guides/qa.md",
                writable_file_patterns=[],
                readonly_file_patterns=[],
                feedback_role_deps=[],
                verify_template="echo 'AssertionError: test failure' && exit 1",
                audit_tag="QA_AUDIT",
                src_pattern="",
            )
        )
        meta_file = os.path.join(self.test_dir, ".autofab_role.json")
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({"role": "qa", "parts_dir": "parts/test_pkg"}, f)

        target_file = os.path.join(self.test_dir, "parts", "test_pkg", "lib", "foo.py")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# impl\n")

        self.fake_work.ready_items = [
            {
                "role": "qa",
                "target_file": target_file,
                "contract_files": [],
                "reasons": ["lib updated"],
            }
        ]

        import io
        from unittest.mock import patch

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            ret = self.checker.run_get_work(dir_scope="test_pkg")
            out = mock_out.getvalue()
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_submit.submitted), 0)
        self.assertIn("READY FOR EXECUTION", out)
        self.assertIn(target_file, self.fake_pending.pending)
        self.assertNotIn("Triage Summary", out)
        self.assertNotIn("AssertionError: test failure", out)


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-30T11:00:00Z
# LAST_CHANGED: 2026-11-09T19:56:00Z
# CHANGE: Test reporting local checks passed and noting other checks occur after submit
# COVERAGE_AUDIT: 2026-10-18T19:13:51Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
