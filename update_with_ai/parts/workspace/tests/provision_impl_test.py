"""Unit tests for provision_impl."""

import json
import os
import stat
import sys
import tempfile
from typing import Any, Optional, Sequence
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.workspace.lib import (
    provision,
    provision_impl,
    role_registry,
    scaffold,
    stub,
)


class FakeWorkspaceRegistry:
    """Test double implementing the declared WorkspaceRegistry interface."""

    tier = agent_session.agent_session

    def __init__(self, roles) -> None:
        self.roles = list(roles)
        self.recorded: list[role_registry.WorkspaceDescriptor] = []

    def discover_repository_root(self, start_dir=None) -> str:
        return start_dir or os.getcwd()

    def resolve_role_definition(
        self, role_name_or_address, repo_root=None, dir_scope=None
    ) -> role_registry.RoleDefinition:
        name = str(role_name_or_address).split(":")[-1].split("#")[0].strip().lower()
        for role in self.roles:
            if role.role_name == name:
                return role
        if not name and len(self.roles) == 1:
            return self.roles[0]
        raise KeyError(f"Role not found: {role_name_or_address}")

    def list_roles(self, repo_root=None, dir_scope=None):
        return list(self.roles)

    def compute_workspace_dir(
        self, role_name, dir_scope, repo_root=None, custom_dest=None
    ) -> str:
        if custom_dest:
            return custom_dest
        folder = f"{role_name}_{str(dir_scope).replace('/', '_').replace(':', '_')}"
        return os.path.join(repo_root or os.getcwd(), ".cleanroom_workspaces", folder)

    def record_workspace(self, descriptor, repo_root=None) -> None:
        self.recorded.append(descriptor)

    def unregister_workspace(self, workspace_dir, repo_root=None) -> bool:
        before = len(self.recorded)
        self.recorded = [d for d in self.recorded if d.workspace_dir != workspace_dir]
        return len(self.recorded) != before

    def load_active_workspaces(self, repo_root=None):
        return list(self.recorded)


class FakeWorkspaceStubSynthesizer:
    """Test double for WorkspaceStubSynthesizer."""

    tier = agent_session.agent_session

    def generate_readonly_test_stub(
        self, pyi_path, stem, out_path, dep_dir="", part_map=None
    ) -> None:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("# CLEANROOM TEST STUB (READ-ONLY)\nraise NotImplementedError()\n")
        try:
            os.chmod(out_path, 0o444)
        except OSError:
            pass

    def sync_all_stub_deps(
        self, workspace_dir, main_root, role_def, dir_scope="staging"
    ) -> int:
        synced = 0
        if not role_def.stub_role_deps:
            return 0
        scope_d = os.path.join(main_root, dir_scope) if dir_scope else main_root
        for root, _, files in os.walk(scope_d):
            for f in files:
                if f.endswith(".py") and f != "__init__.py":
                    rel = os.path.relpath(os.path.join(root, f), scope_d)
                    if self.is_stub_dep_file(rel, role_def, main_root):
                        dst = (
                            os.path.join(workspace_dir, dir_scope, rel)
                            if dir_scope
                            else os.path.join(workspace_dir, rel)
                        )
                        self.generate_readonly_test_stub(
                            None, os.path.splitext(f)[0], dst
                        )
                        synced += 1
        return synced

    def is_stub_dep_file(self, rel_path, role_def, repo_root=None) -> bool:
        if not role_def.stub_role_deps:
            return False
        if os.path.basename(rel_path) == "__init__.py":
            return False
        return "lib" in rel_path.split(os.sep) or "lib/" in rel_path

    def is_valid_test_stub(self, file_path: str) -> bool:
        if not os.path.isfile(file_path):
            return False
        with open(file_path, "r", encoding="utf-8") as f:
            return "CLEANROOM TEST STUB" in f.read()


