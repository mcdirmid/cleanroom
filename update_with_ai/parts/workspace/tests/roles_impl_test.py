"""Unit tests for roles_impl."""

from __future__ import annotations
import os
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.workspace.lib import roles, roles_impl
from update_with_ai.parts.workspace.lib.roles_impl import RoleResolver


class WorkspaceRolesImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        roles_impl.__initialize__(self.registry)
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.resolver = self.scope.get_singleton(RoleResolver)

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_resolve_standard_role_definition(self) -> None:
        role_def = self.resolver.resolve_role_definition("lib")
        self.assertEqual(role_def.role_name, "lib")
        self.assertIn("lib/*.py", role_def.writable_file_patterns)
        self.assertIn("low/*.pyi", role_def.readonly_file_patterns)
        self.assertEqual(list(role_def.silent_cross_role_deps), ["lib"])
        self.assertEqual(list(role_def.star_role_deps), ["low"])

    def test_resolve_auditor_role_definition(self) -> None:
        qa_def = self.resolver.resolve_role_definition(":qa")
        self.assertEqual(qa_def.role_name, "qa")
        self.assertEqual(qa_def.writable_file_patterns, [])
        self.assertEqual(qa_def.audit_tag, "QA_AUDIT")

    def test_unknown_role_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.resolver.resolve_role_definition("nonexistent_role_xyz")

    def test_list_roles(self) -> None:
        roles = self.resolver.list_roles()
        role_names = [r.role_name for r in roles]
        for expected in ("high", "scenario", "planning", "low", "spec_qa", "lib", "test", "qa", "coverage"):
            self.assertIn(expected, role_names)

    def test_reject_redundant_feedback_in_role_deps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            toml_path = os.path.join(tmp_dir, "cleanroom_roles.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write(
                    "[roles.bad]\n"
                    'role_deps = ["other"]\n'
                    'feedback_role_deps = ["other"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.resolver.list_roles(repo_root=tmp_dir)
            self.assertIn("redundantly declares feedback_role_deps", str(ctx.exception))

    def test_reject_redundant_star_in_role_deps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            toml_path = os.path.join(tmp_dir, "cleanroom_roles.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write(
                    "[roles.bad]\n"
                    'role_deps = ["other"]\n'
                    'star_role_deps = ["other"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.resolver.list_roles(repo_root=tmp_dir)
            self.assertIn("redundantly declares star_role_deps", str(ctx.exception))

    def test_reject_conflicting_silent_role_deps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            toml_path = os.path.join(tmp_dir, "cleanroom_roles.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write(
                    "[roles.bad]\n"
                    'role_deps = ["other"]\n'
                    'silent_role_deps = ["other"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.resolver.list_roles(repo_root=tmp_dir)
            self.assertIn("both a role dependency and a silent role dependency", str(ctx.exception))

    def test_reject_auditor_in_role_deps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            toml_path = os.path.join(tmp_dir, "cleanroom_roles.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write(
                    "[roles.auditor]\n"
                    'audit_tag = "AUDITOR_AUDIT"\n\n'
                    "[roles.dev]\n"
                    'role_deps = ["auditor"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.resolver.list_roles(repo_root=tmp_dir)
            self.assertIn("Auditor roles can only be silent_role_deps", str(ctx.exception))


    def test_list_roles_pipeline_filtering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            toml_path = os.path.join(tmp_dir, "cleanroom_roles.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.lib]\nsrc_pattern = "lib/{unit}.py"\n\n'
                    '[roles.test]\nsrc_pattern = "tests/{unit}_test.py"\npipeline = "standard"\n\n'
                    '[roles.pretense]\nsrc_pattern = "pretense/{unit}_pretense.py"\npipeline = "pretense"\n'
                )
            # Create a dir_scope with cleanroom.toml setting pipeline = "pretense"
            scope_dir = os.path.join(tmp_dir, "my_scope")
            os.makedirs(scope_dir)
            with open(os.path.join(scope_dir, "cleanroom.toml"), "w", encoding="utf-8") as f:
                f.write('pipeline = "pretense"\n')

            roles = self.resolver.list_roles(repo_root=tmp_dir, dir_scope="my_scope")
            role_names = [r.role_name for r in roles]
            self.assertIn("lib", role_names)
            self.assertIn("pretense", role_names)
            self.assertNotIn("test", role_names)

            # Create standard scope
            std_dir = os.path.join(tmp_dir, "std_scope")
            os.makedirs(std_dir)
            with open(os.path.join(std_dir, "cleanroom.toml"), "w", encoding="utf-8") as f:
                f.write('pipeline = "standard"\n')

            std_roles = self.resolver.list_roles(repo_root=tmp_dir, dir_scope="std_scope")
            std_names = [r.role_name for r in std_roles]
            self.assertIn("lib", std_names)
            self.assertIn("test", std_names)
            self.assertNotIn("pretense", std_names)


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-25T21:55:00Z
# CHANGE: Add test for pipeline-aware role listing in roles_impl_test
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
