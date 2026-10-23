"""Unit tests for check_impl aligned with low-level specifications."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Sequence, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.control.lib import submit
from update_with_ai.parts.workspace_cli.lib import (
    check,
    check_impl,
    pending,
    work,
)
from update_with_ai.parts.workspace.lib import (
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

    def is_pending_target_dirty(
        self,
        target: str,
        ws_root: str,
        main_root: Optional[str] = None,
        role_name: str = "",
    ) -> bool:
        return target in self.pending


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


class WorkspaceCheckImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.phase_cm.__enter__()

        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)

        with open(os.path.join(self.test_dir, ".cleanroom_role.json"), "w", encoding="utf-8") as f:
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

        self.registry.register_instance(self.fake_reg, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(self.fake_work, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)
        self.registry.register_instance(self.fake_pending, keys=[pending.WorkspacePendingManager], tier=agent_session.agent_session)
        self.registry.register_instance(self.fake_sync, keys=[sync.WorkspaceSynchronizer], tier=agent_session.agent_session)
        self.registry.register_instance(self.fake_submit, keys=[submit.SubmissionCoordinator], tier=agent_session.agent_session)
        self.registry.register_instance(self.fake_prov, keys=[provision.WorkspaceProvisioner], tier=agent_session.agent_session)

        self.checker = check_impl.WorkspaceChecker()
        self.registry.register_instance(self.checker, keys=[check.WorkspaceChecker], tier=agent_session.agent_session)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)
        self.phase_cm.__exit__(None, None, None)

    def test_run_get_work_clean(self) -> None:
        ret = self.checker.run_get_work(dir_scope="pkg")
        self.assertEqual(ret, 0)

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
        self.assertEqual(ret, 1)
        self.assertEqual(len(self.fake_pending.pending), 1)
        self.assertIn("Companion Guide to Follow:", out)
        self.assertIn("guides/lib.md", out)

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
        self.assertIn("Conclude your round immediately without executing additional tools", out)

    def test_run_check_files_no_targets(self) -> None:
        ret = self.checker.run_check_files()
        self.assertEqual(ret, 0)

    def test_run_check_files_with_target(self) -> None:
        target_file = os.path.join(self.test_dir, "pkg", "parts", "foo", "lib", "foo.py")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# sample implementation\n")

        ret = self.checker.run_check_files(target=target_file)
        self.assertEqual(ret, 0)
        self.assertTrue(self.checker.is_checked_since_modification(self.test_dir, target_file))

    def test_run_check_files_prioritizes_workspace_pythonpath(self) -> None:
        target_file = os.path.join(self.test_dir, "pkg", "parts", "foo", "lib", "foo.py")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# sample implementation\n")

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
        pypaths = [os.path.realpath(p) for p in captured_env["PYTHONPATH"].split(os.pathsep)]
        ws_real = os.path.realpath(self.test_dir)
        main_real = os.path.realpath(fake_main_root)
        self.assertIn(ws_real, pypaths)
        self.assertNotIn(main_real, pypaths)

    def test_run_check_files_propagates_max_failures_for_local_model(self) -> None:
        target_file = os.path.join(self.test_dir, "pkg", "parts", "foo", "lib", "foo.py")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# sample implementation\n")

        cfg_path = os.path.join(self.test_dir, "model_configs.toml")
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(
                'default = "qwen-moe-q6"\n'
                '[models.qwen-moe-q6]\n'
                'model = "Qwen3.6-35B-A3B-oQ6-mtp"\n'
                'tier = 1\n'
                'max_failures = 5\n'
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
        target_file = os.path.join(self.test_dir, "pkg", "parts", "foo", "lib", "foo.py")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# sample implementation\n")

        cfg_path = os.path.join(self.test_dir, "model_configs.toml")
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(
                'default = "cloud-model"\n'
                '[models.cloud-model]\n'
                'model = "cloud-model"\n'
                'tier = 2\n'
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
        target_file = os.path.join(self.test_dir, "pkg", "parts", "foo", "lib", "foo.py")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# sample implementation\n")

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
        rec_file = os.path.join(self.test_dir, ".cleanroom", ".last_check_files.json")
        self.assertTrue(os.path.isfile(rec_file))
        with open(rec_file, "r", encoding="utf-8") as f:
            records = json.load(f)
        self.assertFalse(records[os.path.realpath(target_file)]["passed"])


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-18T19:13:51Z
# LAST_CHANGED: 2026-10-14T18:25:00Z
# CHANGE: Unit tests for check_impl
# COVERAGE_AUDIT: 2026-10-18T19:13:51Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