def _make_roles():
    low_role = role_registry.RoleDefinition(
        role_name="low",
        guide_path="guides/low.md",
        writable_file_patterns=["low/*.pyi", "**/low/*.pyi"],
        readonly_file_patterns=[],
        feedback_role_deps=[],
        src_pattern="{unit_dir}/low/{unit_name}.pyi",
    )
    lib_role = role_registry.RoleDefinition(
        role_name="lib",
        guide_path="guides/lib.md",
        writable_file_patterns=["lib/*.py", "**/lib/*.py"],
        readonly_file_patterns=[
            "low/*.pyi",
            "**/low/*.pyi",
            "*.toml",
            "**/*.toml",
        ],
        feedback_role_deps=[],
        role_deps=["low"],
        star_role_deps=["low"],
        src_pattern="{unit_dir}/lib/{unit_name}.py",
    )
    test_role = role_registry.RoleDefinition(
        role_name="test",
        guide_path="guides/test.md",
        writable_file_patterns=["tests/*.py", "**/tests/*.py"],
        readonly_file_patterns=["low/*.pyi", "**/low/*.pyi"],
        feedback_role_deps=[],
        role_deps=["low"],
        stub_role_deps=["lib"],
        src_pattern="{unit_dir}/tests/{unit_name}_test.py",
    )
    qa_role = role_registry.RoleDefinition(
        role_name="qa",
        guide_path="guides/qa.md",
        writable_file_patterns=[],
        readonly_file_patterns=["low/*.pyi", "lib/*.py", "tests/*.py"],
        feedback_role_deps=["lib", "test"],
        audit_tag="QA_AUDIT",
    )
    return [low_role, lib_role, test_role, qa_role]


