# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:50:00Z
# CHANGE: Author unit tests for workspace_scaffold_impl
# CODE_HASH: 9584feb98d81
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Unit tests for workspace_scaffold_impl."""

import json
import os
import stat
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.workspace.lib import (
    workspace_roles,
    workspace_scaffold,
    workspace_scaffold_impl,
)


class WorkspaceScaffoldImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.scaffolder = workspace_scaffold_impl.WorkspaceScaffolder()
        self.registry.register_instance(
            self.scaffolder,
            keys=[
                workspace_scaffold.WorkspaceScaffolder,
                workspace_scaffold_impl.WorkspaceScaffolder,
            ],
            tier=agent_session.agent_session,
        )
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.phase_cm.__enter__()

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_write_file_with_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Writable file
            w_file = os.path.join(tmp_dir, "writable.txt")
            self.scaffolder.write_file_with_permissions(w_file, "write content", readonly=False)
            self.assertTrue(os.path.isfile(w_file))
            mode = stat.S_IMODE(os.stat(w_file).st_mode)
            self.assertEqual(mode, 0o644)

            # Read-only file
            ro_file = os.path.join(tmp_dir, "readonly.txt")
            self.scaffolder.write_file_with_permissions(ro_file, "ro content", readonly=True)
            self.assertTrue(os.path.isfile(ro_file))
            mode = stat.S_IMODE(os.stat(ro_file).st_mode)
            self.assertEqual(mode, 0o444)

            # Overwrite read-only file
            self.scaffolder.write_file_with_permissions(ro_file, "new content", readonly=False)
            with open(ro_file, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "new content")

            # Executable file
            exe_file = os.path.join(tmp_dir, "exec.sh")
            self.scaffolder.write_file_with_permissions(exe_file, "#!/bin/sh\n", executable=True)
            mode = stat.S_IMODE(os.stat(exe_file).st_mode)
            self.assertEqual(mode, 0o755)

    def test_deploy_runner_zipapps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bin_dir = os.path.join(tmp_dir, "bin")
            # Create a stale coverage file that should be removed
            os.makedirs(bin_dir, exist_ok=True)
            stale_cov = os.path.join(bin_dir, "coverage")
            with open(stale_cov, "w") as f:
                f.write("stale")

            self.scaffolder.deploy_runner_zipapps(bin_dir)
            self.assertFalse(os.path.exists(stale_cov))

            for tool in ("get_work", "check_files", "submit", "blame", "feedback", "fail"):
                tool_path = os.path.join(bin_dir, tool)
                self.assertTrue(os.path.isfile(tool_path), f"Missing {tool}")
                mode = stat.S_IMODE(os.stat(tool_path).st_mode)
                self.assertEqual(mode, 0o755)
                with open(tool_path, "rb") as f:
                    header = f.readline()
                    self.assertEqual(header, b"#!/usr/bin/env python3\n")

    def test_write_role_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.scaffolder.write_role_metadata(
                tmp_dir,
                role_name="lib",
                dir_scope="parts/example",
                model="gpt-4o",
                batch_size=3,
                max_feedback_chars=2000,
            )
            meta_path = os.path.join(tmp_dir, ".cleanroom_role.json")
            self.assertTrue(os.path.isfile(meta_path))
            mode = stat.S_IMODE(os.stat(meta_path).st_mode)
            self.assertEqual(mode, 0o644)

            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["role"], "lib")
            self.assertEqual(data["role_name"], "lib")
            self.assertEqual(data["dir_scope"], "parts/example")
            self.assertEqual(data["model"], "gpt-4o")
            self.assertEqual(data["batch_size"], 3)
            self.assertEqual(data["max_feedback_chars"], 2000)

    def test_write_role_agents_guide_author(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            role_def = workspace_roles.RoleDefinition(
                role_name="lib",
                guide_path="guides/lib.md",
                writable_file_patterns=["lib/*.py"],
                readonly_file_patterns=["low/*.pyi"],
                feedback_role_deps=[],
            )
            self.scaffolder.write_role_agents_guide(tmp_dir, role_def, "parts/sample")
            agents_md = os.path.join(tmp_dir, "AGENTS.md")
            self.assertTrue(os.path.isfile(agents_md))
            with open(agents_md, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Cleanroom Role Instructions: Lib", content)
            self.assertIn("Acting on Blame & Feedback", content)
            self.assertIn("bin/check_files", content)
            self.assertIn("bin/submit", content)

    def test_write_role_agents_guide_auditor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            role_def = workspace_roles.RoleDefinition(
                role_name="qa",
                guide_path="guides/qa.md",
                writable_file_patterns=[],
                readonly_file_patterns=["lib/*.py"],
                feedback_role_deps=["lib"],
            )
            self.scaffolder.write_role_agents_guide(tmp_dir, role_def, "parts/sample")
            agents_md = os.path.join(tmp_dir, "AGENTS.md")
            self.assertTrue(os.path.isfile(agents_md))
            with open(agents_md, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Cleanroom Role Instructions: Qa", content)
            self.assertIn("Delivering Blame & Feedback", content)
            self.assertIn("# CHANGE:", content)

    def test_create_missing_target_skeletons_from_template(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as ws_dir:
                template_file = "templates/skeleton.py"
                os.makedirs(os.path.join(repo_root, "templates"), exist_ok=True)
                with open(os.path.join(repo_root, template_file), "w", encoding="utf-8") as f:
                    f.write("# SKELETON TEMPLATE\n")

                parts_dir = os.path.join(repo_root, "pkg", "parts", "sample", "low")
                os.makedirs(parts_dir, exist_ok=True)
                with open(os.path.join(parts_dir, "foo.pyi"), "w", encoding="utf-8") as f:
                    f.write("# spec foo\n")

                role_def = workspace_roles.RoleDefinition(
                    role_name="lib",
                    guide_path="guides/lib.md",
                    writable_file_patterns=["pkg/parts/*/lib/*.py"],
                    readonly_file_patterns=[],
                    feedback_role_deps=[],
                    src_pattern="{unit_dir}/lib/{unit_name}.py",
                    template=template_file,
                )

                created = self.scaffolder.create_missing_target_skeletons(
                    workspace_dir=ws_dir,
                    repo_root=repo_root,
                    dir_scope="pkg",
                    role_def=role_def,
                )
                self.assertIn("pkg/parts/sample/lib/foo.py", created)
                created_file = os.path.join(ws_dir, "pkg/parts/sample/lib/foo.py")
                self.assertTrue(os.path.isfile(created_file))
                with open(created_file, "r", encoding="utf-8") as f:
                    self.assertEqual(f.read(), "# SKELETON TEMPLATE\n")
