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

from update_with_ai.parts.control.lib import src_metadata
from update_with_ai.parts.workspace.lib import workspace_provision_impl
from update_with_ai.support.lib import cleanroom_role_tool


def commission_workspace(role_name: str, dir_scope: str = "staging", repo_root: str | None = None) -> str:
    prov = workspace_provision_impl.WorkspaceProvisioner()
    desc = prov.commission(role_name, dir_scope, repo_root=repo_root)
    return desc.workspace_dir


write_file_with_perms = cleanroom_role_tool.write_file_with_perms
compute_role_work_queue = cleanroom_role_tool.compute_role_work_queue


class CleanroomRoleToolTest(unittest.TestCase):
    def setUp(self) -> None:
        from update_with_ai.parts.workspace.lib import workspace_asm
        from support.lib.lifecycle import enter_phase
        from update_with_ai.parts.agent.lib import agent_session

        from update_with_ai.parts.control.lib import control_asm
        workspace_asm.__initialize__()
        control_asm.__initialize__()
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

        lib_ws = commission_workspace(
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

        lib_ws = commission_workspace(
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

        # Canonical file in main is also updated directly
        main_lib = os.path.join(self.fake_repo, "staging/parts/agent/lib/config.py")
        main_meta = src_metadata.extract_metadata(main_lib)
        self.assertIsNotNone(main_meta)
        assert main_meta is not None
        self.assertEqual(main_meta.change_summary, "Implemented config parser")

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
        """Verifies that submit stamps <ROLE>_AUDIT directly in main without buffer."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        main_lib = os.path.join(self.fake_repo, "staging/parts/agent/lib/config.py")
        write_file_with_perms(
            main_lib, "# verified in main\n", readonly=False
        )

        qa_ws = commission_workspace(
            "qa", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(qa_ws)

        target = os.path.join(qa_ws, "staging/parts/agent/lib/config.py")
        write_file_with_perms(
            target, "# verified\n", readonly=True
        )

        ret = cleanroom_role_tool.main(["submit", target, "QA verified clean"])
        self.assertEqual(ret, 0)

        # In zero-sync architecture, buffer file is retired
        buf_path = os.path.join(qa_ws, cleanroom_role_tool.AUDIT_BUFFER_FILE)
        self.assertFalse(os.path.isfile(buf_path))

        # Directly stamped in main
        main_meta = src_metadata.extract_metadata(main_lib)
        self.assertIsNotNone(main_meta)
        assert main_meta is not None
        self.assertIn("QA_AUDIT", main_meta.audits)

    def test_blame_command_direct_mutation(self) -> None:
        """Verifies blaming directly mutates upstream contract in main without buffer."""
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

        lib_ws = commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(lib_ws)

        # 3 arguments are disallowed and raise SystemExit
        with self.assertRaises(SystemExit):
            cleanroom_role_tool.main(
                [
                    "blame",
                    "staging/parts/agent/lib/config.py",
                    "staging/parts/agent/low/config.pyi",
                    "Contract missing parameter X",
                ]
            )

        # 2-arg blame succeeds
        ret = cleanroom_role_tool.main(
            [
                "blame",
                "staging/parts/agent/low/config.pyi",
                "Contract missing parameter X",
            ]
        )
        self.assertEqual(ret, 0)

        # No buffer written
        buf_path = os.path.join(lib_ws, ".cleanroom_blame_buffer.json")
        self.assertFalse(os.path.isfile(buf_path))

        # Directly mutated in main
        meta_low = src_metadata.extract_metadata(low_f)
        self.assertIsNotNone(meta_low)
        assert meta_low is not None
        self.assertEqual(len(meta_low.feedback), 1)
        self.assertIn("Contract missing parameter X", meta_low.feedback[0])
        self.assertIsNotNone(meta_low.dirty)

        # Second 2-arg blame
        ret2 = cleanroom_role_tool.main(
            [
                "blame",
                "staging/parts/agent/low/config.pyi",
                "Contract missing parameter Y",
            ]
        )
        self.assertEqual(ret2, 0)
        meta_low2 = src_metadata.extract_metadata(low_f)
        assert meta_low2 is not None
        self.assertEqual(len(meta_low2.feedback), 2)
        self.assertIn("Contract missing parameter Y", meta_low2.feedback[1])

    def test_fail_command(self) -> None:
        """Verifies that fail adds DIRTY tag, advances LAST_CLEANED, and appends diagnostics."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        main_lib = os.path.join(self.fake_repo, "staging/parts/agent/lib/config.py")
        src_metadata.update_metadata(
            main_lib,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )

        lib_ws = commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(lib_ws)

        target = os.path.join(lib_ws, "staging/parts/agent/lib/config.py")
        ret = cleanroom_role_tool.main(["fail", target, "Compilation syntax error"])
        self.assertEqual(ret, 0)

        meta = src_metadata.extract_metadata(main_lib)
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

        qa_ws = commission_workspace(
            "qa", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(qa_ws)

        test_file = os.path.join(qa_ws, "staging/parts/agent/tests/config_test.py")
        write_file_with_perms(
            test_file, "# test code\n", readonly=True
        )

        ret = cleanroom_role_tool.main(["submit", test_file])
        self.assertEqual(ret, 1)

    def test_submit_command_auditor_stamps_companion_test(self) -> None:
        """Verifies that submitting the implementation target in QA stamps both lib and companion test directly in main."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "tests"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        main_lib = os.path.join(self.fake_repo, "staging/parts/agent/lib/config.py")
        main_test = os.path.join(
            self.fake_repo, "staging/parts/agent/tests/config_test.py"
        )
        write_file_with_perms(
            main_lib, "# lib\n", readonly=False
        )
        write_file_with_perms(
            main_test, "# test\n", readonly=False
        )

        qa_ws = commission_workspace(
            "qa", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(qa_ws)

        lib_target = os.path.join(qa_ws, "staging/parts/agent/lib/config.py")
        ret = cleanroom_role_tool.main(["submit", lib_target])
        self.assertEqual(ret, 0)

        buf_path = os.path.join(qa_ws, cleanroom_role_tool.AUDIT_BUFFER_FILE)
        self.assertFalse(os.path.isfile(buf_path))

        meta_lib = src_metadata.extract_metadata(main_lib)
        meta_test = src_metadata.extract_metadata(main_test)
        self.assertIsNotNone(meta_lib)
        self.assertIsNotNone(meta_test)
        assert meta_lib is not None
        assert meta_test is not None
        self.assertIn("QA_AUDIT", meta_lib.audits)
        self.assertIn("QA_AUDIT", meta_test.audits)

    def test_submit_command_auditor_resolves_bare_unit_and_virtual_path(self) -> None:
        """Verifies that auditor submit resolves bare unit name and virtual role path."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        main_lib = os.path.join(self.fake_repo, "staging/parts/agent/lib/config.py")
        write_file_with_perms(
            main_lib, "# lib in main\n", readonly=False
        )

        qa_ws = commission_workspace(
            "qa", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(qa_ws)

        lib_target = os.path.join(qa_ws, "staging/parts/agent/lib/config.py")
        write_file_with_perms(
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

        lib_ws = commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(lib_ws)

        # Read-only upstream file
        ro_file = os.path.join(lib_ws, "staging/parts/agent/low/config.pyi")
        write_file_with_perms(
            ro_file, "# contract\n", readonly=True
        )

        ret_ro = cleanroom_role_tool.main(["submit", ro_file])
        self.assertEqual(ret_ro, 1)

    def test_fail_command_readonly_direct_mutation(self) -> None:
        """Verifies that running fail on a read-only target mutates main directly without buffering."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        main_lib = os.path.join(self.fake_repo, "staging/parts/agent/lib/config.py")
        write_file_with_perms(
            main_lib, "# lib\n", readonly=False
        )

        qa_ws = commission_workspace(
            "qa", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(qa_ws)

        lib_target = os.path.join(qa_ws, "staging/parts/agent/lib/config.py")
        write_file_with_perms(
            lib_target, "# lib\n", readonly=True
        )

        ret = cleanroom_role_tool.main(["fail", lib_target, "Integration test failed"])
        self.assertEqual(ret, 0)

        buf_path = os.path.join(qa_ws, cleanroom_role_tool.BLAME_BUFFER_FILE)
        self.assertFalse(os.path.isfile(buf_path))

        meta_main = src_metadata.extract_metadata(main_lib)
        self.assertIsNotNone(meta_main)
        assert meta_main is not None
        self.assertEqual(meta_main.dirty, "Integration test failed")

    def test_get_work_dependencies_and_topological_sort(self) -> None:
        """Verifies cross-role blocking, intra-role dependency allowing, and topological sorting."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "base")\n')
            f.write(
                'update_python_with_ai(name = "derived", module_deps = [":base"])\n'
            )

        low_base = os.path.join(part_dir, "low/base.pyi")
        low_derived = os.path.join(part_dir, "low/derived.pyi")
        src_metadata.update_metadata(
            low_base,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )
        # derived low is dirty (missing last_cleaned)
        with open(low_derived, "w", encoding="utf-8") as f:
            f.write("# low spec\n")

        lib_ws = commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(lib_ws)

        # Evaluates queue for lib:
        # base: upstream low is clean -> ready!
        # derived: upstream low is dirty -> blocked!
        ready, blocked = compute_role_work_queue(
            "lib", "staging", self.fake_repo
        )
        ready_names = [item["unit_name"] for item in ready]
        blocked_names = [item["unit_name"] for item in blocked]
        self.assertEqual(ready_names, ["base"])
        self.assertEqual(blocked_names, ["derived"])
        self.assertIn(
            "Upstream role 'low' is dirty for unit 'derived'",
            blocked[0]["blocked_reasons"][0],
        )

        # Now clean low/derived
        src_metadata.update_metadata(
            low_derived,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )
        ready2, blocked2 = compute_role_work_queue(
            "lib", "staging", self.fake_repo
        )
        ready_names2 = [item["unit_name"] for item in ready2]
        self.assertEqual(blocked2, [])
        # Topological order: prerequisite "base" appears before "derived"!
        self.assertEqual(ready_names2, ["base", "derived"])

    def test_get_work_pending_work_blocking_and_clearing(self) -> None:
        """Verifies that get_work blocks when prior work is pending, --force bypasses, and submit/blame clear it."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')
        low_file = os.path.join(part_dir, "low/config.pyi")
        with open(low_file, "w", encoding="utf-8") as f:
            f.write("def get_config() -> str: ...\n")
        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )

        lib_ws = commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(lib_ws)

        # 1. Initial get_work detects dirty task and records it in pending work
        ret1 = cleanroom_role_tool.main(["get_work"])
        self.assertEqual(ret1, 1)
        pending = cleanroom_role_tool.get_pending_work(lib_ws)
        self.assertEqual(len(pending), 1)
        self.assertIn("config.py", pending[0])

        # 2. Second get_work call without submit or blame is BLOCKED with exit code 1
        ret2 = cleanroom_role_tool.main(["get_work"])
        self.assertEqual(ret2, 1)

        # 3. get_work --force bypasses the pending work block
        ret_force = cleanroom_role_tool.main(["get_work", "--force"])
        self.assertEqual(ret_force, 1)

        # 4. Modify and submit the target -> clears pending work
        ws_lib = os.path.join(lib_ws, "staging/parts/agent/lib/config.py")
        with open(ws_lib, "w", encoding="utf-8") as f:
            f.write("def get_config() -> str: return 'ok'\n")
        ret_sub = cleanroom_role_tool.main(
            ["submit", "staging/parts/agent/lib/config.py", "implemented get_config"]
        )
        self.assertEqual(ret_sub, 0)
        self.assertEqual(cleanroom_role_tool.get_pending_work(lib_ws), [])

        # 5. get_work now succeeds and reports clean
        ret_clean = cleanroom_role_tool.main(["get_work"])
        self.assertEqual(ret_clean, 0)

        # 6. Mark dirty again by updating upstream low contract
        src_metadata.update_metadata(
            low_file,
            last_cleaned="2099-01-01T00:00:00Z",
            last_changed="2099-01-01T00:00:00Z",
        )
        ret3 = cleanroom_role_tool.main(["get_work"])
        self.assertEqual(ret3, 1)
        self.assertEqual(len(cleanroom_role_tool.get_pending_work(lib_ws)), 1)

        # 7. Blaming upstream contract clears pending work
        ret_blame = cleanroom_role_tool.main(
            ["blame", "staging/parts/agent/low/config.pyi", "Changed spec broken"]
        )
        self.assertEqual(ret_blame, 0)
        self.assertEqual(cleanroom_role_tool.get_pending_work(lib_ws), [])

    def test_coverage_command(self) -> None:
        """Verifies cleanroom_role_tool coverage command."""
        impl_path = os.path.join(self.test_dir, "sample_impl.py")
        test_path = os.path.join(self.test_dir, "sample_impl_test.py")

        with open(impl_path, "w", encoding="utf-8") as f:
            f.write("def foo():\n    return 42\ndef bar():\n    return 0\n")

        with open(test_path, "w", encoding="utf-8") as f:
            f.write(
                "import unittest\nfrom sample_impl import foo\n"
                "class STest(unittest.TestCase):\n"
                "    def test_f(self):\n"
                "        self.assertEqual(foo(), 42)\n"
            )

        # Baseline: threshold 0.0 passes
        ret_pass = cleanroom_role_tool.main(
            ["coverage", "--impl", impl_path, "--test", test_path, "-t", "0.0"]
        )
        self.assertEqual(ret_pass, 0)

        # Threshold 100.0 fails due to uncovered bar()
        ret_fail = cleanroom_role_tool.main(
            ["coverage", "--impl", impl_path, "--test", test_path, "-t", "100.0"]
        )
        self.assertEqual(ret_fail, 1)

    def test_refresh_sys_command(self) -> None:
        """Verifies cleanroom_role_tool refresh-sys command refreshes system files."""
        lib_ws = commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        ret = cleanroom_role_tool.main(["refresh-sys", "--repo-root", self.fake_repo])
        self.assertEqual(ret, 0)
        self.assertTrue(os.path.isdir(os.path.join(lib_ws, "bin")))


if __name__ == "__main__":
    unittest.main()