class FakeWorkspaceScaffolder:
    tier = agent_session.agent_session

    def deploy_runner_zipapps(
        self,
        bin_dir: str,
        role_def: Optional[role_registry.RoleDefinition] = None,
        can_blame: bool = True,
    ) -> None:
        os.makedirs(bin_dir, exist_ok=True)
        if role_def is not None:
            can_blame = bool(role_def.feedback_role_deps or role_def.audit_tag or not role_def.writable_file_patterns)
        tools = ["get_work", "check_files", "submit", "fail"]
        if can_blame:
            tools.append("blame")
        for tool in tools:
            p = os.path.join(bin_dir, tool)
            with open(p, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\n")
            os.chmod(p, 0o755)

    def write_role_metadata(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: Optional[int] = None,
        max_feedback_chars: Optional[int] = None,
    ) -> None:
        role_cfg = os.path.join(workspace_dir, ".cleanroom_role.json")
        data: dict[str, Any] = {
            "role": role_name,
            "role_name": role_name,
            "parts_dir": dir_scope,
            "dir_scope": dir_scope,
        }
        if model:
            data["model"] = model
        if batch_size is not None:
            data["batch_size"] = batch_size
        if max_feedback_chars is not None:
            data["max_feedback_chars"] = max_feedback_chars
        with open(role_cfg, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2))

    def write_role_agents_guide(
        self,
        workspace_dir: str,
        role_def: role_registry.RoleDefinition,
        dir_scope: str,
    ) -> None:
        agents_md = os.path.join(workspace_dir, "AGENTS.md")
        content = (
            "## Contamination Tripwire (Poison Pill)\n"
            "CRITICAL CONTAMINATION: I read a file outside my assigned role workspace\n"
            "## In-Workspace Execution & Permitted Commands\n"
            "## Mandatory Cleanroom Workflow Binaries\n"
            "bin/fail\n"
            "## Acting on Blame & Feedback\n"
            "## Unresolvable Impasse & Failure Protocol\n"
        )
        if role_def.audit_tag:
            content += (
                "## Delivering Blame & Feedback (Auditor Role Requirements)\n"
                "# CHANGE:\n"
                "NEVER recycle identical blame critiques\n"
            )
        with open(agents_md, "w", encoding="utf-8") as f:
            f.write(content)

    def create_missing_target_skeletons(
        self,
        workspace_dir: str,
        repo_root: str,
        dir_scope: str,
        role_def: Any,
    ) -> list[str]:
        return []

    def write_file_with_permissions(
        self,
        dst: str,
        content: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            try:
                os.chmod(dst, 0o644)
            except OSError:
                pass
        with open(dst, "w", encoding="utf-8") as f:
            f.write(content)
        mode = 0o444 if readonly else 0o644
        if executable:
            mode |= 0o111
        try:
            os.chmod(dst, mode)
        except OSError:
            pass


class WorkspaceProvisionImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.ws_registry = FakeWorkspaceRegistry(_make_roles())
        self.registry.register_instance(
            self.ws_registry,
            keys=[
                role_registry.WorkspaceRegistry,
            ],
            tier=agent_session.agent_session,
        )
        self.stub_synth = FakeWorkspaceStubSynthesizer()
        self.registry.register_instance(
            self.stub_synth,
            keys=[
                stub.WorkspaceStubSynthesizer,
            ],
            tier=agent_session.agent_session,
        )
        self.scaffolder = FakeWorkspaceScaffolder()
        self.registry.register_instance(
            self.scaffolder,
            keys=[
                scaffold.WorkspaceScaffolder,
            ],
            tier=agent_session.agent_session,
        )
        self.provisioner = provision_impl.WorkspaceProvisioner()
        self.registry.register_instance(
            self.provisioner,
            keys=[
                provision.WorkspaceProvisioner,
                provision_impl.WorkspaceProvisioner,
            ],
            tier=agent_session.agent_session,
        )
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.phase_cm.__enter__()

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_commission(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            scope_dir = os.path.join(repo_root, "test_scope", "lib")
            os.makedirs(scope_dir, exist_ok=True)
            target_f = os.path.join(scope_dir, "sample.py")
            with open(target_f, "w", encoding="utf-8") as f:
                f.write("# sample target\n")

            low_dir = os.path.join(repo_root, "test_scope", "low")
            os.makedirs(low_dir, exist_ok=True)
            contract_f = os.path.join(low_dir, "sample.pyi")
            with open(contract_f, "w", encoding="utf-8") as f:
                f.write("# sample contract\n")

            support_lib_dir = os.path.join(repo_root, "test_scope", "support", "lib")
            os.makedirs(support_lib_dir, exist_ok=True)
            with open(os.path.join(support_lib_dir, "lifecycle.py"), "w", encoding="utf-8") as f:
                f.write("class LifecycleRegistry:\n    pass\n")
            with open(os.path.join(support_lib_dir, "build_lint_common.py"), "w", encoding="utf-8") as f:
                f.write("# oracle AST parser\n")
            with open(os.path.join(support_lib_dir, "test_lint.py"), "w", encoding="utf-8") as f:
                f.write("# oracle test linter\n")

            guides_d = os.path.join(repo_root, "test_scope", "guides")
            os.makedirs(guides_d, exist_ok=True)
            with open(os.path.join(guides_d, "qa.md"), "w", encoding="utf-8") as f:
                f.write("# qa guide\n")
            tmpl_d = os.path.join(repo_root, "test_scope", "templates")
            os.makedirs(tmpl_d, exist_ok=True)
            with open(os.path.join(tmpl_d, "tmpl.md"), "w", encoding="utf-8") as f:
                f.write("# tmpl\n")

            parts_d = os.path.join(repo_root, "test_scope", "parts")
            os.makedirs(parts_d, exist_ok=True)
            with open(os.path.join(parts_d, "cleanroom.toml"), "w", encoding="utf-8") as f:
                f.write('methodology = "cleanroom_python_roles.toml"\n')

            # Project configurations and legacy Bazel files in repo root
            with open(os.path.join(repo_root, ".python-version"), "w", encoding="utf-8") as f:
                f.write("3.12.0\n")
            with open(os.path.join(repo_root, "pyproject.toml"), "w", encoding="utf-8") as f:
                f.write("[project]\nname = 'test'\n")
            with open(os.path.join(repo_root, "cleanroom_python_roles.toml"), "w", encoding="utf-8") as f:
                f.write(
                    "[methodology]\nname = 'python'\n\n"
                    "[roles.low]\nname = 'low'\nsrc_pattern = '{unit_dir}/low/{unit_name}.pyi'\n\n"
                    "[roles.lib]\nname = 'lib'\nsrc_pattern = '{unit_dir}/lib/{unit_name}.py'\n"
                    "star_role_deps = ['low']\n\n"
                    "[roles.qa]\nname = 'qa'\naudit_tag = 'QA_AUDIT'\nguide_path = 'guides/qa.md'\n"
                )
            with open(os.path.join(repo_root, "notes.txt"), "w", encoding="utf-8") as f:
                f.write("# notes\n")
            with open(os.path.join(repo_root, "pyrightconfig.json"), "w", encoding="utf-8") as f:
                f.write("{}\n")

            # Unbound consumer directory at repo root must NOT be copied into role workspace
            unbound_dir = os.path.join(repo_root, "unbound_consumer", "parts")
            os.makedirs(unbound_dir, exist_ok=True)
            with open(os.path.join(repo_root, "unbound_consumer", "pyproject.toml"), "w", encoding="utf-8") as f:
                f.write("[project]\nname = 'unbound'\n")
            with open(os.path.join(unbound_dir, "cleanroom.toml"), "w", encoding="utf-8") as f:
                f.write('methodology = "cleanroom_python_roles.toml"\n')

            desc = self.provisioner.commission(
                role_name="lib",
                dir_scope="test_scope",
                repo_root=repo_root,
            )

            ws_dir = desc.workspace_dir
            self.assertTrue(os.path.isdir(ws_dir))
            bin_dir = os.path.join(ws_dir, "bin")
            self.assertTrue(os.path.isdir(bin_dir))
            for tool in ("get_work", "check_files", "submit", "fail"):
                tool_p = os.path.join(bin_dir, tool)
                self.assertTrue(os.path.isfile(tool_p))
                mode = stat.S_IMODE(os.stat(tool_p).st_mode)
                self.assertEqual(mode & 0o755, 0o755)
            self.assertFalse(os.path.isfile(os.path.join(bin_dir, "blame")))
            self.assertFalse(os.path.isfile(os.path.join(bin_dir, "coverage")))

            desc_qa = self.provisioner.commission(
                role_name="qa",
                dir_scope="test_scope",
                repo_root=repo_root,
            )
            bin_dir_qa = os.path.join(desc_qa.workspace_dir, "bin")
            self.assertTrue(os.path.isfile(os.path.join(bin_dir_qa, "blame")))

            role_cfg = os.path.join(ws_dir, ".cleanroom_role.json")
            self.assertTrue(os.path.isfile(role_cfg))
            with open(role_cfg, "r", encoding="utf-8") as f:
                cfg_data = json.load(f)
            self.assertNotIn("main_workspace_root", cfg_data)
            self.assertNotIn("repo_root", cfg_data)
            agents_md = os.path.join(ws_dir, "AGENTS.md")
            self.assertTrue(os.path.isfile(agents_md))
            with open(agents_md, "r", encoding="utf-8") as f:
                agents_text = f.read()
            self.assertNotIn("main_workspace_root", agents_text)
            self.assertIn("## Contamination Tripwire (Poison Pill)", agents_text)
            self.assertIn("CRITICAL CONTAMINATION: I read a file outside my assigned role workspace", agents_text)
            self.assertIn("## In-Workspace Execution & Permitted Commands", agents_text)
            self.assertIn("## Mandatory Cleanroom Workflow Binaries", agents_text)
            self.assertIn("bin/fail", agents_text)
            self.assertIn("## Acting on Blame & Feedback", agents_text)
            self.assertIn("## Unresolvable Impasse & Failure Protocol", agents_text)

            qa_desc = self.provisioner.commission(
                role_name="qa",
                dir_scope="test_scope",
                repo_root=repo_root,
            )
            qa_agents_md = os.path.join(qa_desc.workspace_dir, "AGENTS.md")
            self.assertTrue(os.path.isfile(qa_agents_md))
            with open(qa_agents_md, "r", encoding="utf-8") as f:
                qa_agents_text = f.read()
            self.assertIn("## Delivering Blame & Feedback (Auditor Role Requirements)", qa_agents_text)
            self.assertIn("# CHANGE:", qa_agents_text)
            self.assertIn("NEVER recycle identical blame critiques", qa_agents_text)

            # Decoupled project configurations copied as read-only
            ws_pyver = os.path.join(ws_dir, ".python-version")
            self.assertTrue(os.path.isfile(ws_pyver))
            ws_pyproj = os.path.join(ws_dir, "pyproject.toml")
            self.assertTrue(os.path.isfile(ws_pyproj))
            self.assertEqual(stat.S_IMODE(os.stat(ws_pyproj).st_mode) & 0o444, 0o444)
            ws_roles = os.path.join(ws_dir, "cleanroom_python_roles.toml")
            self.assertTrue(os.path.isfile(ws_roles))
            self.assertEqual(stat.S_IMODE(os.stat(ws_roles).st_mode) & 0o444, 0o444)
            ws_parts_cfg = os.path.join(ws_dir, "test_scope", "parts", "cleanroom.toml")
            self.assertTrue(os.path.isfile(ws_parts_cfg))
            self.assertEqual(stat.S_IMODE(os.stat(ws_parts_cfg).st_mode) & 0o444, 0o444)

            # Support libraries: promoted to workspace root, runtime files copied, linters/runners excluded
            ws_support = os.path.join(ws_dir, "support", "lib")
            self.assertTrue(os.path.isfile(os.path.join(ws_support, "lifecycle.py")))
            self.assertFalse(os.path.exists(os.path.join(ws_support, "build_lint_common.py")))
            self.assertFalse(os.path.exists(os.path.join(ws_support, "test_lint.py")))

            # Promoted guides and templates at workspace root
            self.assertTrue(os.path.isdir(os.path.join(ws_dir, "guides")))
            self.assertTrue(os.path.isfile(os.path.join(ws_dir, "guides", "qa.md")))
            self.assertTrue(os.path.isdir(os.path.join(ws_dir, "templates")))
            self.assertTrue(os.path.isfile(os.path.join(ws_dir, "templates", "tmpl.md")))

            # Verify standard python import without PYTHONPATH
            import subprocess
            res = subprocess.run(
                [sys.executable, "-c", "from support.lib.lifecycle import LifecycleRegistry; print('OK')"],
                cwd=ws_dir,
                capture_output=True,
                text=True,
                env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("OK", res.stdout)

            # Non-system files must NOT be copied into role workspace
            self.assertFalse(os.path.exists(os.path.join(ws_dir, "notes.txt")))
            self.assertFalse(os.path.exists(os.path.join(ws_dir, "pyrightconfig.json")))
            self.assertFalse(os.path.exists(os.path.join(ws_dir, "unbound_consumer")))

            ws_contract = os.path.join(ws_dir, "test_scope", "low", "sample.pyi")
            self.assertTrue(os.path.isfile(ws_contract))
            contract_mode = stat.S_IMODE(os.stat(ws_contract).st_mode)
            self.assertEqual(contract_mode & 0o444, 0o444)

    def test_commission_synthesizes_stub_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            part_dir = os.path.join(repo_root, "scope", "parts", "sample")
            os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
            os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)

            spec_f = os.path.join(part_dir, "low", "config.pyi")
            with open(spec_f, "w", encoding="utf-8") as f:
                f.write("def get_config() -> str: ...\n")

            real_f = os.path.join(part_dir, "lib", "config.py")
            with open(real_f, "w", encoding="utf-8") as f:
                f.write("def get_config() -> str:\n    return 'secret_implementation'\n")

            with open(os.path.join(repo_root, "pyproject.toml"), "w", encoding="utf-8") as f:
                f.write("[project]\nname = 'test'\n")
            with open(os.path.join(repo_root, "cleanroom_roles.toml"), "w", encoding="utf-8") as f:
                f.write(
                    "[roles.low]\nname = 'low'\nsrc_pattern = '{unit_dir}/low/{unit_name}.pyi'\n\n"
                    "[roles.lib]\nname = 'lib'\nsrc_pattern = '{unit_dir}/lib/{unit_name}.py'\n"
                    "role_deps = ['low']\n\n"
                    "[roles.test]\nname = 'test'\nsrc_pattern = '{unit_dir}/tests/{unit_name}_test.py'\n"
                    "role_deps = ['low']\nstub_role_deps = ['lib']\n"
                )

            desc = self.provisioner.commission(
                role_name="test",
                dir_scope="scope",
                repo_root=repo_root,
            )

            ws_stub = os.path.join(desc.workspace_dir, "scope", "parts", "sample", "lib", "config.py")
            self.assertTrue(os.path.isfile(ws_stub))
            with open(ws_stub, "r", encoding="utf-8") as f:
                stub_content = f.read()
            self.assertIn("CLEANROOM TEST STUB", stub_content)
            self.assertIn("NotImplementedError", stub_content)
            self.assertNotIn("secret_implementation", stub_content)
            mode = os.stat(ws_stub).st_mode
            self.assertFalse(bool(mode & stat.S_IWUSR))

    def test_commission_with_reset_and_model(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            scope_dir = os.path.join(repo_root, "test_scope", "lib")
            os.makedirs(scope_dir, exist_ok=True)
            with open(os.path.join(scope_dir, "sample.py"), "w", encoding="utf-8") as f:
                f.write("# sample target\n")

            with open(os.path.join(repo_root, "cleanroom_roles.toml"), "w", encoding="utf-8") as f:
                f.write(
                    "[roles.lib]\nname = 'lib'\nsrc_pattern = '{unit_dir}/lib/{unit_name}.py'\n"
                )
            with open(os.path.join(repo_root, "model_configs.toml"), "w", encoding="utf-8") as f:
                f.write(
                    'default = "deepseek-v41-flash"\n\n'
                    '[models.deepseek-v41-flash]\n'
                    'model = "deepseek-v41-flash"\n'
                    'batch_size = 3\n'
                    'max_feedback_chars = 300\n'
                )

            desc = self.provisioner.commission(
                role_name="lib",
                dir_scope="test_scope",
                repo_root=repo_root,
                model="deepseek-v41-flash",
            )
            ws_dir = desc.workspace_dir
            role_cfg = os.path.join(ws_dir, ".cleanroom_role.json")
            with open(role_cfg, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.assertEqual(cfg.get("model"), "deepseek-v41-flash")
            self.assertEqual(cfg.get("batch_size"), 3)
            self.assertEqual(cfg.get("max_feedback_chars"), 300)
            self.assertNotIn("main_workspace_root", cfg)
            self.assertNotIn("repo_root", cfg)

            pending_file = os.path.join(ws_dir, ".cleanroom_pending_work.json")
            with open(pending_file, "w", encoding="utf-8") as f:
                json.dump({"targets": ["stale_target.py"]}, f)
            blame_buf = os.path.join(ws_dir, ".cleanroom_blame_buffer.json")
            with open(blame_buf, "w", encoding="utf-8") as f:
                json.dump([{"stale": True}], f)
            turn_log = os.path.join(ws_dir, ".cleanroom_turn_123.log")
            with open(turn_log, "w", encoding="utf-8") as f:
                f.write("old log\n")

            self.provisioner.commission(
                role_name="lib",
                dir_scope="test_scope",
                repo_root=repo_root,
                reset=True,
                model="deepseek-v41-flash",
            )
            self.assertFalse(os.path.exists(pending_file))
            self.assertFalse(os.path.exists(blame_buf))
            self.assertFalse(os.path.exists(turn_log))

    def test_commission_projects_metadata_for_writable_and_readonly_files(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            scope_dir = os.path.join(repo_root, "test_scope")
            parts_lib = os.path.join(scope_dir, "parts", "alpha", "lib")
            parts_low = os.path.join(scope_dir, "parts", "alpha", "low")
            os.makedirs(parts_lib, exist_ok=True)
            os.makedirs(parts_low, exist_ok=True)

            writable_src = os.path.join(parts_lib, "alpha.py")
            with open(writable_src, "w", encoding="utf-8") as f:
                f.write(
                    "# --- CLEANROOM METADATA ---\n"
                    "# LAST_CLEANED: 2026-10-15T17:42:47Z\n"
                    "# LAST_CHANGED: 2026-10-14T17:45:00Z\n"
                    "# CHANGE: implement alpha\n"
                    "# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z\n"
                    "# DIRTY: some reason\n"
                    "# FEEDBACK:\n"
                    "# - please check type hints\n"
                    "# --- END CLEANROOM METADATA ---\n"
                    "def alpha(): pass\n"
                )

            readonly_src = os.path.join(parts_low, "alpha.pyi")
            with open(readonly_src, "w", encoding="utf-8") as f:
                f.write(
                    "# --- CLEANROOM METADATA ---\n"
                    "# LAST_CLEANED: 2026-10-15T17:42:47Z\n"
                    "# LAST_CHANGED: 2026-10-14T17:45:00Z\n"
                    "# CHANGE: define contract\n"
                    "# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z\n"
                    "# --- END CLEANROOM METADATA ---\n"
                    "def alpha() -> None: ...\n"
                )

            desc = self.provisioner.commission(
                role_name="lib",
                dir_scope="test_scope",
                repo_root=repo_root,
            )
            ws_dir = desc.workspace_dir
            ws_writable = os.path.join(ws_dir, "test_scope", "parts", "alpha", "lib", "alpha.py")
            ws_readonly = os.path.join(ws_dir, "test_scope", "parts", "alpha", "low", "alpha.pyi")

            self.assertTrue(os.path.isfile(ws_writable))
            self.assertTrue(os.path.isfile(ws_readonly))

            with open(ws_writable, "r", encoding="utf-8") as f:
                writable_content = f.read()
            self.assertIn("CHANGE: implement alpha", writable_content)
            self.assertIn("CODE_HASH:", writable_content)
            self.assertIn("- please check type hints", writable_content)
            self.assertNotIn("LAST_CLEANED:", writable_content)
            self.assertNotIn("LAST_CHANGED:", writable_content)
            self.assertNotIn("SPEC_QA_AUDIT:", writable_content)
            self.assertNotIn("DIRTY:", writable_content)

            with open(ws_readonly, "r", encoding="utf-8") as f:
                readonly_content = f.read()
            self.assertIn("CHANGE: define contract", readonly_content)
            self.assertNotIn("CODE_HASH:", readonly_content)
            self.assertNotIn("LAST_CLEANED:", readonly_content)
            self.assertNotIn("LAST_CHANGED:", readonly_content)
            self.assertNotIn("SPEC_QA_AUDIT:", readonly_content)


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-20T23:45:00Z
# LAST_CHANGED: 2026-10-20T23:45:00Z
# CHANGE: Assert active methodology assets promoted to role workspace root
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
