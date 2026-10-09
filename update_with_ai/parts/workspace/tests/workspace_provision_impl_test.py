# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:02Z
# LAST_CHANGED: 2026-10-09T02:39:58Z
# CHANGE: test contamination tripwire in generated AGENTS.md
# CODE_HASH: c1c2e950c765
# COVERAGE_AUDIT: 2026-10-09T21:19:02Z
# QA_AUDIT: 2026-10-09T21:19:01Z
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


class WorkspaceProvisionImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = get_default_registry()
        self.ws_registry = workspace_registry._DefaultWorkspaceRegistry()
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
                    "role_deps = ['low']\nstar_role_deps = ['low']\n"
                )
            with open(os.path.join(repo_root, "MODULE.bazel"), "w", encoding="utf-8") as f:
                f.write("# legacy bazel module\n")
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

            # Decoupled project configurations copied as read-only
            ws_pyproj = os.path.join(ws_dir, "pyproject.toml")
            self.assertTrue(os.path.isfile(ws_pyproj))
            self.assertEqual(stat.S_IMODE(os.stat(ws_pyproj).st_mode) & 0o444, 0o444)
            ws_roles = os.path.join(ws_dir, "cleanroom_python_roles.toml")
            self.assertTrue(os.path.isfile(ws_roles))
            self.assertEqual(stat.S_IMODE(os.stat(ws_roles).st_mode) & 0o444, 0o444)

            # Bazel files must NOT be copied into role workspace
            self.assertFalse(os.path.exists(os.path.join(ws_dir, "MODULE.bazel")))
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
