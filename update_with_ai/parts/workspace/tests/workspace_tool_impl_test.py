# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T23:30:00Z
# CHANGE: unit test for workspace_tool_impl
# CODE_HASH: 456789abcdef
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

"""Unit tests for workspace_tool_impl."""

import os
import shutil
import tempfile
import unittest

from support.lib.lifecycle import enter_phase
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.control.lib import control_asm, src_metadata
from update_with_ai.parts.tools.lib import tools_asm
from update_with_ai.parts.workspace.lib import (
    workspace_asm,
    workspace_provision_impl,
    workspace_tool,
    workspace_tool_impl,
)


class WorkspaceToolImplTest(unittest.TestCase):
    def setUp(self) -> None:
        workspace_asm.__initialize__()
        control_asm.__initialize__()
        tools_asm.__initialize__()
        workspace_tool_impl.__initialize__()
        self.phase_cm = enter_phase(agent_session.agent_session)
        self.phase_cm.__enter__()

        self.test_dir = tempfile.mkdtemp()
        self.fake_repo = os.path.join(self.test_dir, "fake_repo")
        os.makedirs(self.fake_repo, exist_ok=True)
        self.orig_cwd = os.getcwd()

    def tearDown(self) -> None:
        if hasattr(self, "phase_cm"):
            self.phase_cm.__exit__(None, None, None)
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_runner_execute_command_help(self) -> None:
        runner = workspace_tool_impl.WorkspaceToolRunner()
        # Invalid command exits 2 via argparse SystemExit
        with self.assertRaises(SystemExit):
            runner.execute_command(["invalid_cmd"])

    def test_runner_get_work_clean(self) -> None:
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        lib_file = os.path.join(part_dir, "lib/config.py")
        src_metadata.update_metadata(
            lib_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )

        prov = workspace_provision_impl.WorkspaceProvisioner()
        desc = prov.commission("lib", "staging", repo_root=self.fake_repo)
        os.chdir(desc.workspace_dir)

        runner = workspace_tool_impl.WorkspaceToolRunner()
        ret = runner.execute_command(["get_work"])
        self.assertEqual(ret, 0)

    def test_runner_submit_and_blame_workflows(self) -> None:
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        low_file = os.path.join(part_dir, "low/config.pyi")
        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )

        prov = workspace_provision_impl.WorkspaceProvisioner()
        desc = prov.commission("lib", "staging", repo_root=self.fake_repo)
        os.chdir(desc.workspace_dir)

        # Blame contract
        runner = workspace_tool_impl.WorkspaceToolRunner()
        ret_blame = runner.execute_command(
            ["blame", "staging/parts/agent/low/config.pyi", "Spec missing parameter"]
        )
        self.assertEqual(ret_blame, 0)
        meta_low = src_metadata.extract_metadata(low_file)
        self.assertIsNotNone(meta_low)
        assert meta_low is not None
        self.assertIn("Spec missing parameter", meta_low.feedback[0])

    def test_runner_check_files(self) -> None:
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "high"), exist_ok=True)
        high_file = os.path.join(part_dir, "high/config.md")
        with open(high_file, "w", encoding="utf-8") as f:
            f.write("# config\n")

        prov = workspace_provision_impl.WorkspaceProvisioner()
        desc = prov.commission("high", "staging", repo_root=self.fake_repo)
        os.chdir(desc.workspace_dir)

        runner = workspace_tool_impl.WorkspaceToolRunner()
        # When no targets pending or specified, returns 0
        ret_no_targets = runner.execute_command(["check_files"])
        self.assertEqual(ret_no_targets, 0)

        # Target not found returns 1
        ret_not_found = runner.execute_command(["check_files", "nonexistent_target"])
        self.assertEqual(ret_not_found, 1)

    def test_runner_get_work_with_contracts(self) -> None:
        import io
        from contextlib import redirect_stdout

        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        low_file = os.path.join(part_dir, "low/config.pyi")
        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-05T12:00:00Z",
            last_changed="2026-10-05T12:00:00Z",
        )

        lib_file = os.path.join(part_dir, "lib/config.py")
        src_metadata.update_metadata(
            lib_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )

        prov = workspace_provision_impl.WorkspaceProvisioner()
        desc = prov.commission("lib", "staging", repo_root=self.fake_repo)
        os.chdir(desc.workspace_dir)

        runner = workspace_tool_impl.WorkspaceToolRunner()
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = runner.execute_command(["get_work"])
        out = buf.getvalue()
        self.assertEqual(ret, 1)
        self.assertIn("Contracts / Specifications to Read:", out)
        self.assertIn("staging/parts/agent/low/config.pyi", out)


if __name__ == "__main__":
    unittest.main()
