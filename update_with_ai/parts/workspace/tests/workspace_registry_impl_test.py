# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:37Z
# LAST_CHANGED: 2026-10-10T19:25:00Z
# CHANGE: add tests rejecting conflicting silent role dependencies and auditor role dependencies
# CODE_HASH: 094c5b1d4727
# COVERAGE_AUDIT: 2026-10-12T23:37:37Z
# QA_AUDIT: 2026-10-12T23:37:36Z
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
        for expected in ("high", "scenario", "planning", "low", "spec_qa", "lib", "test", "qa", "coverage"):
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

    def test_redundant_star_role_deps_in_role_deps_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_root:
            toml_file = os.path.join(tmp_root, "cleanroom_roles.toml")
            with open(toml_file, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.bad_role]\n'
                    'name = "bad_role"\n'
                    'src_pattern = "{unit_dir}/bad/{unit_name}.py"\n'
                    'role_deps = ["low"]\n'
                    'star_role_deps = ["low"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.ws_registry.resolve_role_definition("bad_role", repo_root=tmp_root)
            self.assertIn("redundantly declares star_role_deps", str(ctx.exception))

    def test_redundant_feedback_role_deps_in_role_deps_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_root:
            toml_file = os.path.join(tmp_root, "cleanroom_roles.toml")
            with open(toml_file, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.bad_role]\n'
                    'name = "bad_role"\n'
                    'src_pattern = "{unit_dir}/bad/{unit_name}.py"\n'
                    'role_deps = ["high"]\n'
                    'feedback_role_deps = ["high"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.ws_registry.resolve_role_definition("bad_role", repo_root=tmp_root)
            self.assertIn("redundantly declares feedback_role_deps", str(ctx.exception))

    def test_conflicting_silent_role_deps_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_root:
            toml_file = os.path.join(tmp_root, "cleanroom_roles.toml")
            with open(toml_file, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.bad_role]\n'
                    'name = "bad_role"\n'
                    'src_pattern = "{unit_dir}/bad/{unit_name}.py"\n'
                    'role_deps = ["high"]\n'
                    'silent_role_deps = ["high"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.ws_registry.resolve_role_definition("bad_role", repo_root=tmp_root)
            self.assertIn("as both a role dependency and a silent role dependency", str(ctx.exception))

    def test_auditor_role_in_role_deps_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_root:
            toml_file = os.path.join(tmp_root, "cleanroom_roles.toml")
            with open(toml_file, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.qa]\n'
                    'name = "qa"\n'
                    'src_pattern = ""\n\n'
                    '[roles.bad_role]\n'
                    'name = "bad_role"\n'
                    'src_pattern = "{unit_dir}/bad/{unit_name}.py"\n'
                    'role_deps = ["qa"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.ws_registry.resolve_role_definition("bad_role", repo_root=tmp_root)
            self.assertIn("Auditor roles can only be silent_role_deps", str(ctx.exception))

    def test_auditor_role_in_star_role_deps_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_root:
            toml_file = os.path.join(tmp_root, "cleanroom_roles.toml")
            with open(toml_file, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.spec_qa]\n'
                    'name = "spec_qa"\n'
                    'src_pattern = ""\n\n'
                    '[roles.bad_role]\n'
                    'name = "bad_role"\n'
                    'src_pattern = "{unit_dir}/bad/{unit_name}.py"\n'
                    'star_role_deps = ["spec_qa"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.ws_registry.resolve_role_definition("bad_role", repo_root=tmp_root)
            self.assertIn("Auditor roles can only be silent_role_deps", str(ctx.exception))

    def test_auditor_role_in_feedback_role_deps_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_root:
            toml_file = os.path.join(tmp_root, "cleanroom_roles.toml")
            with open(toml_file, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.coverage]\n'
                    'name = "coverage"\n'
                    'src_pattern = ""\n\n'
                    '[roles.bad_role]\n'
                    'name = "bad_role"\n'
                    'src_pattern = "{unit_dir}/bad/{unit_name}.py"\n'
                    'feedback_role_deps = ["coverage"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.ws_registry.resolve_role_definition("bad_role", repo_root=tmp_root)
            self.assertIn("Auditor roles can only be silent_role_deps", str(ctx.exception))

    def test_custom_auditor_role_in_role_deps_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_root:
            toml_file = os.path.join(tmp_root, "cleanroom_roles.toml")
            with open(toml_file, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.my_auditor]\n'
                    'name = "my_auditor"\n'
                    'src_pattern = ""\n\n'
                    '[roles.my_consumer]\n'
                    'name = "my_consumer"\n'
                    'src_pattern = "{unit_dir}/lib/{unit_name}.py"\n'
                    'role_deps = ["my_auditor"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.ws_registry.resolve_role_definition("my_consumer", repo_root=tmp_root)
            self.assertIn("Auditor roles can only be silent_role_deps", str(ctx.exception))

    def test_auditor_role_in_silent_role_deps_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_root:
            toml_file = os.path.join(tmp_root, "cleanroom_roles.toml")
            with open(toml_file, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.valid_consumer]\n'
                    'name = "valid_consumer"\n'
                    'src_pattern = "{unit_dir}/lib/{unit_name}.py"\n'
                    'silent_role_deps = ["qa"]\n'
                )
            role_def = self.ws_registry.resolve_role_definition("valid_consumer", repo_root=tmp_root)
            self.assertEqual(role_def.role_name, "valid_consumer")
            self.assertEqual(list(role_def.silent_role_deps), ["qa"])

    def test_resolve_role_with_dir_scope_bound_methodology(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_root:
            meth_dir = os.path.join(tmp_root, "custom_methodology")
            os.makedirs(meth_dir, exist_ok=True)
            roles_toml = os.path.join(meth_dir, "cleanroom_roles.toml")
            with open(roles_toml, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.scoped_role]\n'
                    'name = "scoped_role"\n'
                    'src_pattern = "{unit_dir}/scoped/{unit_name}.py"\n'
                )

            scoped_parts = os.path.join(tmp_root, "consumer_scope", "parts")
            os.makedirs(scoped_parts, exist_ok=True)
            cleanroom_toml = os.path.join(scoped_parts, "cleanroom.toml")
            with open(cleanroom_toml, "w", encoding="utf-8") as f:
                f.write('methodology = "//custom_methodology"\n')

            role_def = self.ws_registry.resolve_role_definition(
                "scoped_role", repo_root=tmp_root, dir_scope="consumer_scope/parts"
            )
            self.assertEqual(role_def.role_name, "scoped_role")

            roles = self.ws_registry.list_roles(repo_root=tmp_root, dir_scope="consumer_scope/parts")
            self.assertIn("scoped_role", [r.role_name for r in roles])

    def test_resolve_package_qualified_role_address(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_root:
            pkg_dir = os.path.join(tmp_root, "external_pkg")
            os.makedirs(pkg_dir, exist_ok=True)
            roles_toml = os.path.join(pkg_dir, "cleanroom_roles.toml")
            with open(roles_toml, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.ext_role]\n'
                    'name = "ext_role"\n'
                    'src_pattern = "{unit_dir}/ext/{unit_name}.py"\n'
                )

            role_def = self.ws_registry.resolve_role_definition(
                "//external_pkg:ext_role", repo_root=tmp_root
            )
            self.assertEqual(role_def.role_name, "ext_role")


if __name__ == "__main__":
    unittest.main()
