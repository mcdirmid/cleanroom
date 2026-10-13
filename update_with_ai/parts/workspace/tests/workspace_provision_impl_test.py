# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:37Z
# LAST_CHANGED: 2026-10-11T05:58:13Z
# CHANGE: Replace the undeclared private workspace registry constructor with a test double implementing the declared WorkspaceRegistry interface
# CODE_HASH: b57075bb7ac0
# COVERAGE_AUDIT: 2026-10-12T23:37:37Z
# QA_AUDIT: 2026-10-12T23:37:36Z
# --- END CLEANROOM METADATA ---

"""Unit tests for workspace_provision_impl."""

import json
import os
import stat
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.workspace.lib import (
    workspace_provision,
    workspace_provision_impl,
    workspace_registry,
)


class FakeWorkspaceRegistry:
    """Test double implementing the declared WorkspaceRegistry interface."""

    tier = agent_session.agent_session

    def __init__(self, roles) -> None:
        self.roles = list(roles)
        self.recorded: list[workspace_registry.WorkspaceDescriptor] = []

    def discover_repository_root(self, start_dir=None) -> str:
        return start_dir or os.getcwd()

    def resolve_role_definition(
        self, role_name_or_address, repo_root=None, dir_scope=None
    ) -> workspace_registry.RoleDefinition:
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


def _make_roles():
    low_role = workspace_registry.RoleDefinition(
        role_name="low",
        guide_path="guides/low.md",
        writable_file_patterns=["low/*.pyi", "**/low/*.pyi"],
        readonly_file_patterns=[],
        feedback_role_deps=[],
        src_pattern="{unit_dir}/low/{unit_name}.pyi",
    )
    lib_role = workspace_registry.RoleDefinition(
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
    test_role = workspace_registry.RoleDefinition(
        role_name="test",
        guide_path="guides/test.md",
        writable_file_patterns=["tests/*.py", "**/tests/*.py"],
        readonly_file_patterns=["low/*.pyi", "**/low/*.pyi"],
        feedback_role_deps=[],
        role_deps=["low"],
        stub_role_deps=["lib"],
        src_pattern="{unit_dir}/tests/{unit_name}_test.py",
    )
    return [low_role, lib_role, test_role]


class WorkspaceProvisionImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = get_default_registry()
        self.ws_registry = FakeWorkspaceRegistry(_make_roles())
        self.registry.register_instance(
            self.ws_registry,
            keys=[
                workspace_registry.WorkspaceRegistry,
            ],
            tier=agent_session.agent_session,
        )
        self.provisioner = workspace_provision_impl.WorkspaceProvisioner()
        self.registry.register_instance(
            self.provisioner,
            keys=[
                workspace_provision.WorkspaceProvisioner,
                workspace_provision_impl.WorkspaceProvisioner,
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

            # Project configurations and legacy Bazel files in repo root
            with open(os.path.join(repo_root, "pyproject.toml"), "w", encoding="utf-8") as f:
                f.write("[project]\nname = 'test'\n")
            with open(os.path.join(repo_root, "cleanroom_python_roles.toml"), "w", encoding="utf-8") as f:
                f.write(
                    "[methodology]\nname = 'python'\n\n"
                    "[roles.low]\nname = 'low'\nsrc_pattern = '{unit_dir}/low/{unit_name}.pyi'\n\n"
                    "[roles.lib]\nname = 'lib'\nsrc_pattern = '{unit_dir}/lib/{unit_name}.py'\n"
                    "star_role_deps = ['low']\n"
                )
            with open(os.path.join(repo_root, "notes.txt"), "w", encoding="utf-8") as f:
                f.write("# notes\n")
            with open(os.path.join(repo_root, "pyrightconfig.json"), "w", encoding="utf-8") as f:
                f.write("{}\n")

            desc = self.provisioner.commission(
                role_name="lib",
                dir_scope="test_scope",
                repo_root=repo_root,
            )

            ws_dir = desc.workspace_dir
            self.assertTrue(os.path.isdir(ws_dir))
            bin_dir = os.path.join(ws_dir, "bin")
            self.assertTrue(os.path.isdir(bin_dir))
            for tool in ("get_work", "check_files", "submit", "blame", "fail"):
                tool_p = os.path.join(bin_dir, tool)
                self.assertTrue(os.path.isfile(tool_p))
                mode = stat.S_IMODE(os.stat(tool_p).st_mode)
                self.assertEqual(mode & 0o755, 0o755)
            self.assertFalse(os.path.isfile(os.path.join(bin_dir, "coverage")))

            role_cfg = os.path.join(ws_dir, ".cleanroom_role.json")
            self.assertTrue(os.path.isfile(role_cfg))
            agents_md = os.path.join(ws_dir, "AGENTS.md")
            self.assertTrue(os.path.isfile(agents_md))
            with open(agents_md, "r", encoding="utf-8") as f:
                agents_text = f.read()
            self.assertIn("## Contamination Tripwire (Poison Pill)", agents_text)
            self.assertIn("CRITICAL CONTAMINATION: I read a file outside my assigned role workspace", agents_text)
            self.assertIn("## Command Execution Tripwire (Restricted Binaries Only)", agents_text)
            self.assertIn("bin/fail", agents_text)
            self.assertIn("## Unresolvable Impasse & Failure Protocol", agents_text)

            # Decoupled project configurations copied as read-only
            ws_pyproj = os.path.join(ws_dir, "pyproject.toml")
            self.assertTrue(os.path.isfile(ws_pyproj))
            self.assertEqual(stat.S_IMODE(os.stat(ws_pyproj).st_mode) & 0o444, 0o444)
            ws_roles = os.path.join(ws_dir, "cleanroom_python_roles.toml")
            self.assertTrue(os.path.isfile(ws_roles))
            self.assertEqual(stat.S_IMODE(os.stat(ws_roles).st_mode) & 0o444, 0o444)

            # Non-system files must NOT be copied into role workspace
            self.assertFalse(os.path.exists(os.path.join(ws_dir, "notes.txt")))
            self.assertFalse(os.path.exists(os.path.join(ws_dir, "pyrightconfig.json")))

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


if __name__ == "__main__":
    unittest.main()
