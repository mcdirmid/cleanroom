"""Unit tests for scaffold_impl."""

import json
import os
import stat
import tempfile
import unittest
import zipfile
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.workspace.lib import (
    roles,
    scaffold,
    scaffold_impl,
)


class WorkspaceScaffoldImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.scaffolder = scaffold_impl.WorkspaceScaffolder()
        self.registry.register_instance(
            self.scaffolder,
            keys=[
                scaffold.WorkspaceScaffolder,
                scaffold_impl.WorkspaceScaffolder,
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
                with zipfile.ZipFile(tool_path) as zf:
                    namelist = zf.namelist()
                    self.assertIn("__main__.py", namelist)
                    self.assertIn("cleanroom_role_tool.pyc", namelist)
                    self.assertIn("cleanroom_role_tool.py", namelist)
                    main_content = zf.read("__main__.py").decode("utf-8")
                    self.assertIn("sys.path.insert(0, curr)", main_content)
                    self.assertNotIn("sys.path.insert(0, pkg_dir)", main_content)
                    self.assertIn("cleanroom_roles.toml", namelist)
                    for name in namelist:
                        if name != "__main__.py":
                            self.assertTrue(
                                name.endswith((".pyc", ".py", ".toml")),
                                f"Expected module .pyc, .py, or .toml in zipapp but found: {name}",
                            )

            # When deployed for a role without blame capability, blame and feedback are omitted
            role_no_blame = roles.RoleDefinition(
                role_name="lib",
                guide_path="guides/lib.md",
                writable_file_patterns=["lib/*.py"],
                readonly_file_patterns=["low/*.pyi"],
                feedback_role_deps=[],
            )
            self.scaffolder.deploy_runner_zipapps(bin_dir, role_def=role_no_blame)
            self.assertFalse(os.path.exists(os.path.join(bin_dir, "blame")))
            self.assertFalse(os.path.exists(os.path.join(bin_dir, "feedback")))
            self.assertTrue(os.path.isfile(os.path.join(bin_dir, "get_work")))
            self.assertTrue(os.path.isfile(os.path.join(bin_dir, "check_files")))
            self.assertTrue(os.path.isfile(os.path.join(bin_dir, "submit")))
            self.assertTrue(os.path.isfile(os.path.join(bin_dir, "fail")))

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
            role_def = roles.RoleDefinition(
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
            self.assertIn("Modify your assigned target files in scope", content)
            self.assertIn("bin/check_files", content)
            self.assertIn("bin/submit", content)
            self.assertNotIn("bin/blame", content)
            self.assertIn("Metadata Inviolability & Projection", content)
            self.assertIn("canonical lifecycle timestamps", content)
            self.assertIn("Continuous Tool Execution & Operational Rules", content)
            self.assertIn("Ground Truth First", content)
            self.assertIn("Targeted Reads Over Full Dumps", content)
            self.assertIn("Round Conclusion Protocol", content)
            self.assertIn("When you have no outstanding work to do and `bin/get_work` does not give you more work to do", content)
            self.assertIn("Conclude with Text Only", content)
            self.assertNotIn("Incremental Authoring", content)

    def test_write_role_agents_guide_with_stubs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            role_def = roles.RoleDefinition(
                role_name="test",
                guide_path="guides/test.md",
                writable_file_patterns=["tests/*_test.py"],
                readonly_file_patterns=["low/*.pyi"],
                feedback_role_deps=[],
                stub_role_deps=["lib"],
            )
            self.scaffolder.write_role_agents_guide(tmp_dir, role_def, "parts/sample")
            agents_md = os.path.join(tmp_dir, "AGENTS.md")
            self.assertTrue(os.path.isfile(agents_md))
            with open(agents_md, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Cleanroom Role Instructions: Test", content)
            self.assertIn("Cleanroom Compilation Stubs", content)
            self.assertIn("CLEANROOM TEST STUB v4", content)
            self.assertIn("DO NOT EDIT STUBS", content)
            self.assertIn("DO NOT ASSERT STUB ERRORS", content)
            self.assertNotIn("bin/blame", content)

    def test_write_role_agents_guide_constrained_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            meta_path = os.path.join(tmp_dir, ".cleanroom_role.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"role": "lib", "model": "qwen-moe-q6"}, f)
            role_def = roles.RoleDefinition(
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
            self.assertIn("Incremental Authoring", content)
            self.assertIn("Output Token Ceiling Protection", content)

    def test_write_role_agents_guide_auditor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            role_def = roles.RoleDefinition(
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
            self.assertIn("Round Conclusion Protocol", content)

    def test_write_role_agents_guide_promoted_guide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            guides_dir = os.path.join(tmp_dir, "guides")
            os.makedirs(guides_dir, exist_ok=True)
            with open(os.path.join(guides_dir, "lib.md"), "w", encoding="utf-8") as f:
                f.write("# Lib guide\n")
            role_def = roles.RoleDefinition(
                role_name="lib",
                guide_path="pkg/guides/lib.md",
                writable_file_patterns=["lib/*.py"],
                readonly_file_patterns=["low/*.pyi"],
                feedback_role_deps=[],
            )
            self.scaffolder.write_role_agents_guide(tmp_dir, role_def, "parts/sample")
            agents_md = os.path.join(tmp_dir, "AGENTS.md")
            self.assertTrue(os.path.isfile(agents_md))
            with open(agents_md, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("guides/lib.md", content)
            self.assertNotIn("pkg/guides/lib.md", content)

    def test_write_role_agents_guide_fused_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            role_def = roles.RoleDefinition(
                role_name="baseline",
                guide_path="guides/baseline.md",
                writable_file_patterns=["lib/*.py", "tests/*_test.py"],
                readonly_file_patterns=["low/*.pyi"],
                feedback_role_deps=[],
                fused_roles=["lib", "test", "qa", "coverage"],
            )
            self.scaffolder.write_role_agents_guide(tmp_dir, role_def, "parts/sample")
            agents_md = os.path.join(tmp_dir, "AGENTS.md")
            self.assertTrue(os.path.isfile(agents_md))
            with open(agents_md, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("bin/verify_lib", content)
            self.assertIn("bin/verify_test", content)
            self.assertIn("bin/verify_coverage", content)
            self.assertIn("Prune Uncontracted Defensive Code", content)
            self.assertIn("prune and delete the unreachable defensive code", content)

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

                role_def = roles.RoleDefinition(
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

    def test_create_missing_target_skeletons_from_promoted_workspace_template(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as ws_dir:
                ws_tmpl_dir = os.path.join(ws_dir, "templates")
                os.makedirs(ws_tmpl_dir, exist_ok=True)
                with open(os.path.join(ws_tmpl_dir, "hls_template.md"), "w", encoding="utf-8") as f:
                    f.write("# PROMOTED HLS TEMPLATE\n")

                parts_dir = os.path.join(repo_root, "pkg", "parts", "sample", "low")
                os.makedirs(parts_dir, exist_ok=True)
                with open(os.path.join(parts_dir, "bar.pyi"), "w", encoding="utf-8") as f:
                    f.write("# spec bar\n")

                role_def = roles.RoleDefinition(
                    role_name="high",
                    guide_path="pkg/guides/high.md",
                    writable_file_patterns=["pkg/parts/*/high/*.md"],
                    readonly_file_patterns=[],
                    feedback_role_deps=[],
                    src_pattern="{unit_dir}/high/{unit_name}.md",
                    template="pkg/templates/hls_template.md",
                )

                created = self.scaffolder.create_missing_target_skeletons(
                    workspace_dir=ws_dir,
                    repo_root=repo_root,
                    dir_scope="pkg",
                    role_def=role_def,
                )
                self.assertIn("pkg/parts/sample/high/bar.md", created)
                created_file = os.path.join(ws_dir, "pkg/parts/sample/high/bar.md")
                self.assertTrue(os.path.isfile(created_file))
                with open(created_file, "r", encoding="utf-8") as f:
                    self.assertEqual(f.read(), "# PROMOTED HLS TEMPLATE\n")

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-20T23:45:00Z
# LAST_CHANGED: 2026-10-20T23:45:00Z
# CHANGE: Test companion guide and template resolution from workspace root
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
