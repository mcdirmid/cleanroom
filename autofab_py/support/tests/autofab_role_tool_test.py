#!/usr/bin/env python3
"""autofab_role_tool_test.py — Unit tests for role workspace internal bin tools."""

import json
import os
import shutil
import stat
import sys
import tempfile
from typing import Any
import unittest

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
for _p in [
    _repo_root,
    os.path.join(_repo_root, "autofab_py"),
    os.path.join(_repo_root, "autofab"),
    os.path.join(_repo_root, "autofab/support/lib"),
    os.path.join(_repo_root, "autofab_py/support/lib"),
]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from autofab.parts.metadata.lib import src_metadata
from autofab.parts.workspace.lib import provision_impl
from autofab.support.lib import autofab_role_tool
from support.lib import app_info


def commission_workspace(role_name: str, dir_scope: str = "staging", repo_root: str | None = None) -> str:
    prov = provision_impl.WorkspaceProvisioner()
    desc = prov.commission(role_name, dir_scope, repo_root=repo_root)
    return desc.workspace_dir


write_file_with_perms = autofab_role_tool.write_file_with_perms
compute_role_work_queue = autofab_role_tool.compute_role_work_queue


class CleanroomRoleToolTest(unittest.TestCase):
    phase_cm: Any = None

    def setUp(self) -> None:
        from autofab.parts.workspace.lib import workspace_asm
        from support.lib.lifecycle import enter_phase
        from autofab.parts.agent.lib import session as agent_session

        from autofab.parts.control.lib import control_asm
        from autofab.parts.core.lib import file_paths_impl
        from autofab.parts.metadata.lib import metadata_asm
        from autofab.parts.workspace_cli.lib import workspace_cli_asm
        file_paths_impl.__initialize__()
        workspace_asm.__initialize__()
        control_asm.__initialize__()
        metadata_asm.__initialize__()
        workspace_cli_asm.__initialize__()
        self.phase_cm = enter_phase(agent_session.agent_session)
        self.phase_cm.__enter__()

        self.test_dir = os.path.realpath(tempfile.mkdtemp())
        self.fake_repo = os.path.join(self.test_dir, "fake_repo")
        os.makedirs(self.fake_repo, exist_ok=True)
        os.environ["BUILD_WORKSPACE_DIRECTORY"] = self.fake_repo
        with open(os.path.join(self.fake_repo, "autofab.toml"), "w", encoding="utf-8") as f:
            f.write('methodology = "//autofab_py"\n')
        with open(os.path.join(self.fake_repo, "cleanroom.toml"), "w", encoding="utf-8") as f:
            f.write('methodology = "//autofab_py"\n')
        roles_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../autofab_py/autofab_roles.toml"))
        if not os.path.isfile(roles_src):
            roles_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../autofab_py/cleanroom_roles.toml"))
        if os.path.isfile(roles_src):
            shutil.copyfile(roles_src, os.path.join(self.fake_repo, "autofab_roles.toml"))
            shutil.copyfile(roles_src, os.path.join(self.fake_repo, "cleanroom_roles.toml"))
            py_dir = os.path.join(self.fake_repo, "autofab_py")
            os.makedirs(py_dir, exist_ok=True)
            shutil.copyfile(roles_src, os.path.join(py_dir, "autofab_roles.toml"))
            shutil.copyfile(roles_src, os.path.join(py_dir, "cleanroom_roles.toml"))
            sup_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../autofab_py/support"))
            if os.path.isdir(sup_src):
                shutil.copytree(sup_src, os.path.join(py_dir, "support"), dirs_exist_ok=True)
        self.orig_cwd = os.getcwd()

    def tearDown(self) -> None:
        if self.phase_cm is not None:
            self.phase_cm.__exit__(None, None, None)
        os.chdir(self.orig_cwd)
        os.environ.pop("BUILD_WORKSPACE_DIRECTORY", None)
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

        lib_file = os.path.join(part_dir, "lib/config.py")
        low_file = os.path.join(part_dir, "low/config.pyi")
        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
            audits={"SPEC_QA_AUDIT": "2026-10-04T12:00:00Z"},
        )

        lib_ws = commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(lib_ws)

        # 1. lib/config.py is missing -> get_work returns 1 (dirty tasks found)
        ret = autofab_role_tool.main(["get_work"])
        self.assertEqual(ret, 1)

        # 2. Worker stamps lib/config.py clean and submits
        ws_lib = os.path.join(lib_ws, "staging/parts/agent/lib/config.py")
        src_metadata.update_metadata(
            ws_lib,
            last_cleaned="2026-10-04T12:05:00Z",
            last_changed="2026-10-04T12:05:00Z",
        )
        autofab_role_tool.main(["submit", "--no-verify", ws_lib, "Initial implementation"])
        ret_clean = autofab_role_tool.main(["get_work"])
        self.assertEqual(ret_clean, 0)


    def test_submit_command_producer(self) -> None:
        """Verifies that submit enforces symmetric change summary rules based on code modification."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)

        lib_ws = commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(lib_ws)

        target = os.path.join(lib_ws, "staging/parts/agent/lib/config.py")
        with open(target, "w", encoding="utf-8") as f:
            f.write("# initial\n")

        # 1. Modified/new file submitted WITHOUT summary -> fails (ret=1)
        ret_no_sum = autofab_role_tool.main(["submit", target])
        self.assertEqual(ret_no_sum, 1)

        # 2. Must run check_files on modified file before submitting with summary
        ret_chk = autofab_role_tool.main(["check_files", target])
        self.assertEqual(ret_chk, 0)

        # 3. Modified/new file submitted WITH summary -> succeeds (ret=0)
        ret = autofab_role_tool.main(["submit", target, "Implemented config parser"])
        self.assertEqual(ret, 0)

        meta = src_metadata.extract_metadata(target)
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertIsNone(meta.last_cleaned)
        self.assertIsNone(meta.last_changed)
        self.assertEqual(meta.change_summary, "Implemented config parser")
        self.assertIsNotNone(meta.code_hash)

        # Canonical file in main is also updated directly
        main_lib = os.path.join(self.fake_repo, "staging/parts/agent/lib/config.py")
        main_meta = src_metadata.extract_metadata(main_lib)
        self.assertIsNotNone(main_meta)
        assert main_meta is not None
        self.assertIsNotNone(main_meta.last_cleaned)
        self.assertIsNotNone(main_meta.last_changed)
        self.assertIsNone(main_meta.code_hash)
        self.assertEqual(main_meta.change_summary, "Implemented config parser")

        # 3. Unmodified file submitted WITH summary -> fails (ret=1)
        ret_unchanged_with_sum = autofab_role_tool.main(
            ["submit", target, "Should fail because code unchanged"]
        )
        self.assertEqual(ret_unchanged_with_sum, 1)

        # 4. Unmodified file submitted WITHOUT summary -> succeeds (ret=0), preserves LAST_CHANGED and CHANGE
        old_changed = main_meta.last_changed
        ret_unchanged = autofab_role_tool.main(["submit", target])
        self.assertEqual(ret_unchanged, 0)

        meta2 = src_metadata.extract_metadata(target)
        self.assertIsNotNone(meta2)
        assert meta2 is not None
        self.assertIsNone(meta2.last_changed)
        self.assertEqual(meta2.change_summary, "Implemented config parser")

        main_meta2 = src_metadata.extract_metadata(main_lib)
        self.assertIsNotNone(main_meta2)
        assert main_meta2 is not None
        self.assertEqual(main_meta2.last_changed, old_changed)
        self.assertEqual(main_meta2.change_summary, "Implemented config parser")

    def test_submit_command_auditor(self) -> None:
        """Verifies that submit stamps <ROLE>_AUDIT directly in main without buffer."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)

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

        ret = autofab_role_tool.main(["submit", "--no-verify", target, "QA verified clean"])
        self.assertEqual(ret, 0)

        # In zero-sync architecture, buffer file is retired
        buf_path = os.path.join(qa_ws, autofab_role_tool.AUDIT_BUFFER_FILE)
        self.assertFalse(os.path.isfile(buf_path))

        # Directly stamped in main
        main_meta = src_metadata.extract_metadata(main_lib)
        self.assertIsNotNone(main_meta)
        assert main_meta is not None
        self.assertIn("QA_AUDIT", main_meta.audits)

    def test_blame_command_direct_mutation(self) -> None:
        """Verifies blaming directly mutates upstream contract in main and records blame buffer."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)

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
            autofab_role_tool.main(
                [
                    "blame",
                    "staging/parts/agent/lib/config.py",
                    "staging/parts/agent/low/config.pyi",
                    "Contract missing parameter X",
                ]
            )

        # Producer role 'lib' cannot blame upstream 'low'
        ret_unauth = autofab_role_tool.main(
            [
                "blame",
                "staging/parts/agent/low/config.pyi",
                "Contract missing parameter X",
            ]
        )
        self.assertEqual(ret_unauth, 1)

        # Arbiter role 'spec_qa' can blame upstream 'low'
        spec_qa_ws = commission_workspace(
            "spec_qa", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(spec_qa_ws)

        ret = autofab_role_tool.main(
            [
                "blame",
                "staging/parts/agent/low/config.pyi",
                "Contract missing parameter X",
            ]
        )
        self.assertEqual(ret, 0)

        # Blame buffer written in workspace root for harnesses to observe
        buf_path = os.path.join(spec_qa_ws, app_info.DEFAULT_BLAME_BUFFER_FILE)
        self.assertTrue(os.path.isfile(buf_path))

        # Directly mutated in main
        meta_low = src_metadata.extract_metadata(low_f)
        self.assertIsNotNone(meta_low)
        assert meta_low is not None
        self.assertEqual(len(meta_low.feedback), 1)
        self.assertIn("Contract missing parameter X", meta_low.feedback[0])
        self.assertIsNone(meta_low.dirty)

        # Second 2-arg blame
        ret2 = autofab_role_tool.main(
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
        ret = autofab_role_tool.main(["fail", target, "Compilation syntax error"])
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

        qa_ws = commission_workspace(
            "qa", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(qa_ws)

        test_file = os.path.join(qa_ws, "staging/parts/agent/tests/config_test.py")
        write_file_with_perms(
            test_file, "# test code\n", readonly=True
        )

        ret = autofab_role_tool.main(["submit", test_file])
        self.assertEqual(ret, 1)

    def test_submit_command_auditor_stamps_companion_test(self) -> None:
        """Verifies that submitting the implementation target in QA stamps both lib and companion test directly in main."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "tests"), exist_ok=True)

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
        ret = autofab_role_tool.main(["submit", "--no-verify", lib_target])
        self.assertEqual(ret, 0)

        buf_path = os.path.join(qa_ws, autofab_role_tool.AUDIT_BUFFER_FILE)
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
        ret_bare = autofab_role_tool.main(["submit", "--no-verify", "config"])
        self.assertEqual(ret_bare, 0)

        # 2. Virtual role path
        ret_virtual = autofab_role_tool.main(
            ["submit", "--no-verify", "staging/parts/agent/qa/config"]
        )
        self.assertEqual(ret_virtual, 0)

    def test_submit_command_producer_rejects_readonly_and_out_of_scope(self) -> None:
        """Verifies producer submit rejects read-only files and files outside active scope."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)

        lib_ws = commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(lib_ws)

        # Read-only upstream file
        ro_file = os.path.join(lib_ws, "staging/parts/agent/low/config.pyi")
        write_file_with_perms(
            ro_file, "# contract\n", readonly=True
        )

        ret_ro = autofab_role_tool.main(["submit", ro_file])
        self.assertEqual(ret_ro, 1)

    def test_fail_command_readonly_direct_mutation(self) -> None:
        """Verifies that running fail on a read-only target mutates main directly without buffering."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)

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

        ret = autofab_role_tool.main(["fail", lib_target, "Integration test failed"])
        self.assertEqual(ret, 0)

        buf_path = os.path.join(qa_ws, autofab_role_tool.BLAME_BUFFER_FILE)
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
        clean_md = (
            "<!-- CLEANROOM METADATA\n"
            "LAST_CLEANED: 2026-10-04T12:00:00Z\n"
            "LAST_CHANGED: 2026-10-04T12:00:00Z\n"
            "SPEC_QA_AUDIT: 2026-10-04T12:00:00Z\n"
            "-->\n"
        )
        os.makedirs(os.path.join(part_dir, "high"), exist_ok=True)
        with open(os.path.join(part_dir, "high/base.md"), "w", encoding="utf-8") as f:
            f.write(clean_md + "# base\n")
        with open(os.path.join(part_dir, "high/derived.md"), "w", encoding="utf-8") as f:
            f.write(clean_md + "imports: base\n\n# derived\n")

        low_base = os.path.join(part_dir, "low/base.pyi")
        low_derived = os.path.join(part_dir, "low/derived.pyi")
        src_metadata.update_metadata(
            low_base,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
            audits={"SPEC_QA_AUDIT": "2026-10-04T12:00:00Z"},
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
            audits={"SPEC_QA_AUDIT": "2026-10-04T12:00:00Z"},
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
        low_file = os.path.join(part_dir, "low/config.pyi")
        with open(low_file, "w", encoding="utf-8") as f:
            f.write("def get_config() -> str: ...\n")
        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
            audits={"SPEC_QA_AUDIT": "2026-10-04T12:00:00Z"},
        )

        lib_ws = commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(lib_ws)

        # 1. Initial get_work detects dirty task and records it in pending work
        ret1 = autofab_role_tool.main(["get_work"])
        self.assertEqual(ret1, 1)
        pending = autofab_role_tool.get_pending_work(lib_ws)
        self.assertEqual(len(pending), 1)
        self.assertIn("config.py", pending[0])

        # 2. Second get_work call without submit or blame is BLOCKED with exit code 1
        ret2 = autofab_role_tool.main(["get_work"])
        self.assertEqual(ret2, 1)

        # 3. get_work --force bypasses the pending work block
        ret_force = autofab_role_tool.main(["get_work", "--force"])
        self.assertEqual(ret_force, 1)

        # 4. Modify and submit the target -> clears pending work
        ws_lib = os.path.join(lib_ws, "staging/parts/agent/lib/config.py")
        with open(ws_lib, "w", encoding="utf-8") as f:
            f.write("def get_config() -> str: return 'ok'\n")
        ret_chk = autofab_role_tool.main(["check_files", "staging/parts/agent/lib/config.py"])
        self.assertEqual(ret_chk, 0)
        ret_sub = autofab_role_tool.main(
            ["submit", "staging/parts/agent/lib/config.py", "implemented get_config"]
        )
        self.assertEqual(ret_sub, 0)
        self.assertEqual(autofab_role_tool.get_pending_work(lib_ws), [])

        # 5. get_work now succeeds and reports clean
        ret_clean = autofab_role_tool.main(["get_work"])
        self.assertEqual(ret_clean, 0)

        # 6. Mark dirty again by updating upstream low contract
        src_metadata.update_metadata(
            low_file,
            last_cleaned="2099-01-01T00:00:00Z",
            last_changed="2099-01-01T00:00:00Z",
            audits={"SPEC_QA_AUDIT": "2099-01-01T00:00:00Z"},
        )
        ret3 = autofab_role_tool.main(["get_work"])
        self.assertEqual(ret3, 1)
        self.assertEqual(len(autofab_role_tool.get_pending_work(lib_ws)), 1)

        # 7. Failing target clears pending work
        ret_fail = autofab_role_tool.main(
            ["fail", "staging/parts/agent/lib/config.py", "Changed spec broken"]
        )
        self.assertEqual(ret_fail, 0)
        self.assertEqual(autofab_role_tool.get_pending_work(lib_ws), [])

    def test_coverage_command(self) -> None:
        """Verifies autofab_role_tool coverage command."""
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
        ret_pass = autofab_role_tool.main(
            ["coverage", "--impl", impl_path, "--test", test_path, "-t", "0.0"]
        )
        self.assertEqual(ret_pass, 0)

        # Threshold 100.0 fails due to uncovered bar()
        ret_fail = autofab_role_tool.main(
            ["coverage", "--impl", impl_path, "--test", test_path, "-t", "100.0"]
        )
        self.assertEqual(ret_fail, 1)

    def test_refresh_sys_command(self) -> None:
        """Verifies autofab_role_tool refresh-sys command refreshes system files."""
        lib_ws = commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        ret = autofab_role_tool.main(["refresh-sys", "--repo-root", self.fake_repo])
        self.assertEqual(ret, 0)
        self.assertTrue(os.path.isdir(os.path.join(lib_ws, "bin")))
        self.assertTrue(os.path.isfile(os.path.join(lib_ws, "bin/check_files")))

    def test_check_files_command(self) -> None:
        """Verifies autofab_role_tool check_files command."""
        lib_ws = commission_workspace(
            "lib", dir_scope="staging", repo_root=self.fake_repo
        )
        os.chdir(lib_ws)
        ret = autofab_role_tool.main(["check_files"])
        self.assertEqual(ret, 0)
        ret_err = autofab_role_tool.main(["check_files", "nonexistent"])
        self.assertEqual(ret_err, 1)

    def test_submit_command_verification_gating(self) -> None:
        """Verifies that submit rejects targets when verification checks fail, and succeeds when they pass or --no-verify is used."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "tests"), exist_ok=True)

        main_lib = os.path.join(self.fake_repo, "staging/parts/agent/lib/config.py")
        write_file_with_perms(main_lib, "# lib in main\n", readonly=False)

        qa_ws = commission_workspace("qa", dir_scope="staging", repo_root=self.fake_repo)
        os.chdir(qa_ws)

        lib_target = os.path.join(qa_ws, "staging/parts/agent/lib/config.py")
        write_file_with_perms(lib_target, "# lib\n", readonly=True)

        # 1. Verification fails (test file missing) -> submit rejected (ret=1)
        ret_fail = autofab_role_tool.main(["submit", lib_target])
        self.assertEqual(ret_fail, 1)

        main_meta = src_metadata.extract_metadata(main_lib)
        self.assertTrue(main_meta is None or "QA_AUDIT" not in getattr(main_meta, "audits", []))

        # 2. Verification bypassed via --no-verify -> submit accepted (ret=0)
        ret_bypass = autofab_role_tool.main(["submit", "--no-verify", lib_target])
        self.assertEqual(ret_bypass, 0)

        main_meta_bypassed = src_metadata.extract_metadata(main_lib)
        self.assertIsNotNone(main_meta_bypassed)
        assert main_meta_bypassed is not None
        self.assertIn("QA_AUDIT", main_meta_bypassed.audits)

        # 3. Add passing test file -> verification passes -> submit accepted (ret=0)
        test_file = os.path.join(qa_ws, "staging/parts/agent/tests/config_test.py")
        write_file_with_perms(test_file, "def test_ok(): pass\n", readonly=False)

        ret_pass = autofab_role_tool.main(["submit", lib_target])
        self.assertEqual(ret_pass, 0)

    def test_cleanroom_help(self) -> None:
        """Verifies cleanroom --help returns 0 and outputs command overview."""
        from io import StringIO
        import contextlib
        out = StringIO()
        with contextlib.redirect_stdout(out):
            ret = autofab_role_tool.main(["--help"])
        self.assertEqual(ret, 0)
        output = out.getvalue()
        self.assertIn("clean", output)
        self.assertIn("mark-dirty", output)
        self.assertIn("work-queue", output)
        self.assertIn("commission", output)

    def test_work_queue_auto_commissions_missing_workspaces(self) -> None:
        """Verifies that work-queue auto-commissions missing role workspaces up to target_role."""
        from autofab.parts.workspace.lib import role_registry_impl
        reg = role_registry_impl.WorkspaceRegistry()
        high_ws = reg.compute_workspace_dir("high", dir_scope="staging", repo_root=self.fake_repo)
        low_ws = reg.compute_workspace_dir("low", dir_scope="staging", repo_root=self.fake_repo)
        if os.path.isdir(high_ws):
            shutil.rmtree(high_ws, ignore_errors=True)
        if os.path.isdir(low_ws):
            shutil.rmtree(low_ws, ignore_errors=True)

        self.assertFalse(os.path.isdir(high_ws))
        self.assertFalse(os.path.isdir(low_ws))

        from io import StringIO
        import contextlib
        out = StringIO()
        with contextlib.redirect_stdout(out):
            ret = autofab_role_tool.main([
                "work-queue", "staging", "low", "--json", "--repo-root", self.fake_repo
            ])
        self.assertEqual(ret, 0)
        data = json.loads(out.getvalue())
        self.assertTrue(os.path.isdir(high_ws))
        self.assertTrue(os.path.isdir(low_ws))
        self.assertIn("high", data["workspace_dirs"])
        self.assertIn("low", data["workspace_dirs"])
        self.assertEqual(data["workspace_dirs"]["high"], high_ws)
        self.assertEqual(data["workspace_dirs"]["low"], low_ws)

    def test_clean_preflight_auto_commissions(self) -> None:
        """Verifies that clean pre-flight commissions workspaces when dirty and decommissions when clean."""
        from autofab.parts.workspace.lib import role_registry_impl
        reg = role_registry_impl.WorkspaceRegistry()
        plan_ws = reg.compute_workspace_dir("planning", dir_scope="staging", repo_root=self.fake_repo)
        if os.path.isdir(plan_ws):
            shutil.rmtree(plan_ws, ignore_errors=True)

        self.assertFalse(os.path.isdir(plan_ws))

        # 1. Create dirty unit in staging -> clean commissions workspaces and emits directive
        high_dir = os.path.join(self.fake_repo, "staging/parts/agent/high")
        os.makedirs(high_dir, exist_ok=True)
        high_file = os.path.join(high_dir, "config.md")
        write_file_with_perms(high_file, "# High spec\n", readonly=False)
        src_metadata.update_metadata(high_file, last_cleaned="", last_changed="2026-10-15T00:00:00Z")

        from io import StringIO
        import contextlib
        out = StringIO()
        with contextlib.redirect_stdout(out):
            ret = autofab_role_tool.main([
                "clean", "staging", "planning", "--model", "gemini-flash", "--repo-root", self.fake_repo, "--antigravity-dispatch", "none"
            ])
        self.assertEqual(ret, 0)
        output = out.getvalue()
        self.assertIn("Autofab Clean Pre-flight", output)
        self.assertIn("AUTONOMOUS ANTIGRAVITY COORDINATION DIRECTIVE", output)
        self.assertTrue(os.path.isdir(plan_ws))
        self.assertTrue(os.path.isdir(os.path.join(plan_ws, "bin")))

        # 2. When clean -> clean decommissions provisioned workspaces
        shutil.rmtree(os.path.join(self.fake_repo, "staging/parts/agent"), ignore_errors=True)
        out2 = StringIO()
        with contextlib.redirect_stdout(out2):
            ret2 = autofab_role_tool.main([
                "clean", "staging", "planning", "--model", "gemini-flash", "--repo-root", self.fake_repo, "--antigravity-dispatch", "none"
            ])
        self.assertEqual(ret2, 0)
        output2 = out2.getvalue()
        self.assertIn("CLEAN", output2)
        self.assertIn("Decommissioned", output2)
        self.assertFalse(os.path.isdir(plan_ws))

    def test_dirty_and_mark_clean_subcommands(self) -> None:
        """Verifies dirty and mark-clean subcommands on targets."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        high_dir = os.path.join(part_dir, "high")
        lib_dir = os.path.join(part_dir, "lib")
        os.makedirs(high_dir, exist_ok=True)
        os.makedirs(lib_dir, exist_ok=True)

        hls_file = os.path.join(high_dir, "sample_tool.md")
        with open(hls_file, "w", encoding="utf-8") as f:
            f.write("# Sample High Level Spec\n\n```python\n# Component: implementation\n```\n")

        lib_file = os.path.join(lib_dir, "sample_tool.py")
        with open(lib_file, "w", encoding="utf-8") as f:
            f.write("# sample implementation\n")

        rel_path = "staging/parts/agent/lib/sample_tool.py"

        # 1. Mark clean via mark-clean subcommand
        ret_clean = autofab_role_tool.main([
            "mark-clean", rel_path, "--workspace-dir", self.fake_repo
        ])
        self.assertEqual(ret_clean, 0)
        meta = src_metadata.extract_metadata(lib_file)
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertTrue(bool(meta.last_cleaned))

    def test_blame_subcommand(self) -> None:
        """Verifies blame subcommand supports positional critiques, -m flag, and file targets."""
        part_dir = os.path.join(self.fake_repo, "staging/parts/agent")
        low_dir = os.path.join(part_dir, "low")
        os.makedirs(low_dir, exist_ok=True)

        low_file = os.path.join(low_dir, "feedback_target.pyi")
        with open(low_file, "w", encoding="utf-8") as f:
            f.write("def do_something() -> None: ...\n")
        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
            audits={"SPEC_QA_AUDIT": "2026-10-04T12:00:00Z"},
        )

        rel_path = "staging/parts/agent/low/feedback_target.pyi"

        # 1. Missing critique returns code 2
        ret_no_critique = autofab_role_tool.main([
            "blame", rel_path, "--repo-root", self.fake_repo
        ])
        self.assertEqual(ret_no_critique, 2)

        # 2. Positional critique updates file metadata
        ret_pos = autofab_role_tool.main([
            "blame", rel_path, "Positional critique", "--repo-root", self.fake_repo
        ])
        self.assertEqual(ret_pos, 0)
        meta = src_metadata.extract_metadata(low_file)
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(len(meta.feedback), 1)
        self.assertIn("Positional critique", meta.feedback[0])

        # 3. Flag-based critique (-m) appends to file metadata
        ret_flag = autofab_role_tool.main([
            "blame", rel_path, "-m", "Message flag critique", "--repo-root", self.fake_repo
        ])
        self.assertEqual(ret_flag, 0)
        meta2 = src_metadata.extract_metadata(low_file)
        assert meta2 is not None
        self.assertEqual(len(meta2.feedback), 2)
        self.assertIn("Message flag critique", meta2.feedback[1])

    def test_commission_subcommand_model_and_harness(self) -> None:
        """Verifies commission subcommand initializes workspace with --model and resolves harness from model_configs.toml."""
        ret = autofab_role_tool.main([
            "commission", "lib", "staging",
            "--model", "deepseek-v41-flash",
            "--repo-root", self.fake_repo,
        ])
        self.assertEqual(ret, 0)
        from autofab.parts.workspace.lib import role_registry_impl
        reg = role_registry_impl.WorkspaceRegistry()
        lib_ws = reg.compute_workspace_dir("lib", "staging", repo_root=self.fake_repo)
        self.assertTrue(os.path.isdir(lib_ws))

        # Check role descriptor records model and harness
        cfg_path = os.path.join(lib_ws, app_info.DEFAULT_ROLE_DESCRIPTOR)
        self.assertTrue(os.path.isfile(cfg_path))
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg.get("model"), "deepseek-v41-flash")
        self.assertEqual(cfg.get("harness"), "dsh")

        # Check DSH patch was created
        dsh_patch = os.path.join(lib_ws, app_info.DEFAULT_STATE_DIR, "dsh_patch.yml")
        self.assertTrue(os.path.isfile(dsh_patch))

        # Check AGENTS.md has DSH confinement header
        agents_md = os.path.join(lib_ws, "AGENTS.md")
        with open(agents_md, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Autofab Role Confinement Rules for DeepSeek Harness", content)

        # Verifies --harness is rejected as unrecognized option
        with self.assertRaises(SystemExit):
            autofab_role_tool.main([
                "commission", "lib", "staging",
                "--harness", "dsh",
                "--repo-root", self.fake_repo,
            ])

    def test_scope_hash_role_syntax_across_subcommands(self) -> None:
        """Verifies scope#role syntax works consistently across commission, work-queue, orchestrate, and decommission."""
        # 1. commission with staging#lib
        ret_comm = autofab_role_tool.main([
            "commission", "staging#lib",
            "--model", "deepseek-v41-flash",
            "--repo-root", self.fake_repo,
        ])
        self.assertEqual(ret_comm, 0)
        from autofab.parts.workspace.lib import role_registry_impl
        reg = role_registry_impl.WorkspaceRegistry()
        lib_ws = reg.compute_workspace_dir("lib", "staging", repo_root=self.fake_repo)
        self.assertTrue(os.path.isdir(lib_ws))

        # 2. work-queue with staging#lib
        ret_wq = autofab_role_tool.main([
            "work-queue", "staging#lib", "--json",
            "--repo-root", self.fake_repo,
        ])
        self.assertEqual(ret_wq, 0)

        # 3. decommission with staging#lib
        ret_decomm = autofab_role_tool.main([
            "decommission", "staging#lib",
            "--repo-root", self.fake_repo,
        ])
        self.assertEqual(ret_decomm, 0)
        self.assertFalse(os.path.isdir(lib_ws))

    def test_unit_label_target_syntax_across_subcommands(self) -> None:
        """Verifies //scope/parts/unit:target#role and path#role work across commission, work-queue, decommission."""
        from autofab.parts.workspace.lib import role_registry_impl
        reg = role_registry_impl.WorkspaceRegistry()
        lib_ws = reg.compute_workspace_dir("lib", "staging", repo_root=self.fake_repo)

        # 1. Commission via canonical DAG label //staging/parts/agent:config#lib
        ret_comm = autofab_role_tool.main([
            "commission", "//staging/parts/agent:config#lib",
            "--model", "deepseek-v41-flash",
            "--repo-root", self.fake_repo,
        ])
        self.assertEqual(ret_comm, 0)
        self.assertTrue(os.path.isdir(lib_ws))

        # 2. Inspect work-queue via canonical DAG label
        ret_wq = autofab_role_tool.main([
            "work-queue", "//staging/parts/agent:config#lib", "--json",
            "--repo-root", self.fake_repo,
        ])
        self.assertEqual(ret_wq, 0)

        # 3. Decommission via canonical DAG label
        ret_decomm = autofab_role_tool.main([
            "decommission", "//staging/parts/agent:config#lib",
            "--repo-root", self.fake_repo,
        ])
        self.assertEqual(ret_decomm, 0)
        self.assertFalse(os.path.isdir(lib_ws))

        # 4. Commission via path format staging/parts/agent/lib#lib
        ret_comm_path = autofab_role_tool.main([
            "commission", "staging/parts/agent/lib#lib",
            "--model", "deepseek-v41-flash",
            "--repo-root", self.fake_repo,
        ])
        self.assertEqual(ret_comm_path, 0)
        self.assertTrue(os.path.isdir(lib_ws))

        # 5. Decommission via path format
        ret_decomm_path = autofab_role_tool.main([
            "decommission", "staging/parts/agent/lib#lib",
            "--repo-root", self.fake_repo,
        ])
        self.assertEqual(ret_decomm_path, 0)
        self.assertFalse(os.path.isdir(lib_ws))

    def test_default_model_resolution_from_model_configs(self) -> None:
        """Verifies commission resolves model and harness from model_configs.toml."""
        # Create model_configs.toml in fake repo with per-model harness
        cfg_path = os.path.join(self.fake_repo, "model_configs.toml")
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(
                'default = "deepseek-v41-flash"\n'
                'max_unproductive_rounds = 3\n\n'
                '[models.qwen-moe-q6]\nmodel = "Qwen3.6-35B-A3B-oQ6-mtp"\nharness = "dsh"\n\n'
                '[models.gemini-flash]\nmodel = "gemini-flash"\nharness = "antigravity"\n\n'
                '[models.deepseek-v41-flash]\nmodel = "DeepSeek-V41-Flash"\nharness = "dsh"\n'
            )

        # Direct helper check
        self.assertEqual(autofab_role_tool.resolve_default_model(self.fake_repo), "deepseek-v41-flash")
        # When model is None, it derives harness from the default model (deepseek-v41-flash -> dsh)
        self.assertEqual(autofab_role_tool.resolve_model_harness(None, self.fake_repo), "dsh")
        self.assertEqual(autofab_role_tool.resolve_model_harness("default", self.fake_repo), "dsh")
        self.assertEqual(autofab_role_tool.resolve_model_harness("gemini-flash", self.fake_repo), "antigravity")
        self.assertEqual(autofab_role_tool.resolve_model_harness("deepseek-v41-flash", self.fake_repo), "dsh")
        self.assertEqual(autofab_role_tool.resolve_model_harness("qwen-moe-q6", self.fake_repo), "dsh")
        self.assertEqual(autofab_role_tool.resolve_model_harness("unknown-model", self.fake_repo), "dsh")
        self.assertEqual(autofab_role_tool.resolve_model_harness("gemini-custom", self.fake_repo), "antigravity")

        # 1. Commission with --model gemini-flash -> binds antigravity harness
        ret_ag = autofab_role_tool.main([
            "commission", "staging#lib",
            "--model", "gemini-flash",
            "--repo-root", self.fake_repo,
        ])
        self.assertEqual(ret_ag, 0)
        from autofab.parts.workspace.lib import role_registry_impl
        reg = role_registry_impl.WorkspaceRegistry()
        lib_ws = reg.compute_workspace_dir("lib", "staging", repo_root=self.fake_repo)
        self.assertTrue(os.path.isdir(lib_ws))

        role_cfg_path = os.path.join(lib_ws, app_info.DEFAULT_ROLE_DESCRIPTOR)
        self.assertTrue(os.path.isfile(role_cfg_path))
        with open(role_cfg_path, "r", encoding="utf-8") as f:
            role_data = json.load(f)
        self.assertEqual(role_data.get("model"), "gemini-flash")
        self.assertEqual(role_data.get("harness"), "antigravity")

        # 2. Commission without --model -> binds default model (deepseek-v41-flash) with dsh harness
        autofab_role_tool.main(["decommission", "staging#lib", "--repo-root", self.fake_repo])
        ret_dsh = autofab_role_tool.main([
            "commission", "staging#lib",
            "--repo-root", self.fake_repo,
        ])
        self.assertEqual(ret_dsh, 0)
        with open(role_cfg_path, "r", encoding="utf-8") as f:
            role_data_dsh = json.load(f)
        self.assertEqual(role_data_dsh.get("model"), "deepseek-v41-flash")
        self.assertEqual(role_data_dsh.get("harness"), "dsh")

    def test_clean_harness_resolution_and_defaults(self) -> None:
        """Verifies clean defaults to subagent coordinator harness."""
        from unittest.mock import patch, MagicMock

        # 1. 'autofab clean staging/parts/sandbox#qa' dispatches to run_clean
        with patch.object(autofab_role_tool, "run_clean", return_value=0) as mock_orch:
            ret = autofab_role_tool.main(["clean", "staging/parts/sandbox#qa", "--repo-root", self.fake_repo])
            self.assertEqual(ret, 0)
            mock_orch.assert_called_once()
            call_args = mock_orch.call_args[0][0]
            self.assertIn("staging/parts/sandbox#qa", call_args)

        # 2. Direct main_clean entrypoint invokes clean
        with patch.object(autofab_role_tool, "run_clean", return_value=0) as mock_orch:
            ret = autofab_role_tool.main_clean(["staging/parts/sandbox#qa", "--repo-root", self.fake_repo])
            self.assertEqual(ret, 0)
            mock_orch.assert_called_once()

        # 6. 'cleanroom clean ... --model deepseek-flash' dispatches to dsh headless runner
        with patch.object(autofab_role_tool, "_find_subagent_tool_mod") as mock_find_mod:
            mock_subagent_mod = MagicMock()
            mock_subagent_mod.main.return_value = 0
            mock_find_mod.return_value = mock_subagent_mod
            ret_dsh = autofab_role_tool.main([
                "clean", "staging#qa", "--model", "deepseek-flash", "--repo-root", self.fake_repo
            ])
            self.assertEqual(ret_dsh, 0)
            mock_subagent_mod.main.assert_called_once()
            forwarded = mock_subagent_mod.main.call_args[0][0]
            self.assertIn("--harness", forwarded)
            self.assertEqual(forwarded[forwarded.index("--harness") + 1], "dsh")

            mock_subagent_mod.reset_mock()
            ret_unit_dsh = autofab_role_tool.main([
                "clean", "//staging/parts/sandbox:file_reader_impl#qa", "--model", "deepseek-flash", "--repo-root", self.fake_repo
            ])
            self.assertEqual(ret_unit_dsh, 0)
            mock_subagent_mod.main.assert_called_once()
            forwarded_unit = mock_subagent_mod.main.call_args[0][0]
            self.assertIn("--target", forwarded_unit)
            self.assertEqual(forwarded_unit[forwarded_unit.index("--target") + 1], "//staging/parts/sandbox:file_reader_impl#qa")

        # 7. Verifies cleanroom clean rejects --harness option
        with self.assertRaises(SystemExit):
            autofab_role_tool.main(["clean", "staging#qa", "--harness", "dsh", "--repo-root", self.fake_repo])

    def test_configure_command(self) -> None:
        """Verifies cleanroom configure initializes user config and credentials template."""
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp_dir:
            from support.lib import app_info
            with patch.dict(os.environ, {f"{app_info.ENV_PREFIX}_CONFIG_DIR": tmp_dir}):
                ret = autofab_role_tool.main(["configure"])
                self.assertEqual(ret, 0)
                self.assertTrue(os.path.isfile(os.path.join(tmp_dir, "model_configs.toml")))
                creds_path = os.path.join(tmp_dir, "credentials.toml")
                self.assertTrue(os.path.isfile(creds_path))
                # verify mode 0600 on POSIX
                if sys.platform != "win32":
                    mode = os.stat(creds_path).st_mode & 0o777
                    self.assertEqual(mode, 0o600)

    def test_install_command(self) -> None:
        """Verifies cleanroom install prepares workspace config and gitignore."""
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp_dir:
            from support.lib import app_info
            # Run install in fake workspace
            with patch.object(autofab_role_tool, "find_workspace_root", return_value=tmp_dir):
                ret = autofab_role_tool.main(["install"])
                self.assertEqual(ret, 0)
                cfg_path = os.path.join(tmp_dir, app_info.DEFAULT_CONFIG_FILE)
                self.assertTrue(os.path.isfile(cfg_path))
                gitignore_path = os.path.join(tmp_dir, ".gitignore")
                self.assertTrue(os.path.isfile(gitignore_path))
                with open(gitignore_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("role_workspaces/", content)

    def test_ensure_dsh_skill_installed(self) -> None:
        """Verifies DSH skill is installed in harness skills directory when present."""
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp_dsh:
            dsh_skills = os.path.join(tmp_dsh, "harness", "skills")
            os.makedirs(dsh_skills, exist_ok=True)
            with patch.dict(os.environ, {"DSH_HOME": tmp_dsh}):
                skill_path = autofab_role_tool.ensure_dsh_skill_installed()
                self.assertIsNotNone(skill_path)
                assert skill_path is not None
                self.assertTrue(os.path.isfile(skill_path))
                with open(skill_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("Autonomous Coordinator", content)
                self.assertNotIn("/Users/seanmcdirmid", content)

    def test_dispatch_antigravity_coordination_message(self) -> None:
        """Verifies dispatch_antigravity_coordination invokes agentapi send-message."""
        from unittest.mock import patch, MagicMock
        with patch.dict(os.environ, {
            "ANTIGRAVITY_AGENTAPI_EXE": "/fake/bin/language_server",
            "ANTIGRAVITY_CONVERSATION_ID": "conv-456",
        }):
            mock_proc = MagicMock(returncode=0, stdout="", stderr="")
            with patch("subprocess.run", return_value=mock_proc) as mock_run:
                res = autofab_role_tool.dispatch_antigravity_coordination("my_scope", mode="message")
                self.assertTrue(res)
                mock_run.assert_called_once()
                cmd = mock_run.call_args[0][0]
                self.assertEqual(cmd[0], "/fake/bin/language_server")
                self.assertEqual(cmd[1], "agentapi")
                self.assertEqual(cmd[2], "send-message")
                self.assertIn("--title=Autofab Coordination [my_scope]", cmd)
                self.assertIn("conv-456", cmd)
                self.assertIn("Clean all dirty nodes in my_scope using autofab_coordinator.", cmd)

    def test_dispatch_antigravity_coordination_new_conversation(self) -> None:
        """Verifies dispatch_antigravity_coordination spawns new conversation tab."""
        from unittest.mock import patch, MagicMock
        with patch.dict(os.environ, {
            "ANTIGRAVITY_AGENTAPI_EXE": "/fake/bin/language_server",
        }):
            mock_proc = MagicMock(returncode=0, stdout="", stderr="")
            with patch("subprocess.run", return_value=mock_proc) as mock_run:
                res = autofab_role_tool.dispatch_antigravity_coordination("my_scope", mode="new-conversation", model="gemini-pro")
                self.assertTrue(res)
                mock_run.assert_called_once()
                cmd = mock_run.call_args[0][0]
                self.assertEqual(cmd[0], "/fake/bin/language_server")
                self.assertEqual(cmd[1], "agentapi")
                self.assertEqual(cmd[2], "new-conversation")
                self.assertIn("--model=pro", cmd)
                self.assertIn("--title=Autofab Coordinator: my_scope", cmd)
                self.assertIn("--", cmd)
                self.assertIn("Clean all dirty nodes in my_scope using autofab_coordinator.", cmd)

    def test_dispatch_antigravity_coordination_disabled_or_missing(self) -> None:
        """Verifies dispatch_antigravity_coordination handles none and missing env gracefully."""
        self.assertFalse(autofab_role_tool.dispatch_antigravity_coordination("my_scope", mode="none"))
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(autofab_role_tool.dispatch_antigravity_coordination("my_scope", mode="message"))

    def test_dispatch_antigravity_coordination_language_server_fallback(self) -> None:
        """Verifies dispatch_antigravity_coordination falls back to language_server directly."""
        from pathlib import Path
        from unittest.mock import patch, MagicMock
        with patch.dict(os.environ, {}, clear=True):
            with patch("shutil.which", return_value=None):
                with patch.object(Path, "is_file", autospec=True) as mock_isfile, patch("os.access", return_value=True):
                    mock_isfile.side_effect = lambda self: "language_server" in str(self)
                    mock_proc = MagicMock(returncode=0, stdout="", stderr="")
                    with patch("subprocess.run", return_value=mock_proc) as mock_run:
                        res = autofab_role_tool.dispatch_antigravity_coordination("my_scope", mode="new-conversation")
                        self.assertTrue(res)
                        cmd = mock_run.call_args[0][0]
                        self.assertIn("language_server", cmd[0])
                        self.assertEqual(cmd[1], "agentapi")
                        self.assertEqual(cmd[2], "new-conversation")

    def test_dispatch_antigravity_coordination_auto_launch_desktop(self) -> None:
        """Verifies dispatch_antigravity_coordination attempts to launch desktop app if agentapi fails initially."""
        from pathlib import Path
        from unittest.mock import patch, MagicMock
        with patch.dict(os.environ, {"ANTIGRAVITY_AGENTAPI_EXE": "/fake/bin/language_server"}):
            with patch("sys.platform", "darwin"):
                with patch.object(Path, "exists", autospec=True, return_value=True):
                    with patch("time.sleep", return_value=None):
                        fail_proc = MagicMock(returncode=1, stdout="", stderr="connection refused")
                        succ_proc = MagicMock(returncode=0, stdout="ok", stderr="")
                        runs = [fail_proc, MagicMock(returncode=0), succ_proc]
                        with patch("subprocess.run", side_effect=runs) as mock_run:
                            res = autofab_role_tool.dispatch_antigravity_coordination("my_scope", mode="new-conversation")
                            self.assertTrue(res)
                            self.assertEqual(mock_run.call_count, 3)
                            self.assertEqual(mock_run.call_args_list[0][0][0][2], "new-conversation")
                            self.assertEqual(mock_run.call_args_list[1][0][0][0], "open")
                            self.assertEqual(mock_run.call_args_list[2][0][0][2], "new-conversation")

    def test_clean_outside_antigravity_dispatches_new_conversation(self) -> None:
        """Verifies clean outside Antigravity dispatches new-conversation and exits 0."""
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            repo_root = os.path.join(td, "repo")
            os.makedirs(repo_root, exist_ok=True)
            from support.lib import app_info
            main_cfg = os.path.join(repo_root, f"{app_info.APP_NAME}.toml")
            with open(main_cfg, "w", encoding="utf-8") as f:
                f.write('methodology = "//autofab_py"\n')
            cfg_path = os.path.join(repo_root, f"{app_info.APP_NAME}_roles.toml")
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write(
                    f'[roles.qa]\n'
                    f'name = "qa"\n'
                    f'persona = "QA Auditor"\n'
                    f'src_pattern = "{{unit_dir}}/tests/{{unit_name}}_test.py"\n'
                    f'model = "gemini-flash"\n'
                    f'harness = "antigravity"\n'
                )
            dummy_target = os.path.join(repo_root, "pkg", "parts", "mod", "tests", "mod_test.py")
            os.makedirs(os.path.dirname(dummy_target), exist_ok=True)
            with open(dummy_target, "w") as f:
                f.write("target\n")

            with patch.dict(os.environ, {}, clear=True):
                with patch.object(autofab_role_tool, "dispatch_antigravity_coordination", return_value=True) as mock_dispatch:
                    ret = autofab_role_tool.run_clean([
                        "pkg",
                        "--model", "gemini-flash",
                        "--repo-root", repo_root,
                    ])
                    self.assertEqual(ret, 0)
                    mock_dispatch.assert_called_once()
                    self.assertEqual(mock_dispatch.call_args[1]["mode"], "new-conversation")

    def test_clean_outside_antigravity_fails_if_dispatch_fails(self) -> None:
        """Verifies clean outside Antigravity returns 1 if dispatch_antigravity_coordination fails."""
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            repo_root = os.path.join(td, "repo")
            os.makedirs(repo_root, exist_ok=True)
            from support.lib import app_info
            main_cfg = os.path.join(repo_root, f"{app_info.APP_NAME}.toml")
            with open(main_cfg, "w", encoding="utf-8") as f:
                f.write('methodology = "//autofab_py"\n')
            cfg_path = os.path.join(repo_root, f"{app_info.APP_NAME}_roles.toml")
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write(
                    f'[roles.qa]\n'
                    f'name = "qa"\n'
                    f'persona = "QA Auditor"\n'
                    f'src_pattern = "{{unit_dir}}/tests/{{unit_name}}_test.py"\n'
                    f'model = "gemini-flash"\n'
                    f'harness = "antigravity"\n'
                )
            dummy_target = os.path.join(repo_root, "pkg", "parts", "mod", "tests", "mod_test.py")
            os.makedirs(os.path.dirname(dummy_target), exist_ok=True)
            with open(dummy_target, "w") as f:
                f.write("target\n")

            with patch.dict(os.environ, {}, clear=True):
                with patch.object(autofab_role_tool, "dispatch_antigravity_coordination", return_value=False):
                    ret = autofab_role_tool.run_clean([
                        "pkg",
                        "--model", "gemini-flash",
                        "--repo-root", repo_root,
                    ])
                    self.assertEqual(ret, 1)

    def test_benchmark_subcommand(self) -> None:
        """Verifies cleanroom benchmark command dispatches properly with arguments."""
        ret = autofab_role_tool.main(["benchmark", "--suite=dag-engine", "--models=deepseek-flash", "--dry-run"])
        self.assertEqual(ret, 0)

    def test_revert_and_checkpoint_subcommands(self) -> None:
        """Verifies autofab checkpoint and revert subcommands."""
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["git", "init"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test Worker"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@cleanroom.local"], cwd=td, check=True, capture_output=True)
            sample_f = os.path.join(td, "file.txt")
            with open(sample_f, "w") as f:
                f.write("v1\n")
            subprocess.run(["git", "add", "-A"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "v1"], cwd=td, check=True, capture_output=True)

            old_cwd = os.getcwd()
            try:
                os.chdir(td)
                with open(sample_f, "w") as f:
                    f.write("v2\n")
                ret_cp = autofab_role_tool.main(["checkpoint", "save-v2"])
                self.assertEqual(ret_cp, 0)

                with open(sample_f, "w") as f:
                    f.write("broken\n")
                ret_rev = autofab_role_tool.main(["revert", "file.txt"])
                self.assertEqual(ret_rev, 0)
                with open(sample_f, "r") as f:
                    self.assertEqual(f.read(), "v2\n")
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()


