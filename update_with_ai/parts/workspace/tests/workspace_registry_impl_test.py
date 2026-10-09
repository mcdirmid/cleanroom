# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: e9ab1cfb89bd
# COVERAGE_AUDIT: 2026-10-07T23:58:18Z
# QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Unit tests for workspace_registry_impl."""

import os
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.workspace.lib import workspace_registry, workspace_registry_impl


class WorkspaceRegistryImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.ws_registry = workspace_registry_impl.WorkspaceRegistry()
        self.registry.register_instance(
            self.ws_registry,
            keys=[
                workspace_registry.WorkspaceRegistry,
                workspace_registry_impl.WorkspaceRegistry,
            ],
            tier=agent_session.agent_session,
        )
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.phase_cm.__enter__()

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_resolve_standard_role_definition(self) -> None:
        role_def = self.ws_registry.resolve_role_definition("lib")
        self.assertEqual(role_def.role_name, "lib")
        self.assertIn("lib/*.py", role_def.writable_file_patterns)
        self.assertIn("low/*.pyi", role_def.readonly_file_patterns)
        self.assertEqual(list(role_def.silent_cross_role_deps), ["lib"])
        self.assertEqual(list(role_def.star_role_deps), ["low"])

        qa_def = self.ws_registry.resolve_role_definition(":qa")
        self.assertEqual(qa_def.role_name, "qa")
        self.assertEqual(qa_def.writable_file_patterns, [])
        self.assertEqual(qa_def.audit_tag, "QA_AUDIT")

    def test_unknown_role_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.ws_registry.resolve_role_definition("nonexistent_role_xyz")

    def test_list_roles(self) -> None:
        roles = self.ws_registry.list_roles()
        role_names = [r.role_name for r in roles]
        for expected in ("high", "planning", "spec_qa", "low", "low_qa", "lib", "test", "qa", "coverage"):
            self.assertIn(expected, role_names)

    def test_load_roles_from_toml_and_build_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_root:
            # 1. Fallback to BUILD.bazel when TOML is missing
            build_dir = os.path.join(tmp_root, "update_python_with_ai")
            os.makedirs(build_dir, exist_ok=True)
            build_file = os.path.join(build_dir, "BUILD.bazel")
            with open(build_file, "w", encoding="utf-8") as f:
                f.write(
                    'define_role(\n'
                    '    name = "build_role",\n'
                    '    src_pattern = "{unit_dir}/build/{unit_name}.py",\n'
                    ')\n'
                )
            role_build = self.ws_registry.resolve_role_definition("build_role", repo_root=tmp_root)
            self.assertEqual(role_build.role_name, "build_role")

            # 2. TOML takes precedence over BUILD.bazel
            toml_file = os.path.join(tmp_root, "cleanroom_python_roles.toml")
            with open(toml_file, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.toml_role]\n'
                    'name = "toml_role"\n'
                    'src_pattern = "{unit_dir}/toml/{unit_name}.py"\n'
                    'template_command = "uv run python -m test_scaffold"\n'
                )
            role_toml = self.ws_registry.resolve_role_definition("toml_role", repo_root=tmp_root)
            self.assertEqual(role_toml.role_name, "toml_role")
            self.assertEqual(role_toml.template_command, "uv run python -m test_scaffold")

    def test_compute_workspace_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_root:
            ws_dir = self.ws_registry.compute_workspace_dir(
                "lib", "staging", repo_root=tmp_root
            )
            self.assertTrue(ws_dir.endswith("lib_staging"))
            self.assertTrue("role_workspaces" in ws_dir)

            custom = os.path.join(tmp_root, "custom_ws")
            ws_dir_custom = self.ws_registry.compute_workspace_dir(
                "lib", "staging", repo_root=tmp_root, custom_dest=custom
            )
            self.assertEqual(ws_dir_custom, os.path.abspath(custom))

    def test_record_load_and_unregister_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_root:
            role_def = self.ws_registry.resolve_role_definition("lib")
            ws_dir = os.path.join(tmp_root, "role_workspaces", "test_lib_staging")
            desc = workspace_registry.WorkspaceDescriptor(
                workspace_dir=ws_dir,
                main_repository_root=tmp_root,
                directory_scope="staging",
                role_definition=role_def,
            )

            self.ws_registry.record_workspace(desc, repo_root=tmp_root)
            active = self.ws_registry.load_active_workspaces(repo_root=tmp_root)
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0].workspace_dir, ws_dir)
            self.assertEqual(active[0].role_definition.role_name, "lib")

            unregistered = self.ws_registry.unregister_workspace(ws_dir, repo_root=tmp_root)
            self.assertTrue(unregistered)
            active_after = self.ws_registry.load_active_workspaces(repo_root=tmp_root)
            self.assertEqual(len(active_after), 0)


if __name__ == "__main__":
    unittest.main()
