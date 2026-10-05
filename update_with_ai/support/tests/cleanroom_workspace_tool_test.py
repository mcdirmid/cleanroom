#!/usr/bin/env python3
"""cleanroom_workspace_tool_test.py — Unit tests for subagentless Cleanroom workspaces."""

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
from update_with_ai.support.lib import cleanroom_workspace_tool


class CleanroomWorkspaceToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
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

    def test_commission_lib_workspace_permissions_and_structure(self) -> None:
        """Verifies commissioning of a Lib role workspace: lib writable, grounding/BUILD read-only, no mailboxes."""
        lib_ws = os.path.join(self.test_dir, "lib_ws")
        cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", dest=lib_ws, repo_root=self.test_dir
        )

        # AGENTS.md exists
        agents_md = os.path.join(lib_ws, "AGENTS.md")
        self.assertTrue(os.path.exists(agents_md))
        with open(agents_md, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Lib Engineer", content)
        self.assertIn("In-Band Source Metadata", content)
        self.assertIn("Early Exit", content)
        self.assertIn("No Unsolicited Work Discovery", content)
        self.assertNotIn("WORK_ORDER.md", content)
        self.assertNotIn("COMPLETED.md", content)

        # Mailbox files must NOT exist
        self.assertFalse(os.path.exists(os.path.join(lib_ws, "WORK_ORDER.md")))
        self.assertFalse(os.path.exists(os.path.join(lib_ws, "COMPLETED.md")))

        # .cleanroom_role.json exists and has last_sync_timestamp
        role_json = os.path.join(lib_ws, ".cleanroom_role.json")
        self.assertTrue(os.path.exists(role_json))
        meta = cleanroom_workspace_tool.load_role_metadata(lib_ws)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["role_name"], "lib")
        self.assertEqual(meta["parts_dir"], "staging")
        self.assertIn("last_sync_timestamp", meta)

        # Helper scripts exist in bin/ (get_work, submit, blame, fail)
        self.assertTrue(os.path.exists(os.path.join(lib_ws, "bin/get_work")))
        self.assertTrue(os.path.exists(os.path.join(lib_ws, "bin/submit")))
        self.assertTrue(os.path.exists(os.path.join(lib_ws, "bin/fail")))
        self.assertTrue(os.path.exists(os.path.join(lib_ws, "bin/blame")))

    def test_setup_test_workspace_stubs_and_permissions(self) -> None:
        """Verifies commissioning of a Test role workspace: tests writable, lib has read-only stubs."""
        test_ws = os.path.join(self.test_dir, "test_ws")
        cleanroom_workspace_tool.commission_workspace(
            "test", dir_scope="staging", dest=test_ws, repo_root=self.test_dir
        )

        synthetic_pyi = os.path.join(self.test_dir, "sample_impl.pyi")
        with open(synthetic_pyi, "w", encoding="utf-8") as f:
            f.write(
                "from framework import operation, override, singleton_type\n"
                "from typing import Self\n\n"
                "@singleton_type('system')\n"
                "class SampleService:\n"
                "    @operation\n"
                "    def process_data(self, item: str) -> bool: ...\n"
            )
        synthetic_stub = os.path.join(test_ws, "sample_impl.py")
        cleanroom_workspace_tool.generate_readonly_test_stub(
            synthetic_pyi, "sample_impl", synthetic_stub
        )
        self.assertTrue(os.path.exists(synthetic_stub))
        st = os.stat(synthetic_stub)
        self.assertEqual(st.st_mode & stat.S_IWUSR, 0, "Test stub must be read-only")
        with open(synthetic_stub, "r", encoding="utf-8") as f:
            stub_content = f.read()
        self.assertIn("CLEANROOM TEST STUB", stub_content)
        self.assertIn("raise NotImplementedError", stub_content)

    def test_tamper_detection(self) -> None:
        """Verifies that tamper checks are retired and verify_integrity does not raise."""
        lib_ws = os.path.join(self.test_dir, "tamper_ws")
        cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", dest=lib_ws, repo_root=self.test_dir
        )

        # Create a mock read-only file
        ro_file = os.path.join(lib_ws, "read_only_contract.pyi")
        cleanroom_workspace_tool.write_file_with_perms(
            ro_file, "# original contract\n", readonly=True
        )
        cleanroom_workspace_tool.record_baseline_hashes(lib_ws)

        # Modify the read-only contract
        os.chmod(ro_file, 0o644)
        with open(ro_file, "a", encoding="utf-8") as f:
            f.write("\n# rogue edit\n")
        os.chmod(ro_file, 0o444)

        # Tamper checks are retired: verify_integrity is a no-op and does not raise
        cleanroom_workspace_tool.verify_integrity(lib_ws)

    def test_phase_ordering(self) -> None:
        """Verifies Cleanroom phase ordering: high -> planning -> low -> grounding -> lib/test -> qa."""
        nodes = [
            {"pkg": "pkg1", "unit_name": "mod1", "role": "qa"},
            {"pkg": "pkg1", "unit_name": "mod1", "role": "lib"},
            {"pkg": "pkg1", "unit_name": "mod1", "role": "test"},
            {"pkg": "pkg1", "unit_name": "mod1", "role": "grounding"},
        ]
        ready = cleanroom_workspace_tool.get_ready_dirty_nodes(nodes)
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0]["role"], "grounding")

        nodes_no_grounding = [
            {"pkg": "pkg1", "unit_name": "mod1", "role": "qa"},
            {"pkg": "pkg1", "unit_name": "mod1", "role": "lib"},
            {"pkg": "pkg1", "unit_name": "mod1", "role": "test"},
        ]
        ready2 = cleanroom_workspace_tool.get_ready_dirty_nodes(nodes_no_grounding)
        self.assertEqual(len(ready2), 2)
        roles2 = {n["role"] for n in ready2}
        self.assertEqual(roles2, {"lib", "test"})

    def test_in_band_forward_dirty_evaluation(self) -> None:
        """Verifies dynamic forward dirtiness detection: timestamps and unacted feedback."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_dirty")
        part_dir = os.path.join(fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)

        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        low_file = os.path.join(part_dir, "low/config.pyi")
        lib_file = os.path.join(part_dir, "lib/config.py")

        # 1. Initially lib file is missing -> DIRTY
        low_role_def = cleanroom_workspace_tool.resolve_role_definition(
            "low", fake_repo
        )
        lib_role_def = cleanroom_workspace_tool.resolve_role_definition(
            "lib", fake_repo
        )

        res = cleanroom_workspace_tool.eval_unit_dirty(
            fake_repo, "staging/parts/agent", "config", "lib", lib_role_def
        )
        self.assertTrue(res["is_dirty"])

        # 2. Both files stamped clean at T1 -> CLEAN
        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )
        src_metadata.update_metadata(
            lib_file,
            last_cleaned="2026-10-04T12:05:00Z",
            last_changed="2026-10-04T12:05:00Z",
        )

        res_clean = cleanroom_workspace_tool.eval_unit_dirty(
            fake_repo, "staging/parts/agent", "config", "lib", lib_role_def
        )
        self.assertFalse(res_clean["is_dirty"])

        # 3. Upstream contract changed at T2 > T1 -> DIRTY
        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T12:10:00Z",
            last_changed="2026-10-04T12:10:00Z",
            change_summary="Added timeout",
        )
        res_after_upstream = cleanroom_workspace_tool.eval_unit_dirty(
            fake_repo, "staging/parts/agent", "config", "lib", lib_role_def
        )
        self.assertTrue(res_after_upstream["is_dirty"])
        self.assertTrue(
            any(
                "modified" in r or "changed" in r for r in res_after_upstream["reasons"]
            )
        )

        # 4. Unacted feedback on lib file -> DIRTY
        src_metadata.update_metadata(
            lib_file,
            last_cleaned="2026-10-04T12:15:00Z",
            last_changed="2026-10-04T12:15:00Z",
        )
        src_metadata.append_feedback(lib_file, "Missing docstring")
        res_fb = cleanroom_workspace_tool.eval_unit_dirty(
            fake_repo, "staging/parts/agent", "config", "lib", lib_role_def
        )
        self.assertTrue(res_fb["is_dirty"])

    def test_auditor_dirty_evaluation_and_stamping(self) -> None:
        """Verifies logless auditor dirtiness evaluation and <ROLE>_AUDIT tag stamping."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_auditor")
        part_dir = os.path.join(fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "tests"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)

        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config_impl")\n')

        lib_file = os.path.join(part_dir, "lib/config_impl.py")
        test_file = os.path.join(part_dir, "tests/config_impl_test.py")
        low_file = os.path.join(part_dir, "low/config_impl.pyi")

        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )
        src_metadata.update_metadata(
            lib_file,
            last_cleaned="2026-10-04T12:05:00Z",
            last_changed="2026-10-04T12:05:00Z",
        )
        src_metadata.update_metadata(
            test_file,
            last_cleaned="2026-10-04T12:05:00Z",
            last_changed="2026-10-04T12:05:00Z",
        )

        qa_role_def = cleanroom_workspace_tool.resolve_role_definition("qa", fake_repo)

        # 1. QA not yet audited -> DIRTY
        res = cleanroom_workspace_tool.eval_unit_dirty(
            fake_repo, "staging/parts/agent", "config_impl", "qa", qa_role_def
        )
        self.assertTrue(res["is_dirty"])

        # 2. Stamp QA_AUDIT -> CLEAN
        src_metadata.stamp_audit(lib_file, "qa")
        src_metadata.stamp_audit(test_file, "qa")

        res_after_audit = cleanroom_workspace_tool.eval_unit_dirty(
            fake_repo, "staging/parts/agent", "config_impl", "qa", qa_role_def
        )
        self.assertFalse(res_after_audit["is_dirty"])

        # 3. Lib modified after audit -> DIRTY again
        import time

        time.sleep(0.01)
        src_metadata.record_change(lib_file, "Updated implementation")
        res_after_mod = cleanroom_workspace_tool.eval_unit_dirty(
            fake_repo, "staging/parts/agent", "config_impl", "qa", qa_role_def
        )
        self.assertTrue(res_after_mod["is_dirty"])

    def test_read_only_blame_buffer_and_harvest(self) -> None:
        """Verifies blaming read-only upstream contracts buffers in .cleanroom_blame_buffer.json and harvests on sync."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_blame")
        part_dir = os.path.join(fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)

        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        low_file = os.path.join(part_dir, "low/config.pyi")
        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )

        # Commission lib workspace
        lib_ws = cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", repo_root=fake_repo
        )

        # Upstream contract in workspace is read-only
        ws_low = os.path.join(lib_ws, "staging/parts/agent/low/config.pyi")
        if os.path.exists(ws_low):
            st = os.stat(ws_low)
            self.assertEqual(st.st_mode & stat.S_IWUSR, 0)

        # Run blame from inside the workspace directory
        orig_cwd = os.getcwd()
        try:
            os.chdir(lib_ws)
            ret = cleanroom_workspace_tool.run_blame_command(
                "staging/parts/agent/lib/config.py",
                "staging/parts/agent/low/config.pyi",
                "Contract missing timeout parameter",
                repo_root=fake_repo,
            )
            self.assertEqual(ret, 0)

            # Blame buffer file must exist in role workspace root
            buf_path = os.path.join(lib_ws, ".cleanroom_blame_buffer.json")
            self.assertTrue(os.path.isfile(buf_path))
            with open(buf_path, "r", encoding="utf-8") as bf:
                entries = json.load(bf)
            self.assertEqual(len(entries), 1)
            self.assertIn(
                "Contract missing timeout parameter", entries[0]["explanation"]
            )
        finally:
            os.chdir(orig_cwd)

        # Run cleanroom_sync to harvest blame into canonical main
        cleanroom_workspace_tool.converge_role_workspace(lib_ws, fake_repo, "lib")

        # Canonical file header must have FEEDBACK appended
        canon_meta = src_metadata.extract_metadata(low_file)
        self.assertIsNotNone(canon_meta)
        self.assertEqual(len(canon_meta.feedback), 1)
        self.assertIn("Contract missing timeout parameter", canon_meta.feedback[0])

        # Blame buffer in role workspace must be cleared
        with open(buf_path, "r", encoding="utf-8") as bf:
            buf_cleared = json.load(bf)
        self.assertEqual(len(buf_cleared), 0)

    def test_inbound_harvest_and_outbound_cascade(self) -> None:
        """Verifies complete cascade sync: role changes harvested to main, main specs cascaded to role."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_cascade")
        part_dir = os.path.join(fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)

        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        low_file = os.path.join(part_dir, "low/config.pyi")
        lib_file = os.path.join(part_dir, "lib/config.py")

        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )
        src_metadata.update_metadata(
            lib_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )

        # 1. Commission lib workspace
        lib_ws = cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", repo_root=fake_repo
        )

        # 2. Worker edits lib/config.py in role workspace
        ws_lib_file = os.path.join(lib_ws, "staging/parts/agent/lib/config.py")
        src_metadata.update_metadata(
            ws_lib_file,
            last_cleaned="2026-10-04T12:30:00Z",
            last_changed="2026-10-04T12:30:00Z",
            change_summary="Implemented timeout handling",
        )

        # 3. Synchronize
        cleanroom_workspace_tool.converge_role_workspace(lib_ws, fake_repo, "lib")

        # Canonical file must receive the updated change summary
        canon_meta = src_metadata.extract_metadata(lib_file)
        self.assertIsNotNone(canon_meta)
        self.assertEqual(canon_meta.change_summary, "Implemented timeout handling")

        # 4. Canonical low contract is updated in main
        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T13:00:00Z",
            last_changed="2026-10-04T13:00:00Z",
            change_summary="Expanded protocol methods",
        )

        # 5. Outbound cascade sync down to role workspace
        cleanroom_workspace_tool.converge_role_workspace(lib_ws, fake_repo, "lib")

        ws_low = os.path.join(lib_ws, "staging/parts/agent/low/config.pyi")
        ws_low_meta = src_metadata.extract_metadata(ws_low)
        self.assertIsNotNone(ws_low_meta)
        self.assertEqual(ws_low_meta.change_summary, "Expanded protocol methods")

    def test_conflict_detection(self) -> None:
        """Verifies that concurrent edits in role and canonical main after last_sync trigger conflict detection."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_conflict")
        part_dir = os.path.join(fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)

        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        lib_file = os.path.join(part_dir, "lib/config.py")
        src_metadata.update_metadata(
            lib_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )

        # Commission workspace and set known last_sync
        lib_ws = cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", repo_root=fake_repo
        )
        cleanroom_workspace_tool.save_role_metadata(
            lib_ws,
            "//update_python_with_ai:lib",
            "lib",
            dir_scope="staging",
            last_sync_timestamp="2026-10-04T12:00:00Z",
            repo_root=fake_repo,
        )

        # Mutate canonical main at T = 12:10:00Z
        src_metadata.update_metadata(
            lib_file,
            last_cleaned="2026-10-04T12:10:00Z",
            last_changed="2026-10-04T12:10:00Z",
            change_summary="Edit in main",
        )

        # Mutate role workspace at T = 12:15:00Z with differing content
        ws_lib = os.path.join(lib_ws, "staging/parts/agent/lib/config.py")
        src_metadata.update_metadata(
            ws_lib,
            last_cleaned="2026-10-04T12:15:00Z",
            last_changed="2026-10-04T12:15:00Z",
            change_summary="Conflicting edit in role",
        )

        # Converge role workspace: conflict detection should prevent overwriting main
        cleanroom_workspace_tool.converge_role_workspace(lib_ws, fake_repo, "lib")

        canon_meta = src_metadata.extract_metadata(lib_file)
        self.assertIsNotNone(canon_meta)
        self.assertEqual(
            canon_meta.change_summary,
            "Edit in main",
            "Main file should not be overwritten on conflict",
        )

    def test_decommission_workspace_safety(self) -> None:
        """Verifies decommission_workspace safety check: refuses when dirty unless force=True."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_decomm")
        part_dir = os.path.join(fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)

        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        lib_file = os.path.join(part_dir, "lib/config.py")
        src_metadata.update_metadata(
            lib_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )

        lib_ws = cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", repo_root=fake_repo
        )

        # Mutate file in role workspace without syncing
        ws_lib = os.path.join(lib_ws, "staging/parts/agent/lib/config.py")
        with open(ws_lib, "a") as f:
            f.write("\n# uncommitted change\n")

        # Decommission without force should fail
        refused = cleanroom_workspace_tool.decommission_workspace(
            "lib", dir_scope="staging", dest=lib_ws, force=False, repo_root=fake_repo
        )
        self.assertFalse(refused)
        self.assertTrue(os.path.exists(lib_ws))

        # Decommission with force should succeed
        succeeded = cleanroom_workspace_tool.decommission_workspace(
            "lib", dir_scope="staging", dest=lib_ws, force=True, repo_root=fake_repo
        )
        self.assertTrue(succeeded)
        self.assertFalse(os.path.exists(lib_ws))

    def test_find_existing_role_workspaces_directory_scoped(self) -> None:
        """Tests that find_existing_role_workspaces finds directory-scoped workspaces."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_disc")
        os.makedirs(fake_repo, exist_ok=True)

        ws_dir = os.path.join(
            self.test_dir, "role_workspaces", "fake_repo_disc_lib_staging"
        )
        os.makedirs(ws_dir, exist_ok=True)
        cleanroom_workspace_tool.save_role_metadata(
            ws_dir,
            "//update_python_with_ai:lib",
            "lib",
            dir_scope="staging",
            repo_root=fake_repo,
        )

        found = cleanroom_workspace_tool.find_existing_role_workspaces(
            repo_root=fake_repo
        )
        found_dirs = [f[0] for f in found]
        self.assertIn(ws_dir, found_dirs)

    def test_commission_decommission_registry_tracking(self) -> None:
        """Verifies that commission and decommission accurately update .cleanroom_workspaces.json."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_registry")
        os.makedirs(fake_repo, exist_ok=True)
        lib_ws = os.path.join(self.test_dir, "ws_lib_reg")

        cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", dest=lib_ws, repo_root=fake_repo
        )
        registered = cleanroom_workspace_tool.load_registered_workspaces(fake_repo)
        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0]["role"], "lib")
        self.assertEqual(registered[0]["dir"], "staging")
        self.assertEqual(registered[0]["workspace_dir"], os.path.abspath(lib_ws))

        cleanroom_workspace_tool.decommission_workspace(
            "lib", dir_scope="staging", dest=lib_ws, force=True, repo_root=fake_repo
        )
        registered_after = cleanroom_workspace_tool.load_registered_workspaces(
            fake_repo
        )
        self.assertEqual(len(registered_after), 0)

    def test_cli_positional_commands(self) -> None:
        """Verifies that positional commission and decommission subcommands work via main()."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_cli")
        os.makedirs(fake_repo, exist_ok=True)
        ws_dest = os.path.join(self.test_dir, "ws_cli")

        # Positional: cleanroom-sync commission lib staging --dest <dest>
        ret_comm = cleanroom_workspace_tool.main(
            ["commission", "lib", "staging", "--dest", ws_dest]
        )
        self.assertEqual(ret_comm, 0)
        self.assertTrue(os.path.isdir(ws_dest))

        # Positional: cleanroom-sync decommission lib staging --dest <dest> --force
        ret_decomm = cleanroom_workspace_tool.main(
            ["decommission", "lib", "staging", "--dest", ws_dest, "--force"]
        )
        self.assertEqual(ret_decomm, 0)
        self.assertFalse(os.path.exists(ws_dest))

    def test_two_way_sync_and_audit_sync(self) -> None:
        """Verifies two-way synchronization: role changes harvested, main specs pushed, audits synchronized."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_twoway")
        part_dir = os.path.join(fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)

        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        lib_file = os.path.join(part_dir, "lib/config.py")
        low_file = os.path.join(part_dir, "low/config.pyi")

        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T10:00:00Z",
            last_changed="2026-10-04T10:00:00Z",
        )
        src_metadata.update_metadata(
            lib_file,
            last_cleaned="2026-10-04T10:00:00Z",
            last_changed="2026-10-04T10:00:00Z",
        )

        # Commission workspace
        lib_ws = cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", repo_root=fake_repo
        )

        # 1. Role workspace modifies lib/config.py with newer LAST_CHANGED and stamps QA_AUDIT
        ws_lib = os.path.join(lib_ws, "staging/parts/agent/lib/config.py")
        src_metadata.update_metadata(
            ws_lib,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
            change_summary="Role updated config",
            audits={"QA_AUDIT": "2026-10-04T12:00:00Z"},
        )

        # 2. Canonical main updates low/config.pyi with newer LAST_CHANGED
        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T13:00:00Z",
            last_changed="2026-10-04T13:00:00Z",
            change_summary="Main updated spec",
        )

        # 3. Zero-argument sync across all commissioned workspaces
        ret = cleanroom_workspace_tool.cleanroom_sync(repo_root=fake_repo)
        self.assertEqual(ret, 0)

        # Verify role change and audit were harvested into main
        main_lib_meta = src_metadata.extract_metadata(lib_file)
        self.assertIsNotNone(main_lib_meta)
        self.assertEqual(main_lib_meta.last_changed, "2026-10-04T12:00:00Z")
        self.assertEqual(main_lib_meta.change_summary, "Role updated config")
        self.assertEqual(main_lib_meta.audits.get("QA_AUDIT"), "2026-10-04T12:00:00Z")

        # Verify main spec change was pushed into role workspace
        ws_low = os.path.join(lib_ws, "staging/parts/agent/low/config.pyi")
        ws_low_meta = src_metadata.extract_metadata(ws_low)
        self.assertIsNotNone(ws_low_meta)
        self.assertEqual(ws_low_meta.last_changed, "2026-10-04T13:00:00Z")
        self.assertEqual(ws_low_meta.change_summary, "Main updated spec")

    def test_cleanroom_sync_sys_flag_and_opaque_tools(self) -> None:
        """Verifies that bin tools are opaque zipapps and --sys refreshes non-parts system files."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_sys")
        os.makedirs(fake_repo, exist_ok=True)
        pyright_cfg = os.path.join(fake_repo, "pyrightconfig.json")
        with open(pyright_cfg, "w", encoding="utf-8") as f:
            f.write('{"version": 1}\n')

        lib_ws = cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", repo_root=fake_repo
        )

        # 1. Verify bin/ tools are opaque zipapp binaries (starts with shebang + zip magic bytes PK)
        get_work_bin = os.path.join(lib_ws, "bin/get_work")
        self.assertTrue(os.path.isfile(get_work_bin))
        with open(get_work_bin, "rb") as f:
            header = f.read(30)
        self.assertTrue(header.startswith(b"#!/usr/bin/env python3\nPK"))

        # Verify no loose python scripts or orchestrator tools in bin/
        self.assertFalse(
            os.path.exists(os.path.join(lib_ws, "bin/cleanroom_workspace_tool.py"))
        )
        self.assertFalse(
            os.path.exists(os.path.join(lib_ws, "bin/cleanroom_role_tool.py"))
        )

        # 2. Update system config in main repo
        with open(pyright_cfg, "w", encoding="utf-8") as f:
            f.write('{"version": 2}\n')

        # 3. Run sync with sys_refresh=True
        ret = cleanroom_workspace_tool.cleanroom_sync(
            repo_root=fake_repo, sys_refresh=True
        )
        self.assertEqual(ret, 0)

        # 4. Verify system file was refreshed in role workspace
        ws_pyright = os.path.join(lib_ws, "pyrightconfig.json")
        with open(ws_pyright, "r", encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), '{"version": 2}')

    def test_dirty_propagation_from_main_to_role_workspaces(self) -> None:
        """Verifies that clearing LAST_CLEANED or removing AUDIT tags in main propagates to role workspaces."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_dirty_prop")
        part_dir = os.path.join(fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)

        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        lib_file = os.path.join(part_dir, "lib/config.py")
        src_metadata.update_metadata(
            lib_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
            audits={"QA_AUDIT": "2026-10-04T12:00:00Z"},
        )

        # Commission both lib workspace and qa workspace
        lib_ws = cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", repo_root=fake_repo
        )
        qa_ws = cleanroom_workspace_tool.commission_workspace(
            "qa", dir_scope="staging", repo_root=fake_repo
        )

        # Initially, role workspaces have LAST_CLEANED and QA_AUDIT
        ws_lib = os.path.join(lib_ws, "staging/parts/agent/lib/config.py")
        ws_qa = os.path.join(qa_ws, "staging/parts/agent/lib/config.py")
        self.assertIsNotNone(src_metadata.extract_metadata(ws_lib).last_cleaned)
        self.assertIn("QA_AUDIT", src_metadata.extract_metadata(ws_lib).audits)
        self.assertIn("QA_AUDIT", src_metadata.extract_metadata(ws_qa).audits)

        # 1. Dirty producer node in main: clear LAST_CLEANED
        src_metadata.delete_last_cleaned(lib_file)
        self.assertIsNone(src_metadata.extract_metadata(lib_file).last_cleaned)

        # 2. Dirty auditor node in main: remove QA_AUDIT
        src_metadata.update_metadata(lib_file, clear_audits=True)
        self.assertNotIn("QA_AUDIT", src_metadata.extract_metadata(lib_file).audits)

        # 3. Synchronize
        cleanroom_workspace_tool.cleanroom_sync(repo_root=fake_repo)

        # 4. Verify main DID NOT resurrect QA_AUDIT
        main_meta = src_metadata.extract_metadata(lib_file)
        self.assertIsNone(main_meta.last_cleaned)
        self.assertNotIn("QA_AUDIT", main_meta.audits)

        # 5. Verify lib workspace had LAST_CLEANED cleared and QA_AUDIT removed
        lib_meta = src_metadata.extract_metadata(ws_lib)
        self.assertIsNone(lib_meta.last_cleaned)
        self.assertNotIn("QA_AUDIT", lib_meta.audits)

        # 6. Verify qa workspace had QA_AUDIT removed
        qa_meta = src_metadata.extract_metadata(ws_qa)
        self.assertNotIn("QA_AUDIT", qa_meta.audits)

    def test_dirty_tag_two_way_sync_lifecycle(self) -> None:
        """Verifies producer node dirtying with DIRTY tag propagates to workspace,
        and cleaning in workspace removes DIRTY tag and propagates back to main.
        """
        fake_repo = os.path.join(self.test_dir, "fake_repo_dirty_tag")
        part_dir = os.path.join(fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)

        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        lib_file = os.path.join(part_dir, "lib/config.py")
        src_metadata.update_metadata(
            lib_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )

        lib_ws = cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", repo_root=fake_repo
        )
        ws_lib = os.path.join(lib_ws, "staging/parts/agent/lib/config.py")

        # 1. Main marks dirty with DIRTY tag
        src_metadata.mark_dirty(lib_file, reason="Manual dirty verification needed")
        main_meta = src_metadata.extract_metadata(lib_file)
        self.assertIsNotNone(main_meta)
        assert main_meta is not None
        self.assertEqual(main_meta.dirty, "Manual dirty verification needed")

        # 2. Sync to role workspace
        cleanroom_workspace_tool.cleanroom_sync(repo_root=fake_repo)

        # 3. Workspace should have the DIRTY tag and be evaluated as dirty
        ws_meta = src_metadata.extract_metadata(ws_lib)
        self.assertIsNotNone(ws_meta)
        assert ws_meta is not None
        self.assertEqual(ws_meta.dirty, "Manual dirty verification needed")
        eval_res = cleanroom_workspace_tool.eval_unit_dirty(
            lib_ws,
            "staging/parts/agent",
            "config",
            "lib",
            cleanroom_workspace_tool.resolve_role_definition("lib", fake_repo),
        )
        self.assertTrue(eval_res["is_dirty"])
        self.assertTrue(any("DIRTY" in r for r in eval_res["reasons"]))

        # 4. Workspace cleans the file (simulating bin/submit)
        src_metadata.mark_clean(ws_lib)
        ws_meta_clean = src_metadata.extract_metadata(ws_lib)
        self.assertIsNotNone(ws_meta_clean)
        assert ws_meta_clean is not None
        self.assertIsNone(ws_meta_clean.dirty)

        # 5. Sync back to main
        cleanroom_workspace_tool.cleanroom_sync(repo_root=fake_repo)

        # 6. Main receives the clean file without DIRTY tag
        main_meta_clean = src_metadata.extract_metadata(lib_file)
        self.assertIsNotNone(main_meta_clean)
        assert main_meta_clean is not None
        self.assertIsNone(main_meta_clean.dirty)
        self.assertEqual(main_meta_clean.last_cleaned, ws_meta_clean.last_cleaned)

    def test_auditor_buffer_harvesting_and_dirty_handling(self) -> None:
        """Verifies auditor workspace buffering via .cleanroom_audit_buffer.json,
        harvesting into main, and mark_node_dirty behavior on auditor nodes.
        """
        fake_repo = os.path.join(self.test_dir, "fake_repo_auditor_buf")
        part_dir = os.path.join(fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "tests"), exist_ok=True)

        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        lib_file = os.path.join(part_dir, "lib/config.py")
        src_metadata.update_metadata(
            lib_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )

        qa_ws = cleanroom_workspace_tool.commission_workspace(
            "qa", dir_scope="staging", repo_root=fake_repo
        )
        ws_lib = os.path.join(qa_ws, "staging/parts/agent/lib/config.py")

        # In qa workspace, lib/config.py is read-only
        st = os.stat(ws_lib)
        self.assertFalse(bool(st.st_mode & stat.S_IWUSR))

        # 1. QA writes an audit entry into .cleanroom_audit_buffer.json (without touching read-only file)
        audit_buf_path = os.path.join(qa_ws, cleanroom_workspace_tool.AUDIT_BUFFER_FILE)
        entries = [
            {
                "target": "staging/parts/agent/lib/config.py",
                "audited_by": "qa",
                "audit_tag": "QA_AUDIT",
                "timestamp": "2026-10-04T15:00:00Z",
            }
        ]
        with open(audit_buf_path, "w", encoding="utf-8") as f:
            json.dump(entries, f)

        # 2. Sync harvests the buffer into main
        cleanroom_workspace_tool.cleanroom_sync(repo_root=fake_repo)

        # 3. Verify main received QA_AUDIT and buffer was cleared
        main_meta = src_metadata.extract_metadata(lib_file)
        self.assertIsNotNone(main_meta)
        assert main_meta is not None
        self.assertEqual(main_meta.audits.get("QA_AUDIT"), "2026-10-04T15:00:00Z")
        with open(audit_buf_path, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f), [])

        # 4. Calling mark_node_dirty on auditor node when target is clean -> removes audit tag
        res = cleanroom_workspace_tool.mark_node_dirty(
            "staging/parts/agent", "config", "qa", repo_root=fake_repo
        )
        self.assertTrue(res)
        main_meta_after_dirty = src_metadata.extract_metadata(lib_file)
        self.assertIsNotNone(main_meta_after_dirty)
        assert main_meta_after_dirty is not None
        self.assertNotIn("QA_AUDIT", main_meta_after_dirty.audits)

        # 5. Calling mark_node_dirty on auditor node when target is ALREADY dirty -> no-op
        # Mark target dirty first:
        src_metadata.mark_dirty(lib_file, "Target broken")
        res_noop = cleanroom_workspace_tool.mark_node_dirty(
            "staging/parts/agent", "config", "qa", repo_root=fake_repo
        )
        self.assertFalse(res_noop)

    def test_classify_unit_type(self) -> None:
        """Verifies cleanroom component classification: _ext, _asm, _impl, and interface default."""
        self.assertEqual(
            cleanroom_workspace_tool.classify_unit_type("commonmark_ext"), "external"
        )
        self.assertEqual(
            cleanroom_workspace_tool.classify_unit_type("dag_asm"), "assembly"
        )
        self.assertEqual(
            cleanroom_workspace_tool.classify_unit_type("sandbox_file_reader_impl"),
            "implementation",
        )
        self.assertEqual(
            cleanroom_workspace_tool.classify_unit_type("agent_config"), "interface"
        )
        self.assertEqual(
            cleanroom_workspace_tool.classify_unit_type("dag_storage"), "interface"
        )
        self.assertEqual(
            cleanroom_workspace_tool.classify_unit_type("runner_logger"), "interface"
        )

    def test_commission_qa_workspace_build_files(self) -> None:
        """Verifies QA auditor workspace receives BUILD.bazel for feedback deps (lib and tests), not star_role_deps."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_qa_build")
        part_dir = os.path.join(fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "tests"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)

        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config_impl")\n')
        with open(
            os.path.join(part_dir, "lib/BUILD.bazel"), "w", encoding="utf-8"
        ) as f:
            f.write("# lib build\n")
        with open(
            os.path.join(part_dir, "tests/BUILD.bazel"), "w", encoding="utf-8"
        ) as f:
            f.write("# tests build\n")
        with open(
            os.path.join(part_dir, "low/BUILD.bazel"), "w", encoding="utf-8"
        ) as f:
            f.write("# low build\n")

        lib_file = os.path.join(part_dir, "lib/config_impl.py")
        test_file = os.path.join(part_dir, "tests/config_impl_test.py")
        low_file = os.path.join(part_dir, "low/config_impl.pyi")

        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )
        src_metadata.update_metadata(
            lib_file,
            last_cleaned="2026-10-04T12:05:00Z",
            last_changed="2026-10-04T12:05:00Z",
        )
        src_metadata.update_metadata(
            test_file,
            last_cleaned="2026-10-04T12:05:00Z",
            last_changed="2026-10-04T12:05:00Z",
        )

        qa_ws = cleanroom_workspace_tool.commission_workspace(
            "qa", dir_scope="staging", repo_root=fake_repo
        )

        # lib and tests are feedback_role_deps for QA -> MUST have BUILD.bazel
        self.assertTrue(
            os.path.isfile(os.path.join(qa_ws, "staging/parts/agent/lib/BUILD.bazel"))
        )
        self.assertTrue(
            os.path.isfile(os.path.join(qa_ws, "staging/parts/agent/tests/BUILD.bazel"))
        )

        # low is star_role_deps for QA -> must NOT have BUILD.bazel
        self.assertFalse(
            os.path.exists(os.path.join(qa_ws, "staging/parts/agent/low/BUILD.bazel"))
        )

    def test_write_role_agents_md_loosely_specified(self) -> None:
        """Verifies AGENTS.md instructs following companion guide rather than prescribing rigid view_file sequence."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_agents_md")
        qa_ws = os.path.join(fake_repo, "qa_ws")
        lib_ws = os.path.join(fake_repo, "lib_ws")
        os.makedirs(qa_ws, exist_ok=True)
        os.makedirs(lib_ws, exist_ok=True)

        cleanroom_workspace_tool.write_role_agents_md(qa_ws, "qa", repo_root=fake_repo)
        cleanroom_workspace_tool.write_role_agents_md(
            lib_ws, "lib", repo_root=fake_repo
        )

        with open(os.path.join(qa_ws, "AGENTS.md"), "r", encoding="utf-8") as f:
            qa_content = f.read()
        self.assertIn("Follow the companion guide", qa_content)
        self.assertIn(
            "Always Run `bin/get_work` First (Even for Out-of-Band Work)", qa_content
        )
        self.assertNotIn(
            "call view_file on target implementation, test, and contract files",
            qa_content,
        )

        with open(os.path.join(lib_ws, "AGENTS.md"), "r", encoding="utf-8") as f:
            lib_content = f.read()
        self.assertIn("Follow the companion guide", lib_content)
        self.assertIn(
            "Always Run `bin/get_work` First (Even for Out-of-Band Work)", lib_content
        )
        self.assertNotIn(
            "call view_file on both the upstream contract and the target file",
            lib_content,
        )

    def test_find_all_dirty_in_scope_auditor_target_file(self) -> None:
        """Verifies find_all_dirty_in_scope sets target_file to primary feedback target for auditor roles."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_dirty_scope")
        part_dir = os.path.join(fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "tests"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)

        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config_impl")\n')

        lib_file = os.path.join(part_dir, "lib/config_impl.py")
        test_file = os.path.join(part_dir, "tests/config_impl_test.py")
        low_file = os.path.join(part_dir, "low/config_impl.pyi")

        src_metadata.update_metadata(
            low_file,
            last_cleaned="2026-10-04T12:00:00Z",
            last_changed="2026-10-04T12:00:00Z",
        )
        src_metadata.update_metadata(
            lib_file,
            last_cleaned="2026-10-04T12:05:00Z",
            last_changed="2026-10-04T12:05:00Z",
        )
        src_metadata.update_metadata(
            test_file,
            last_cleaned="2026-10-04T12:05:00Z",
            last_changed="2026-10-04T12:05:00Z",
        )

        dirty_items = cleanroom_workspace_tool.find_all_dirty_in_scope(
            fake_repo, dir_scope="staging", role_filter="qa"
        )
        self.assertEqual(len(dirty_items), 1)
        item = dirty_items[0]
        # Target file must be lib/config_impl.py, NOT virtual qa/config_impl
        self.assertEqual(item["target_file"], "staging/parts/agent/lib/config_impl.py")
        # Reasons must only list the primary target as uncertified
        self.assertEqual(len(item["reasons"]), 1)
        self.assertIn(
            "staging/parts/agent/lib/config_impl.py has not been certified with QA_AUDIT",
            item["reasons"][0],
        )

    def test_one_and_done_blame_distribution(self) -> None:
        """Verifies one-and-done synchronization: QA blames a Lib contract in qa_ws,
        and a single cleanroom_sync() harvests blame into main AND cascades DIRTY tag
        and FEEDBACK into lib_ws where Lib can immediately fix it.
        """
        fake_repo = os.path.join(self.test_dir, "fake_repo_one_and_done")
        part_dir = os.path.join(fake_repo, "staging/parts/agent")
        os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(part_dir, "tests"), exist_ok=True)

        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_python_with_ai(name = "config")\n')

        low_file = os.path.join(part_dir, "low/config.pyi")
        lib_file = os.path.join(part_dir, "lib/config.py")
        test_file = os.path.join(part_dir, "tests/config_test.py")

        with open(low_file, "w", encoding="utf-8") as f:
            f.write("# Specification\n")
        with open(lib_file, "w", encoding="utf-8") as f:
            f.write("def get_config(): return {}\n")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("def test_config(): pass\n")

        init_ts = "2026-10-04T12:00:00Z"
        src_metadata.update_metadata(
            low_file, last_cleaned=init_ts, last_changed=init_ts
        )
        src_metadata.update_metadata(
            lib_file,
            last_cleaned=init_ts,
            last_changed=init_ts,
            audits={"QA_AUDIT": init_ts},
        )
        src_metadata.update_metadata(
            test_file,
            last_cleaned=init_ts,
            last_changed=init_ts,
            audits={"QA_AUDIT": init_ts},
        )

        # Commission lib workspace and qa workspace
        lib_ws = cleanroom_workspace_tool.commission_workspace(
            "lib", dir_scope="staging", repo_root=fake_repo
        )
        qa_ws = cleanroom_workspace_tool.commission_workspace(
            "qa", dir_scope="staging", repo_root=fake_repo
        )

        ws_lib_file = os.path.join(lib_ws, "staging/parts/agent/lib/config.py")
        ws_qa_lib_file = os.path.join(qa_ws, "staging/parts/agent/lib/config.py")

        # In qa_ws, lib/config.py is read-only
        st = os.stat(ws_qa_lib_file)
        self.assertEqual(st.st_mode & stat.S_IWUSR, 0)

        # QA records blame on read-only lib/config.py
        critique = "get_config() crashes on missing environment variable"
        orig_cwd = os.getcwd()
        try:
            os.chdir(qa_ws)
            ret = cleanroom_workspace_tool.run_blame_command(
                "staging/parts/agent/tests/config_test.py",
                "staging/parts/agent/lib/config.py",
                critique,
                repo_root=fake_repo,
            )
            self.assertEqual(ret, 0)
            qa_blame_buf = os.path.join(qa_ws, ".cleanroom_blame_buffer.json")
            self.assertTrue(os.path.isfile(qa_blame_buf))
            with open(qa_blame_buf, "r", encoding="utf-8") as bf:
                entries = json.load(bf)
            self.assertEqual(len(entries), 1)
            self.assertIn("dirty_reason", entries[0])
        finally:
            os.chdir(orig_cwd)

        # Before sync: lib_ws does NOT have feedback or dirty tag yet
        pre_sync_lib_meta = src_metadata.extract_metadata(ws_lib_file)
        self.assertIsNotNone(pre_sync_lib_meta)
        assert pre_sync_lib_meta is not None
        self.assertIsNone(pre_sync_lib_meta.dirty)
        self.assertEqual(len(pre_sync_lib_meta.feedback), 0)

        # ONE AND DONE SYNC: run cleanroom_sync() once!
        sync_ret = cleanroom_workspace_tool.cleanroom_sync(repo_root=fake_repo)
        self.assertEqual(sync_ret, 0)

        # 1. Main workspace: harvested blame, marked dirty, appended feedback, advanced LAST_CLEANED
        main_meta = src_metadata.extract_metadata(lib_file)
        self.assertIsNotNone(main_meta)
        assert main_meta is not None
        self.assertIsNotNone(main_meta.dirty)
        self.assertIn("staging/parts/agent/tests/config_test.py", main_meta.dirty)
        self.assertEqual(len(main_meta.feedback), 1)
        self.assertIn(critique, main_meta.feedback[0])
        self.assertGreater(main_meta.last_cleaned, init_ts)

        # 2. QA workspace: blame buffer was consumed and cleared
        with open(qa_blame_buf, "r", encoding="utf-8") as bf:
            qa_buf_after = json.load(bf)
        self.assertEqual(len(qa_buf_after), 0)

        # 3. Lib workspace: IN THE SAME RUN, received DIRTY tag, FEEDBACK, and updated LAST_CLEANED!
        lib_meta = src_metadata.extract_metadata(ws_lib_file)
        self.assertIsNotNone(lib_meta)
        assert lib_meta is not None
        self.assertIsNotNone(lib_meta.dirty)
        self.assertEqual(lib_meta.dirty, main_meta.dirty)
        self.assertEqual(len(lib_meta.feedback), 1)
        self.assertIn(critique, lib_meta.feedback[0])
        self.assertEqual(lib_meta.last_cleaned, main_meta.last_cleaned)

        # 4. Lib workspace dirty evaluation: reports dirty and ready to fix!
        lib_dirty = cleanroom_workspace_tool.find_all_dirty_in_scope(
            lib_ws, dir_scope="staging", role_filter="lib"
        )
        self.assertEqual(len(lib_dirty), 1)
        self.assertEqual(
            lib_dirty[0]["target_file"], "staging/parts/agent/lib/config.py"
        )
        self.assertTrue(any("DIRTY" in r for r in lib_dirty[0]["reasons"]))
        self.assertTrue(any(critique in r for r in lib_dirty[0]["reasons"]))

    def test_resolve_main_workspace_from_convention(self) -> None:
        """Verifies resolve_main_workspace_from_convention on conventional layout and nested paths."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            main_repo = os.path.join(tmp_dir, "my_cleanroom")
            role_ws = os.path.join(
                tmp_dir, "role_workspaces", "my_cleanroom_test_staging"
            )
            os.makedirs(main_repo, exist_ok=True)
            os.makedirs(role_ws, exist_ok=True)

            # Write pathless descriptor
            desc_path = os.path.join(role_ws, ".cleanroom_role.json")
            with open(desc_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "role_address": "//update_python_with_ai:test",
                        "role_name": "test",
                        "parts_dir": "staging",
                    },
                    f,
                )

            # 1. Direct role workspace root
            main_root, ws_name, role_addr, d_scope = (
                cleanroom_workspace_tool.resolve_main_workspace_from_convention(role_ws)
            )
            self.assertEqual(main_root, os.path.realpath(main_repo))
            self.assertEqual(ws_name, "my_cleanroom")
            self.assertEqual(role_addr, "//update_python_with_ai:test")
            self.assertEqual(d_scope, "staging")

            # 2. Deeply nested subdirectory inside role workspace
            nested_sub = os.path.join(role_ws, "staging/parts/foo/tests")
            os.makedirs(nested_sub, exist_ok=True)
            n_main_root, n_ws_name, n_role_addr, n_d_scope = (
                cleanroom_workspace_tool.resolve_main_workspace_from_convention(
                    nested_sub
                )
            )
            self.assertEqual(n_main_root, os.path.realpath(main_repo))
            self.assertEqual(n_ws_name, "my_cleanroom")
            self.assertEqual(n_role_addr, "//update_python_with_ai:test")
            self.assertEqual(n_d_scope, "staging")

    def test_pathless_descriptor_disk_format_and_dynamic_resolution(self) -> None:
        """Verifies that .cleanroom_role.json on disk has NO host paths, and load_role_metadata dynamically resolves them."""
        ws = cleanroom_workspace_tool.commission_workspace(
            "//update_python_with_ai:test",
            dir_scope="staging",
            repo_root=self.test_dir,
        )

        # 1. Verify disk format has zero host paths
        desc_path = os.path.join(ws, ".cleanroom_role.json")
        self.assertTrue(os.path.isfile(desc_path))
        with open(desc_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        self.assertNotIn("main_workspace_root", raw_data)
        self.assertNotIn("main_workspace", raw_data)
        self.assertEqual(raw_data["role_address"], "//update_python_with_ai:test")
        self.assertEqual(raw_data["role_name"], "test")
        self.assertEqual(raw_data["parts_dir"], "staging")

        # 2. Verify load_role_metadata dynamically resolves main_workspace_root
        meta = cleanroom_workspace_tool.load_role_metadata(ws)
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertIn("main_workspace_root", meta)
        self.assertEqual(
            os.path.realpath(meta["main_workspace_root"]),
            os.path.realpath(self.test_dir),
        )
        self.assertEqual(meta["main_workspace"], os.path.basename(self.test_dir))

    def test_deleted_lib_file_reconstituted_and_marked_dirty(self) -> None:
        """Verifies that deleting a lib file causes it to be marked dirty and reconstituted from template upon get_work / pull."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            main_repo = os.path.join(tmp_dir, "fake_repo")
            part_dir = os.path.join(main_repo, "staging/parts/agent")
            os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
            os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)

            with open(
                os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8"
            ) as f:
                f.write('update_python_with_ai(name = "config_impl")\n')

            # Create companion low spec
            low_file = os.path.join(part_dir, "low/config_impl.pyi")
            cleanroom_workspace_tool.write_file_with_perms(
                low_file,
                "# low spec\ndef get_config() -> str: ...\n",
                readonly=False,
            )
            src_metadata.update_metadata(
                low_file,
                last_cleaned="2026-10-04T12:00:00Z",
                last_changed="2026-10-04T12:00:00Z",
            )

            # Commission lib role workspace
            lib_ws = cleanroom_workspace_tool.commission_workspace(
                "//update_python_with_ai:lib",
                dir_scope="staging",
                repo_root=main_repo,
            )

            # Simulate user deleting lib file in main
            main_lib = os.path.join(part_dir, "lib/config_impl.py")
            if os.path.exists(main_lib):
                os.remove(main_lib)

            # 1. Verify it is detected dirty
            dirty_res = cleanroom_workspace_tool.eval_unit_dirty(
                main_repo,
                "staging/parts/agent",
                "config_impl",
                "lib",
                cleanroom_workspace_tool.resolve_role_definition("lib", main_repo),
            )
            self.assertTrue(dirty_res["is_dirty"])
            self.assertTrue(any("does not exist" in r for r in dirty_res["reasons"]))

            # 2. Simulate lib role agent running get_work (pull_workspace_from_main)
            cleanroom_workspace_tool.pull_workspace_from_main(
                lib_ws, main_repo, "lib", dir_scope="staging"
            )

            # 3. Verify file is reconstituted in main and workspace from low spec
            self.assertTrue(os.path.isfile(main_lib))
            ws_lib = os.path.join(lib_ws, "staging/parts/agent/lib/config_impl.py")
            self.assertTrue(os.path.isfile(ws_lib))

            with open(ws_lib, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Requirements specified in config_impl.pyi", content)

            # 4. Verify work queue sees it ready
            ready, blocked = cleanroom_workspace_tool.compute_role_work_queue(
                "lib", "staging", main_repo
            )
            self.assertEqual(len(ready), 1)
            self.assertEqual(ready[0]["unit_name"], "config_impl")
            self.assertEqual(len(blocked), 0)

    def test_test_role_workspace_stub_dependencies_never_leak_real_implementation(
        self,
    ) -> None:
        """Verifies that in a test role workspace, stub_role_deps (lib/*.py) are ALWAYS
        synthesized as pure read-only stubs from companion .pyi contracts and NEVER
        overwritten by real implementation code from main during commissioning, sync, or pull."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            main_repo = os.path.join(tmp_dir, "cleanroom_main")
            part_dir = os.path.join(main_repo, "staging/parts/calc")
            os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
            os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
            os.makedirs(os.path.join(part_dir, "tests"), exist_ok=True)

            with open(
                os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8"
            ) as f:
                f.write('update_python_with_ai(name = "calc_impl")\n')

            pyi_file = os.path.join(part_dir, "low/calc_impl.pyi")
            with open(pyi_file, "w", encoding="utf-8") as f:
                f.write("""class Calculator:
    def add(self, a: int, b: int) -> int: ...
""")

            real_lib_file = os.path.join(part_dir, "lib/calc_impl.py")
            with open(real_lib_file, "w", encoding="utf-8") as f:
                f.write("""class Calculator:
    def add(self, a: int, b: int) -> int:
        # SUPER SECRET REAL IMPLEMENTATION
        return a + b
""")
            ts = "2026-10-05T12:00:00Z"
            src_metadata.update_metadata(pyi_file, last_cleaned=ts, last_changed=ts)
            src_metadata.update_metadata(
                real_lib_file, last_cleaned=ts, last_changed=ts
            )

            # Commission test role workspace
            test_ws = cleanroom_workspace_tool.commission_workspace(
                "test", dir_scope="staging", repo_root=main_repo
            )
            ws_stub_file = os.path.join(test_ws, "staging/parts/calc/lib/calc_impl.py")

            # 1. Verify stub was generated and does NOT contain real implementation
            self.assertTrue(os.path.isfile(ws_stub_file))
            with open(ws_stub_file, "r", encoding="utf-8") as f:
                stub_content = f.read()
            self.assertIn("CLEANROOM TEST STUB", stub_content)
            self.assertIn("raise NotImplementedError", stub_content)
            self.assertNotIn("SUPER SECRET REAL IMPLEMENTATION", stub_content)
            st = os.stat(ws_stub_file)
            self.assertEqual(st.st_mode & stat.S_IWUSR, 0)  # Read-only (chmod 444)

            # 2. Main updates real implementation with newer event timestamp
            ts2 = "2026-10-05T13:00:00Z"
            src_metadata.update_metadata(
                real_lib_file,
                last_cleaned=ts2,
                last_changed=ts2,
                change_summary="Optimized add",
            )

            # 3. Test agent calls get_work (pull_workspace_from_main)
            cleanroom_workspace_tool.pull_workspace_from_main(
                test_ws, main_repo, "test", dir_scope="staging"
            )

            # Verify it STILL does not leak real implementation!
            with open(ws_stub_file, "r", encoding="utf-8") as f:
                stub_after_pull = f.read()
            self.assertIn("CLEANROOM TEST STUB", stub_after_pull)
            self.assertNotIn("SUPER SECRET REAL IMPLEMENTATION", stub_after_pull)

            # 4. Host runs full cascade (converge_role_workspace)
            cleanroom_workspace_tool.converge_role_workspace(
                test_ws, main_repo, "test", parts_dirs=["staging"], phase="both"
            )

            # Verify cascade does NOT overwrite stub with real implementation
            with open(ws_stub_file, "r", encoding="utf-8") as f:
                stub_after_cascade = f.read()
            self.assertIn("CLEANROOM TEST STUB", stub_after_cascade)
            self.assertNotIn("SUPER SECRET REAL IMPLEMENTATION", stub_after_cascade)

            # 5. Even if an agent accidentally/maliciously copied real implementation into ws_stub_file,
            # pull_workspace_from_main must detect the missing CLEANROOM TEST STUB header and restore the stub!
            os.chmod(ws_stub_file, 0o644)
            with open(ws_stub_file, "w", encoding="utf-8") as f:
                f.write("class LeakedCalculator: pass\n")

            cleanroom_workspace_tool.pull_workspace_from_main(
                test_ws, main_repo, "test", dir_scope="staging"
            )
            with open(ws_stub_file, "r", encoding="utf-8") as f:
                restored_stub = f.read()
            self.assertIn("CLEANROOM TEST STUB", restored_stub)
            self.assertNotIn("LeakedCalculator", restored_stub)


if __name__ == "__main__":
    unittest.main()
