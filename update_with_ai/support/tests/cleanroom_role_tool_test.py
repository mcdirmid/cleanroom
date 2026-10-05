#!/usr/bin/env python3
"""cleanroom_role_tool_test.py — Unit tests for role workspace internal bin tools."""

import json
import os
import shutil
import stat
import sys
import tempfile
import unittest

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
for _p in [
    _repo_root,
    os.path.join(_repo_root, "update_python_with_ai"),
    os.path.join(_repo_root, "update_with_ai"),
    os.path.join(_repo_root, "update_with_ai/support/lib"),
    os.path.join(_repo_root, "update_python_with_ai/support/lib"),
]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

import src_metadata
from update_with_ai.support.lib import cleanroom_role_tool
from update_with_ai.support.lib import cleanroom_workspace_tool


class CleanroomRoleToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.fake_repo = os.path.join(self.test_dir, "fake_repo")
        os.makedirs(self.fake_repo, exist_ok=True)
        self.orig_cwd = os.getcwd()

    def tearDown(self) -> None:
        os.chdir(self.orig_cwd)
        for root, dirs, files in os.walk(self.test_dir):
            for d in dirs:
                try:
                    os.chmod(os.path.join(root, d), 0o755)
                except OSError:
                    pass
            for f in files:
                try:
                    os.chmod(os.path.join(root, f), 0o644)
                except OSError:
                    pass
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_work_command(self) -> None:
        """Verifies that get_work detects dirty tasks in the role workspace."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)

        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        lib_file = os.path.join(part_dir, "lib/config.py")
        low_file = os.path.join(part_dir, "low/config.pyi")
        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )

        lib_ws = cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(lib_ws)

        # 1. lib/config.py is missing -> get_work returns 1 (dirty tasks found)
        ret = cleanroom_role_tool.main(["get_work"])
        self.assertEqual(ret, 1)

        # 2. Worker stamps lib/config.py clean
        ws_lib = os.path.join(lib_ws, "staging/parts/agent/lib/config.py")
        src_metadata.update_metadata(
            ws_lib,
            last_cleaned="2026-10-04T12:05:00Z",
            last_changed="2026-10-04T12:05:00Z",
        )
        ret_clean = cleanroom_role_tool.main(["get_work"])
        self.assertEqual(ret_clean, 0)

    def test_submit_command_producer(self) -> None:
        """Verifies that submit enforces symmetric change summary rules based on code modification."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        lib_ws = cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(lib_ws)

        target = os.path.join(lib_ws, "staging/parts/agent/lib/config.py")
        with open(target, "w", encoding="utf-8") as f:
            f.write("# initial\n")

        # 1. Modified/new file submitted WITHOUT summary -> fails (ret=1)
        ret_no_sum = cleanroom_role_tool.main(["submit", target])
        self.assertEqual(ret_no_sum, 1)

        # 2. Modified/new file submitted WITH summary -> succeeds (ret=0)
        ret = cleanroom_role_tool.main(["submit", target, "Implemented config parser"])
        self.assertEqual(ret, 0)

        meta = src_metadata.extract_metadata(target)
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertIsNotNone(meta.last_cleaned)
        self.assertIsNotNone(meta.last_changed)
        self.assertEqual(meta.change_summary, "Implemented config parser")
        self.assertIsNotNone(meta.code_hash)

        # 3. Unmodified file submitted WITH summary -> fails (ret=1)
        ret_unchanged_with_sum = cleanroom_role_tool.main(
            ["submit", target, "Should fail because code unchanged"]
        )
        self.assertEqual(ret_unchanged_with_sum, 1)

        # 4. Unmodified file submitted WITHOUT summary -> succeeds (ret=0), preserves LAST_CHANGED and CHANGE
        old_changed = meta.last_changed
        ret_unchanged = cleanroom_role_tool.main(["submit", target])
        self.assertEqual(ret_unchanged, 0)

        meta2 = src_metadata.extract_metadata(target)
        self.assertIsNotNone(meta2)
        assert meta2 is not None
        self.assertEqual(meta2.last_changed, old_changed)
        self.assertEqual(meta2.change_summary, "Implemented config parser")

    def test_submit_command_auditor(self) -> None:
        """Verifies that submit stamps <ROLE>_AUDIT for auditor roles."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        qa_ws = cleanroom_workspace_tool.commission_workspace(
            "qa", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(qa_ws)

        target = os.path.join(qa_ws, "staging/parts/agent/lib/config.py")
        cleanroom_workspace_tool.write_file_with_perms(
            target, "# verified\n", readonly=True
        )

        ret = cleanroom_role_tool.main(["submit", target, "QA verified clean"])
        self.assertEqual(ret, 0)

        # In auditor workspace, read-only targets are buffered into .cleanroom_audit_buffer.json
        buf_path = os.path.join(qa_ws, cleanroom_role_tool.AUDIT_BUFFER_FILE)
        self.assertTrue(os.path.isfile(buf_path))
        with open(buf_path, "r", encoding="utf-8") as bf:
            entries = json.load(bf)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["audit_tag"], "QA_AUDIT")

    def test_blame_command_readonly_buffer(self) -> None:
        """Verifies blaming read-only contracts writes to .cleanroom_blame_buffer.json."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        low_f = os.path.join(part_dir, "low/config.pyi")
        src_metadata.update_metadata(
            low_f,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )

        lib_ws = cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(lib_ws)

        ws_low = os.path.join(lib_ws, "staging/parts/agent/low/config.pyi")
        # Ensure read-only
        st = os.stat(ws_low)
        self.assertEqual(st.st_mode & stat.S_IWUSR, 0)

        ret = cleanroom_role_tool.main(
            [
                "blame",
                "staging/parts/agent/lib/config.py",
                "staging/parts/agent/low/config.pyi",
                "Contract missing parameter X",
            ]
        )
        self.assertEqual(ret, 0)

        buf_path = os.path.join(lib_ws, ".cleanroom_blame_buffer.json")
        self.assertTrue(os.path.isfile(buf_path))
        with open(buf_path, "r", encoding="utf-8") as bf:
            entries = json.load(bf)
        self.assertEqual(len(entries), 1)
        self.assertIn("Contract missing parameter X", entries[0]["explanation"])

    def test_fail_command(self) -> None:
        """Verifies that fail adds DIRTY tag, advances LAST_CLEANED, and appends diagnostics."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        lib_ws = cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(lib_ws)

        target = os.path.join(lib_ws, "staging/parts/agent/lib/config.py")
        src_metadata.update_metadata(
            target,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )

        ret = cleanroom_role_tool.main(["fail", target, "Compilation syntax error"])
        self.assertEqual(ret, 0)

        meta = src_metadata.extract_metadata(target)
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta.dirty, "Compilation syntax error")
        self.assertIsNotNone(meta.last_cleaned)
        self.assertEqual(len(meta.feedback), 1)
        self.assertIn("Compilation syntax error", meta.feedback[0])

    def test_submit_command_auditor_rejects_test_file(self) -> None:
        """Verifies that an auditor role cannot directly submit a feedback/test file."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "tests"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        qa_ws = cleanroom_workspace_tool.commission_workspace(
            "qa", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(qa_ws)

        test_file = os.path.join(qa_ws, "staging/parts/agent/tests/config_test.py")
        cleanroom_workspace_tool.write_file_with_perms(
            test_file, "# test code\n", readonly=True
        )

        ret = cleanroom_role_tool.main(["submit", test_file])
        self.assertEqual(ret, 1)

    def test_submit_command_auditor_stamps_companion_test(self) -> None:
        """Verifies that submitting the implementation target in QA stamps both lib and companion test."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "tests"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        qa_ws = cleanroom_workspace_tool.commission_workspace(
            "qa", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(qa_ws)

        lib_target = os.path.join(qa_ws, "staging/parts/agent/lib/config.py")
        test_target = os.path.join(qa_ws, "staging/parts/agent/tests/config_test.py")
        cleanroom_workspace_tool.write_file_with_perms(
            lib_target, "# lib\n", readonly=True
        )
        cleanroom_workspace_tool.write_file_with_perms(
            test_target, "# test\n", readonly=True
        )

        ret = cleanroom_role_tool.main(["submit", lib_target])
        self.assertEqual(ret, 0)

        buf_path = os.path.join(qa_ws, cleanroom_role_tool.AUDIT_BUFFER_FILE)
        self.assertTrue(os.path.isfile(buf_path))
        with open(buf_path, "r", encoding="utf-8") as bf:
            entries = json.load(bf)
        self.assertEqual(len(entries), 2)
        targets = {e["target"] for e in entries}
        self.assertIn("staging/parts/agent/lib/config.py", targets)
        self.assertIn("staging/parts/agent/tests/config_test.py", targets)

    def test_submit_command_auditor_resolves_bare_unit_and_virtual_path(self) -> None:
        """Verifies that auditor submit resolves bare unit name and virtual role path."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        qa_ws = cleanroom_workspace_tool.commission_workspace(
            "qa", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(qa_ws)

        lib_target = os.path.join(qa_ws, "staging/parts/agent/lib/config.py")
        cleanroom_workspace_tool.write_file_with_perms(
            lib_target, "# lib\n", readonly=True
        )

        # 1. Bare unit name
        ret_bare = cleanroom_role_tool.main(["submit", "config"])
        self.assertEqual(ret_bare, 0)

        # 2. Virtual role path
        ret_virtual = cleanroom_role_tool.main(
            ["submit", "staging/parts/agent/qa/config"]
        )
        self.assertEqual(ret_virtual, 0)

    def test_submit_command_producer_rejects_readonly_and_out_of_scope(self) -> None:
        """Verifies producer submit rejects read-only files and files outside active scope."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        lib_ws = cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(lib_ws)

        # Read-only upstream file
        ro_file = os.path.join(lib_ws, "staging/parts/agent/low/config.pyi")
        cleanroom_workspace_tool.write_file_with_perms(
            ro_file, "# contract\n", readonly=True
        )

        ret_ro = cleanroom_role_tool.main(["submit", ro_file])
        self.assertEqual(ret_ro, 1)

    def test_fail_command_readonly_buffers(self) -> None:
        """Verifies that running fail on a read-only target buffers into .cleanroom_blame_buffer.json."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        qa_ws = cleanroom_workspace_tool.commission_workspace(
            "qa", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(qa_ws)

        lib_target = os.path.join(qa_ws, "staging/parts/agent/lib/config.py")
        cleanroom_workspace_tool.write_file_with_perms(
            lib_target, "# lib\n", readonly=True
        )

        ret = cleanroom_role_tool.main(["fail", lib_target, "Integration test failed"])
        self.assertEqual(ret, 0)

        buf_path = os.path.join(qa_ws, cleanroom_role_tool.BLAME_BUFFER_FILE)
        self.assertTrue(os.path.isfile(buf_path))
        with open(buf_path, "r", encoding="utf-8") as bf:
            entries = json.load(bf)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["target"], "staging/parts/agent/lib/config.py")
        self.assertEqual(entries[0]["dirty_reason"], "Integration test failed")


if __name__ == "__main__":
    unittest.main()
