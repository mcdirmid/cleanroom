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
for _p in [_repo_root, os.path.join(_repo_root, "update_python_with_ai"), os.path.join(_repo_root, "update_with_ai"), os.path.join(_repo_root, "update_with_ai/support/lib")]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from update_with_ai.support.lib import cleanroom_mailbox
from update_with_ai.support.lib import cleanroom_workspace_tool


class CleanroomWorkspaceToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        # Restore write permissions on any read-only files so cleanup succeeds
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

    def test_mailbox_atomic_lifecycle(self) -> None:
        """Tests submit, blame, fail, and atomic read_and_clear in mailbox."""
        mb_dir = os.path.join(self.test_dir, "mailbox")
        os.makedirs(mb_dir, exist_ok=True)

        # 1. Submit
        cleanroom_mailbox.submit("update_with_ai/parts/core/lib/test_impl.py", "Added feature", mailbox_dir=mb_dir)

        # 2. Blame
        cleanroom_mailbox.blame("update_with_ai/parts/core/tests/test_test.py", "update_with_ai/parts/core/lib/test_impl.py", "Contract mismatch", mailbox_dir=mb_dir)

        # 3. Fail
        cleanroom_mailbox.fail("update_with_ai/parts/core/lib/test_impl.py", "Unsolvable dependency", mailbox_dir=mb_dir)

        # 4. Read and clear
        entries = cleanroom_mailbox.read_and_clear(mb_dir)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["type"], "SUBMIT")
        self.assertEqual(entries[0]["target"], "update_with_ai/parts/core/lib/test_impl.py")
        self.assertEqual(entries[0]["change"], "Added feature")

        self.assertEqual(entries[1]["type"], "BLAME")
        self.assertEqual(entries[1]["target"], "update_with_ai/parts/core/tests/test_test.py")
        self.assertEqual(entries[1]["blame_target"], "update_with_ai/parts/core/lib/test_impl.py")

        self.assertEqual(entries[2]["type"], "FAIL")
        self.assertEqual(entries[2]["reason"], "Unsolvable dependency")

        # 5. Subsequent read should be empty
        subsequent = cleanroom_mailbox.read_and_clear(mb_dir)
        self.assertEqual(len(subsequent), 0)

    def test_setup_lib_workspace_permissions_and_structure(self) -> None:
        """Verifies setup of a Lib role workspace: lib is writable, grounding/BUILD are read-only."""
        lib_ws = os.path.join(self.test_dir, "lib_ws")
        cleanroom_workspace_tool.setup_workspace("lib", dest=lib_ws)

        # AGENTS.md exists
        agents_md = os.path.join(lib_ws, "AGENTS.md")
        self.assertTrue(os.path.exists(agents_md))
        with open(agents_md, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Lib Engineer", content)
        self.assertTrue("CRITICAL" in content or "Mandatory Behavioral Constraints" in content)
        self.assertIn("The user may also ask you to align units directly", content)
        self.assertIn("<parts-dir>/parts/lib", content)

        # Mailbox files exist
        self.assertTrue(os.path.exists(os.path.join(lib_ws, "WORK_ORDER.md")))
        self.assertTrue(os.path.exists(os.path.join(lib_ws, "COMPLETED.md")))

        # Helper scripts
        self.assertTrue(os.path.exists(os.path.join(lib_ws, "bin/submit")))
        self.assertTrue(os.path.exists(os.path.join(lib_ws, "bin/fail")))
        # Lib cannot blame!
        self.assertFalse(os.path.exists(os.path.join(lib_ws, "bin/blame")))

        # Check permissions on grounding vs lib files
        pyi_path = os.path.join(lib_ws, "update_with_ai/parts/core/grounding/file_paths_impl.pyi")
        if os.path.exists(pyi_path):
            st = os.stat(pyi_path)
            self.assertEqual(st.st_mode & stat.S_IWUSR, 0, "Grounding pyi must be read-only")

        lib_py = os.path.join(lib_ws, "update_with_ai/parts/core/lib/file_paths_impl.py")
        if os.path.exists(lib_py):
            st = os.stat(lib_py)
            self.assertNotEqual(st.st_mode & stat.S_IWUSR, 0, "Lib file must be read-write")

        # Tests directory should not exist in lib workspace (double-blind separation)
        tests_dir = os.path.join(lib_ws, "update_with_ai/parts/core/tests")
        self.assertFalse(os.path.exists(tests_dir), "tests/ must be completely excluded from lib workspace")

    def test_setup_test_workspace_stubs_and_permissions(self) -> None:
        """Verifies setup of a Test role workspace: tests writable, lib has read-only stubs."""
        test_ws = os.path.join(self.test_dir, "test_ws")
        cleanroom_workspace_tool.setup_workspace("test", dest=test_ws)

        # Helper scripts: test can blame
        self.assertTrue(os.path.exists(os.path.join(test_ws, "bin/blame")))

        # Tests file should be writable
        test_py = os.path.join(test_ws, "update_with_ai/parts/core/tests/file_paths_impl_test.py")
        if os.path.exists(test_py):
            st = os.stat(test_py)
            self.assertNotEqual(st.st_mode & stat.S_IWUSR, 0, "Test file must be read-write")

        # Test direct stub generation on a sample pyi contract
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
        cleanroom_workspace_tool.generate_readonly_test_stub(synthetic_pyi, "sample_impl", synthetic_stub)
        self.assertTrue(os.path.exists(synthetic_stub))
        st = os.stat(synthetic_stub)
        self.assertEqual(st.st_mode & stat.S_IWUSR, 0, "Test stub must be read-only")
        with open(synthetic_stub, "r", encoding="utf-8") as f:
            stub_content = f.read()
        self.assertIn("CLEANROOM TEST STUB", stub_content)
        self.assertIn("raise NotImplementedError", stub_content)
        self.assertIn("def __init__(self)", stub_content)

    def test_tamper_detection(self) -> None:
        """Verifies that modifying a read-only file triggers PermissionError on sync."""
        lib_ws = os.path.join(self.test_dir, "tamper_ws")
        cleanroom_workspace_tool.setup_workspace("lib", dest=lib_ws)

        # Tamper with a read-only contract
        pyi_path = os.path.join(lib_ws, "update_with_ai/parts/core/grounding/file_paths_impl.pyi")
        if os.path.exists(pyi_path):
            os.chmod(pyi_path, 0o644)
            with open(pyi_path, "a", encoding="utf-8") as f:
                f.write("\n# rogue edit\n")
            os.chmod(pyi_path, 0o444)

            with self.assertRaises(PermissionError):
                cleanroom_workspace_tool.sync_workspace("lib", dest=lib_ws)

    def test_textproto_load_and_save(self) -> None:
        """Verifies parsing and serialization of .update_with_ai.textproto files."""
        tp_path = os.path.join(self.test_dir, ".update_with_ai.textproto")
        records = {
            "//update_with_ai/parts/core:filesystem_ext#//update_python_with_ai:low": {
                "messages": [
                    {"kind": "change", "content": "Updated contract", "sender": "//upstream:spec"}
                ],
                "reverse_dependencies": ["//update_with_ai/parts/core:filesystem_ext#//update_python_with_ai:lib"],
            }
        }
        self.assertTrue(cleanroom_workspace_tool.save_package_textproto(tp_path, records))
        loaded = cleanroom_workspace_tool.load_package_textproto(tp_path)
        self.assertEqual(len(loaded), 1)
        node_id = "//update_with_ai/parts/core:filesystem_ext#//update_python_with_ai:low"
        self.assertIn(node_id, loaded)
        self.assertEqual(len(loaded[node_id]["messages"]), 1)
        self.assertEqual(loaded[node_id]["messages"][0]["kind"], "change")
        self.assertEqual(loaded[node_id]["messages"][0]["content"], "Updated contract")
        self.assertEqual(loaded[node_id]["messages"][0]["sender"], "//upstream:spec")
        self.assertEqual(loaded[node_id]["reverse_dependencies"], ["//update_with_ai/parts/core:filesystem_ext#//update_python_with_ai:lib"])

    def test_phase_ordering(self) -> None:
        """Verifies Cleanroom phase ordering: requirements -> grounding -> lib/test -> qa."""
        nodes = [
            {"pkg": "pkg1", "unit_name": "mod1", "role": "qa"},
            {"pkg": "pkg1", "unit_name": "mod1", "role": "lib"},
            {"pkg": "pkg1", "unit_name": "mod1", "role": "test"},
            {"pkg": "pkg1", "unit_name": "mod1", "role": "grounding"},
        ]
        # When grounding is dirty, only grounding is ready
        ready = cleanroom_workspace_tool.get_ready_dirty_nodes(nodes)
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0]["role"], "grounding")

        # Once grounding is clean, both lib and test are ready concurrently
        nodes_no_grounding = [
            {"pkg": "pkg1", "unit_name": "mod1", "role": "qa"},
            {"pkg": "pkg1", "unit_name": "mod1", "role": "lib"},
            {"pkg": "pkg1", "unit_name": "mod1", "role": "test"},
        ]
        ready2 = cleanroom_workspace_tool.get_ready_dirty_nodes(nodes_no_grounding)
        self.assertEqual(len(ready2), 2)
        roles2 = {n["role"] for n in ready2}
        self.assertEqual(roles2, {"lib", "test"})

        # Once lib and test are clean, qa is ready
        nodes_qa = [{"pkg": "pkg1", "unit_name": "mod1", "role": "qa"}]
        ready3 = cleanroom_workspace_tool.get_ready_dirty_nodes(nodes_qa)
        self.assertEqual(len(ready3), 1)
        self.assertEqual(ready3[0]["role"], "qa")

    def test_textproto_dispatch_and_sync_lifecycle(self) -> None:
        """Verifies complete dispatch, work order generation, submission, sync, and message clearing."""
        fake_repo = os.path.join(self.test_dir, "fake_repo")
        pkg_dir = os.path.join(fake_repo, "update_with_ai/parts/sandbox")
        os.makedirs(os.path.join(pkg_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(pkg_dir, "grounding"), exist_ok=True)

        # 1. Setup .update_with_ai.textproto with a dirty lib node
        tp_path = os.path.join(pkg_dir, ".update_with_ai.textproto")
        lib_node = "//update_with_ai/parts/sandbox:tool_provider#//update_python_with_ai:lib"
        qa_node = "//update_with_ai/parts/sandbox:tool_provider#//update_python_with_ai:qa"
        records = {
            lib_node: {
                "messages": [
                    {
                        "kind": "change",
                        "content": "updated with new operation for checking read file access.",
                        "sender": "update_with_ai/parts/sandbox/grounding/tool_provider.pyi",
                    }
                ],
                "reverse_dependencies": [qa_node],
            },
            qa_node: {
                "messages": [],
                "reverse_dependencies": [],
            },
        }
        cleanroom_workspace_tool.save_package_textproto(tp_path, records)

        # Canonical file
        lib_file = os.path.join(pkg_dir, "lib/tool_provider.py")
        with open(lib_file, "w", encoding="utf-8") as f:
            f.write("# original lib\n")

        # 2. Dispatch to lib role workspace
        role_ws = os.path.join(self.test_dir, "cleanroom_lib_ws")
        res = cleanroom_workspace_tool.dispatch_dirty_work(
            role_filter="lib",
            dest=role_ws,
            repo_root=fake_repo,
        )
        self.assertEqual(res, 0)

        # Verify WORK_ORDER.md
        wo_path = os.path.join(role_ws, "WORK_ORDER.md")
        self.assertTrue(os.path.exists(wo_path))
        with open(wo_path, "r", encoding="utf-8") as f:
            wo_content = f.read()
        self.assertIn("CLEAN update_with_ai/parts/sandbox/lib/tool_provider.py", wo_content)
        self.assertIn("REASON: Change from update_with_ai/parts/sandbox/grounding/tool_provider.pyi: updated with new operation for checking read file access.", wo_content)

        # 3. Simulate role worker submission
        ws_lib_file = os.path.join(role_ws, "update_with_ai/parts/sandbox/lib/tool_provider.py")
        with open(ws_lib_file, "w", encoding="utf-8") as f:
            f.write("# updated lib with new check operation\n")
        cleanroom_mailbox.submit(
            "update_with_ai/parts/sandbox/lib/tool_provider.py",
            "added new methods to deal with checking read file access.",
            mailbox_dir=role_ws,
        )

        # 4. Sync workspace back to repo
        synced = cleanroom_workspace_tool.sync_workspace("lib", dest=role_ws, repo_root=fake_repo)
        self.assertEqual(len(synced), 1)

        # Verify file synced
        with open(lib_file, "r", encoding="utf-8") as f:
            synced_content = f.read()
        self.assertIn("# updated lib with new check operation", synced_content)

        # Verify messages cleared for lib node in .update_with_ai.textproto
        updated_data = cleanroom_workspace_tool.load_package_textproto(tp_path)
        self.assertEqual(len(updated_data[lib_node]["messages"]), 0, "Lib node messages must be cleared after sync")

        # Verify change message propagated to reverse dependency (qa node)
        qa_msgs = updated_data[qa_node]["messages"]
        self.assertEqual(len(qa_msgs), 1, "Reverse dependency must receive change notification")
        self.assertEqual(qa_msgs[0]["kind"], "change")
        self.assertIn("added new methods to deal with checking read file access", qa_msgs[0]["content"])

        # Verify WORK_ORDER.md updated
        with open(wo_path, "r", encoding="utf-8") as f:
            updated_wo = f.read()
        self.assertNotIn("CLEAN update_with_ai/parts/sandbox/lib/tool_provider.py", updated_wo)

    def test_blame_feedback_recording(self) -> None:
        """Verifies BLAME submissions record feedback messages in the blamed target's textproto."""
        fake_repo = os.path.join(self.test_dir, "fake_repo2")
        pkg_dir = os.path.join(fake_repo, "update_with_ai/parts/sandbox")
        os.makedirs(pkg_dir, exist_ok=True)

        tp_path = os.path.join(pkg_dir, ".update_with_ai.textproto")
        lib_node = "//update_with_ai/parts/sandbox:sandbox_cleanroom_impl#//update_python_with_ai:lib"
        cleanroom_workspace_tool.save_package_textproto(
            tp_path,
            {lib_node: {"messages": [], "reverse_dependencies": []}},
        )

        qa_ws = os.path.join(self.test_dir, "qa_ws")
        cleanroom_workspace_tool.setup_workspace("qa", dest=qa_ws, repo_root=fake_repo)

        # QA submits a BLAME on lib
        cleanroom_mailbox.blame(
            "update_with_ai/parts/sandbox/logs/sandbox_cleanroom_impl_qa.log",
            "update_with_ai/parts/sandbox/lib/sandbox_cleanroom_impl.py",
            "implemented read file access methods do not implement contract because ...",
            mailbox_dir=qa_ws,
        )

        # Sync QA workspace
        cleanroom_workspace_tool.sync_workspace("qa", dest=qa_ws, repo_root=fake_repo)

        # Check that blamed target received feedback message in textproto
        data = cleanroom_workspace_tool.load_package_textproto(tp_path)
        self.assertIn(lib_node, data)
        msgs = data[lib_node]["messages"]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["kind"], "feedback")
        self.assertIn("implemented read file access methods do not implement contract because ...", msgs[0]["content"])

    def test_parts_dir_isolation_in_setup(self) -> None:
        """Verifies that specifying a parts directory isolates workspace setup (e.g. staging vs update_with_ai)."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_parts")
        up_dir = os.path.join(fake_repo, "update_with_ai/parts/core/lib")
        staging_dir = os.path.join(fake_repo, "staging/parts/sandbox/lib")
        os.makedirs(up_dir, exist_ok=True)
        os.makedirs(staging_dir, exist_ok=True)

        with open(os.path.join(up_dir, "up_mod.py"), "w", encoding="utf-8") as f:
            f.write("# update_with_ai mod\n")
        with open(os.path.join(staging_dir, "test_mod.py"), "w", encoding="utf-8") as f:
            f.write("# staging mod\n")

        # 1. Setup workspace specifying ONLY 'staging'
        staging_ws = os.path.join(self.test_dir, "ws_staging_only")
        cleanroom_workspace_tool.setup_workspace("lib", dest=staging_ws, repo_root=fake_repo, parts_dirs=["staging"])

        # Must contain staging parts
        self.assertTrue(os.path.exists(os.path.join(staging_ws, "staging/parts/sandbox/lib/test_mod.py")))
        # Must NOT contain update_with_ai parts
        self.assertFalse(os.path.exists(os.path.join(staging_ws, "update_with_ai/parts/core/lib/up_mod.py")))
        self.assertFalse(os.path.exists(os.path.join(staging_ws, "update_with_ai/parts")))

        # 2. Setup workspace specifying ONLY 'update_with_ai'
        update_ws = os.path.join(self.test_dir, "ws_update_only")
        cleanroom_workspace_tool.setup_workspace("lib", dest=update_ws, repo_root=fake_repo, parts_dirs=["update_with_ai"])

        # Must contain update_with_ai parts
        self.assertTrue(os.path.exists(os.path.join(update_ws, "update_with_ai/parts/core/lib/up_mod.py")))
        # Must NOT contain staging parts
        self.assertFalse(os.path.exists(os.path.join(update_ws, "staging/parts/sandbox/lib/test_mod.py")))
        self.assertFalse(os.path.exists(os.path.join(update_ws, "staging/parts")))

    def test_parts_dir_in_dispatch(self) -> None:
        """Verifies dispatch filters dirty nodes and provisions workspaces according to parts_dirs."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_dispatch_parts")
        up_dir = os.path.join(fake_repo, "update_with_ai/parts/core")
        test_dir = os.path.join(fake_repo, "staging/parts/sandbox")
        os.makedirs(os.path.join(up_dir, "lib"), exist_ok=True)
        os.makedirs(os.path.join(test_dir, "lib"), exist_ok=True)

        with open(os.path.join(up_dir, "lib/up_mod.py"), "w", encoding="utf-8") as f:
            f.write("# up mod\n")
        with open(os.path.join(test_dir, "lib/test_mod.py"), "w", encoding="utf-8") as f:
            f.write("# test mod\n")

        # Dirty node in update_with_ai
        cleanroom_workspace_tool.save_package_textproto(
            os.path.join(up_dir, ".update_with_ai.textproto"),
            {"//update_with_ai/parts/core:up_mod#//update_python_with_ai:lib": {
                "messages": [{"kind": "change", "content": "Update core"}],
                "reverse_dependencies": [],
            }},
        )
        # Dirty node in staging
        cleanroom_workspace_tool.save_package_textproto(
            os.path.join(test_dir, ".update_with_ai.textproto"),
            {"//staging/parts/sandbox:test_mod#//update_python_with_ai:lib": {
                "messages": [{"kind": "change", "content": "Update sandbox"}],
                "reverse_dependencies": [],
            }},
        )

        # Dispatch with parts_dirs=["staging"]
        staging_ws = os.path.join(self.test_dir, "ws_dispatch_staging")
        res = cleanroom_workspace_tool.dispatch_dirty_work(
            parts_dirs=["staging"],
            dest=staging_ws,
            repo_root=fake_repo,
        )
        self.assertEqual(res, 0)

        # WORK_ORDER.md should contain staging/parts/sandbox/lib/test_mod.py
        wo_path = os.path.join(staging_ws, "WORK_ORDER.md")
        with open(wo_path, "r", encoding="utf-8") as f:
            wo_content = f.read()
        self.assertIn("CLEAN staging/parts/sandbox/lib/test_mod.py", wo_content)
        self.assertNotIn("CLEAN update_with_ai/parts/core/lib/up_mod.py", wo_content)
        # update_with_ai parts must NOT be in workspace
        self.assertFalse(os.path.exists(os.path.join(staging_ws, "update_with_ai/parts")))

    def test_high_role_workspace_setup(self) -> None:
        """Tests that setup with role //update_python_with_ai:high copies high/ and HLS linter, excluding downstream."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_high")
        test_part = os.path.join(fake_repo, "staging/parts/sandbox")
        os.makedirs(os.path.join(test_part, "high"), exist_ok=True)
        os.makedirs(os.path.join(test_part, "requirements"), exist_ok=True)
        os.makedirs(os.path.join(test_part, "grounding"), exist_ok=True)
        os.makedirs(os.path.join(test_part, "lib"), exist_ok=True)
        os.makedirs(os.path.join(test_part, "tests"), exist_ok=True)

        with open(os.path.join(test_part, "high/sample.md"), "w") as f:
            f.write("# sample\n\n## Purpose\nSample spec.\n")
        with open(os.path.join(test_part, "requirements/sample.md"), "w") as f:
            f.write("# sample requirements\n")
        with open(os.path.join(test_part, "grounding/sample.pyi"), "w") as f:
            f.write("class Sample: pass\n")
        with open(os.path.join(test_part, "lib/sample.py"), "w") as f:
            f.write("class Sample: pass\n")
        with open(os.path.join(test_part, "tests/sample_test.py"), "w") as f:
            f.write("def test_sample(): pass\n")

        # Setup with target label //update_python_with_ai:high
        high_ws = os.path.join(self.test_dir, "high_ws")
        cleanroom_workspace_tool.setup_workspace(
            role="//update_python_with_ai:high",
            dest=high_ws,
            repo_root=fake_repo,
            parts_dirs=["staging"],
        )

        # 1. High spec is present and writable
        h_file = os.path.join(high_ws, "staging/parts/sandbox/high/sample.md")
        self.assertTrue(os.path.exists(h_file))
        st = os.stat(h_file)
        self.assertTrue(bool(st.st_mode & stat.S_IWUSR))

        # 2. Downstream requirements, grounding, lib, and tests are excluded
        self.assertFalse(os.path.exists(os.path.join(high_ws, "staging/parts/sandbox/requirements")))
        self.assertFalse(os.path.exists(os.path.join(high_ws, "staging/parts/sandbox/grounding")))
        self.assertFalse(os.path.exists(os.path.join(high_ws, "staging/parts/sandbox/lib")))
        self.assertFalse(os.path.exists(os.path.join(high_ws, "staging/parts/sandbox/tests")))

        # 3. Bazel scaffolding is excluded (not declared in workspace_files)
        self.assertFalse(os.path.exists(os.path.join(high_ws, "MODULE.bazel")))
        self.assertFalse(os.path.exists(os.path.join(high_ws, ".bazelversion")))
        self.assertFalse(os.path.exists(os.path.join(high_ws, "bin/pyright_library.bzl")))

        # 4. High linter and guide are present
        self.assertTrue(os.path.exists(os.path.join(high_ws, "update_python_with_ai/support/lib/high_lint.py")))
        self.assertTrue(os.path.exists(os.path.join(high_ws, "update_python_with_ai/guides/high_level_spec.md")))

        # 5. AGENTS.md references HLS persona, guide, and high_lint.py
        with open(os.path.join(high_ws, "AGENTS.md"), "r", encoding="utf-8") as f:
            agents_md = f.read()
        self.assertIn("High-Level Spec Engineer", agents_md)
        self.assertIn("//update_python_with_ai:high", agents_md)
        self.assertIn("high_lint.py", agents_md)

    def test_planning_role_workspace_setup(self) -> None:
        """Tests that planning setup copies upstream high/ as read-only, planning/ as writable."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_plan")
        test_part = os.path.join(fake_repo, "staging/parts/sandbox")
        os.makedirs(os.path.join(test_part, "high"), exist_ok=True)
        os.makedirs(os.path.join(test_part, "planning"), exist_ok=True)
        os.makedirs(os.path.join(test_part, "grounding"), exist_ok=True)

        with open(os.path.join(test_part, "high/sample.md"), "w") as f:
            f.write("# sample HLS\n")
        with open(os.path.join(test_part, "planning/sample.md"), "w") as f:
            f.write("# sample planning\n")
        with open(os.path.join(test_part, "grounding/sample.pyi"), "w") as f:
            f.write("class Sample: pass\n")

        plan_ws = os.path.join(self.test_dir, "plan_ws")
        cleanroom_workspace_tool.setup_workspace(
            role="//update_python_with_ai:planning",
            dest=plan_ws,
            repo_root=fake_repo,
            parts_dirs=["staging"],
        )

        # 1. Planning is writable
        p_file = os.path.join(plan_ws, "staging/parts/sandbox/planning/sample.md")
        self.assertTrue(os.path.exists(p_file))
        st_p = os.stat(p_file)
        self.assertTrue(bool(st_p.st_mode & stat.S_IWUSR))

        # 2. Upstream high is read-only
        h_file = os.path.join(plan_ws, "staging/parts/sandbox/high/sample.md")
        self.assertTrue(os.path.exists(h_file))
        st_h = os.stat(h_file)
        self.assertFalse(bool(st_h.st_mode & stat.S_IWUSR))

        # 3. Downstream grounding is excluded
        self.assertFalse(os.path.exists(os.path.join(plan_ws, "staging/parts/sandbox/grounding")))

        # 4. Tool is present
        self.assertTrue(os.path.exists(os.path.join(plan_ws, "update_with_ai/support/lib/build_lint_common.py")))

        # 5. Bazel scaffolding is excluded
        self.assertFalse(os.path.exists(os.path.join(plan_ws, "MODULE.bazel")))

        # 6. feedback_role_deps is non-empty -> bin/blame IS present
        self.assertTrue(os.path.exists(os.path.join(plan_ws, "bin/blame")))

    def test_grounding_role_workspace_setup(self) -> None:
        """Tests that grounding setup copies low as read-only, grounding as writable, and provisions bin/blame."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_grounding")
        test_part = os.path.join(fake_repo, "staging/parts/sandbox")
        os.makedirs(os.path.join(test_part, "low"), exist_ok=True)
        os.makedirs(os.path.join(test_part, "grounding"), exist_ok=True)
        os.makedirs(os.path.join(test_part, "lib"), exist_ok=True)

        with open(os.path.join(test_part, "low/sample.pyi"), "w") as f:
            f.write("class Sample: pass\n")
        with open(os.path.join(test_part, "grounding/sample.py"), "w") as f:
            f.write("# sample Grounding Python\n")
        with open(os.path.join(test_part, "grounding/sample.gt"), "w") as f:
            f.write("# sample Groundtalk\n")
        with open(os.path.join(test_part, "lib/sample.py"), "w") as f:
            f.write("class Sample: pass\n")

        g_ws = os.path.join(self.test_dir, "grounding_ws")
        cleanroom_workspace_tool.setup_workspace(
            role="//update_python_with_ai:grounding",
            dest=g_ws,
            repo_root=fake_repo,
            parts_dirs=["staging"],
        )

        # 1. Grounding is writable (.py)
        g_file = os.path.join(g_ws, "staging/parts/sandbox/grounding/sample.py")
        self.assertTrue(os.path.exists(g_file))
        st_g = os.stat(g_file)
        self.assertTrue(bool(st_g.st_mode & stat.S_IWUSR))

        # 2. Upstream low is read-only
        low_file = os.path.join(g_ws, "staging/parts/sandbox/low/sample.pyi")
        self.assertTrue(os.path.exists(low_file))
        st_low = os.stat(low_file)
        self.assertFalse(bool(st_low.st_mode & stat.S_IWUSR))

        # 3. Downstream lib is excluded
        self.assertFalse(os.path.exists(os.path.join(g_ws, "staging/parts/sandbox/lib")))

        # 4. feedback_role_deps is non-empty -> bin/blame IS present
        self.assertTrue(os.path.exists(os.path.join(g_ws, "bin/blame")))

    def test_qa_role_workspace_setup(self) -> None:
        """Tests that QA setup copies grounding, lib, and tests as read-only, has Bazel scaffolding, and can blame."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_qa")
        os.makedirs(fake_repo, exist_ok=True)
        with open(os.path.join(fake_repo, "MODULE.bazel"), "w") as f:
            f.write("# mock module.bazel\n")
        test_part = os.path.join(fake_repo, "staging/parts/sandbox")
        os.makedirs(os.path.join(test_part, "low"), exist_ok=True)
        os.makedirs(os.path.join(test_part, "grounding"), exist_ok=True)
        os.makedirs(os.path.join(test_part, "lib"), exist_ok=True)
        os.makedirs(os.path.join(test_part, "tests"), exist_ok=True)

        with open(os.path.join(test_part, "low/sample.pyi"), "w") as f:
            f.write("class Sample: pass\n")
        with open(os.path.join(test_part, "grounding/sample.py"), "w") as f:
            f.write("# sample Grounding Python\n")
        with open(os.path.join(test_part, "lib/sample.py"), "w") as f:
            f.write("class Sample: pass\n")
        with open(os.path.join(test_part, "tests/sample_test.py"), "w") as f:
            f.write("def test_sample(): pass\n")

        qa_ws = os.path.join(self.test_dir, "qa_full_ws")
        cleanroom_workspace_tool.setup_workspace(
            role="//update_python_with_ai:qa",
            dest=qa_ws,
            repo_root=fake_repo,
            parts_dirs=["staging"],
        )

        # 1. All code files are read-only
        for sub, fname in [("low", "sample.pyi"), ("grounding", "sample.py"), ("lib", "sample.py"), ("tests", "sample_test.py")]:
            f_path = os.path.join(qa_ws, "staging/parts/sandbox", sub, fname)
            self.assertTrue(os.path.exists(f_path), f"Expected {sub}/{fname} to exist")
            st = os.stat(f_path)
            self.assertFalse(bool(st.st_mode & stat.S_IWUSR), f"Expected {sub}/{fname} to be read-only")

        # 2. Bazel scaffolding is present (declared in workspace_files)
        self.assertTrue(os.path.exists(os.path.join(qa_ws, "MODULE.bazel")))

        # 3. QA can blame
        self.assertTrue(os.path.exists(os.path.join(qa_ws, "bin/blame")))

        # 4. AGENTS.md specifies Strict Read-Only Mode
        with open(os.path.join(qa_ws, "AGENTS.md"), "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Strict Read-Only Mode", content)

    def test_sync_out_of_band_changes(self) -> None:
        """Verifies that out-of-band changes to read-write files in role workspace are synced back to canonical repo."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_oob")
        pkg_dir = os.path.join(fake_repo, "update_with_ai/parts/core")
        os.makedirs(os.path.join(pkg_dir, "high"), exist_ok=True)

        # 1. Canonical file & textproto
        high_file = os.path.join(pkg_dir, "high/my_spec.md")
        with open(high_file, "w", encoding="utf-8") as f:
            f.write("# original high spec\n")

        tp_path = os.path.join(pkg_dir, ".update_with_ai.textproto")
        high_node = "//update_with_ai/parts/core:my_spec#//update_python_with_ai:high"
        grounding_node = "//update_with_ai/parts/core:my_spec#//update_python_with_ai:grounding"
        cleanroom_workspace_tool.save_package_textproto(
            tp_path,
            {
                high_node: {
                    "messages": [{"kind": "change", "content": "Initial dirty message"}],
                    "reverse_dependencies": [grounding_node],
                },
                grounding_node: {
                    "messages": [],
                    "reverse_dependencies": [],
                },
            },
        )

        # 2. Setup high role workspace
        high_ws = os.path.join(self.test_dir, "ws_high_oob")
        cleanroom_workspace_tool.setup_workspace("high", dest=high_ws, repo_root=fake_repo)

        # 3. Simulate out-of-band edit (no bin/submit, COMPLETED.md stays empty)
        ws_high_file = os.path.join(high_ws, "update_with_ai/parts/core/high/my_spec.md")
        with open(ws_high_file, "w", encoding="utf-8") as f:
            f.write("# modified high spec out of band\n")

        # 4. Sync workspace with default submitted mode (sync_all=False) -> should NOT sync unsubmitted files
        submitted_synced = cleanroom_workspace_tool.sync_workspace("high", dest=high_ws, repo_root=fake_repo, sync_all=False)
        self.assertEqual(len(submitted_synced), 0)

        # Canonical file should still have original content
        with open(high_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "# original high spec\n")

        # 5. Sync workspace with all read-write files mode (sync_all=True / --all) -> should sync file by edit time
        synced = cleanroom_workspace_tool.sync_workspace("high", dest=high_ws, repo_root=fake_repo, sync_all=True)
        self.assertEqual(len(synced), 1)
        self.assertEqual(synced[0]["target"], "update_with_ai/parts/core/high/my_spec.md")

        # Verify file synced in canonical repo
        with open(high_file, "r", encoding="utf-8") as f:
            canonical_content = f.read()
        self.assertIn("# modified high spec out of band", canonical_content)

        # 6. In --all mode, .update_with_ai.textproto is NOT touched
        data_after_all = cleanroom_workspace_tool.load_package_textproto(tp_path)
        self.assertEqual(len(data_after_all[high_node]["messages"]), 1)
        self.assertEqual(len(data_after_all[grounding_node]["messages"]), 0)

        # 7. Now submit via mailbox and sync without --all -> updates textproto
        cleanroom_mailbox.submit("update_with_ai/parts/core/high/my_spec.md", "Finalized spec", mailbox_dir=high_ws)
        submit_synced = cleanroom_workspace_tool.sync_workspace("high", dest=high_ws, repo_root=fake_repo, sync_all=False)
        self.assertEqual(len(submit_synced), 1)

        updated_data = cleanroom_workspace_tool.load_package_textproto(tp_path)
        self.assertEqual(len(updated_data[high_node]["messages"]), 0)
        self.assertEqual(len(updated_data[grounding_node]["messages"]), 1)
        self.assertIn("Finalized spec", updated_data[grounding_node]["messages"][0]["content"])

        # 8. Running sync again without further changes produces nothing
        subsequent = cleanroom_workspace_tool.sync_workspace("high", dest=high_ws, repo_root=fake_repo, sync_all=True)
        self.assertEqual(len(subsequent), 0)

    def test_cleanroom_sync_lifecycle(self) -> None:
        """Tests unified cleanroom_sync with --role: auto-creates workspace and populates WORK_ORDER.md."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_sync")
        pkg_dir = os.path.join(fake_repo, "staging/parts/sandbox")
        os.makedirs(os.path.join(pkg_dir, "low"), exist_ok=True)

        low_file = os.path.join(pkg_dir, "low/sandbox_file_editor.pyi")
        with open(low_file, "w", encoding="utf-8") as f:
            f.write("# low spec\n")

        # Dirty low node in textproto
        tp_path = os.path.join(pkg_dir, ".update_with_ai.textproto")
        low_node = "//staging/parts/sandbox:sandbox_file_editor#//update_python_with_ai:low"
        cleanroom_workspace_tool.save_package_textproto(
            tp_path,
            {
                low_node: {
                    "messages": [{"kind": "change", "content": "check"}],
                    "reverse_dependencies": [],
                },
            },
        )

        role_dir = cleanroom_workspace_tool.get_default_role_dir("low", repo_root=fake_repo)
        self.assertEqual(role_dir, os.path.join(self.test_dir, "role_workspaces", "fake_repo_sync_low"))
        self.assertFalse(os.path.exists(role_dir))

        # Run cleanroom_sync without explicit dest (uses default role dir)
        ret = cleanroom_workspace_tool.cleanroom_sync(
            role="//update_python_with_ai:low",
            parts_dirs=["staging"],
            repo_root=fake_repo,
        )
        self.assertEqual(ret, 0)
        self.assertTrue(os.path.exists(role_dir))

        # Check metadata
        meta = cleanroom_workspace_tool.load_role_metadata(role_dir)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["role_name"], "low")

        # Check WORK_ORDER.md populated
        wo_path = os.path.join(role_dir, "WORK_ORDER.md")
        self.assertTrue(os.path.exists(wo_path))
        with open(wo_path, "r", encoding="utf-8") as f:
            wo_content = f.read()
        self.assertIn("CLEAN staging/parts/sandbox/low/sandbox_file_editor.pyi", wo_content)
        self.assertIn("REASON: Change: check", wo_content)

    def test_cleanroom_sync_all_existing_workspaces(self) -> None:
        """Tests that cleanroom_sync without role syncs all existing role workspaces found via metadata."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_multi")
        pkg_dir = os.path.join(fake_repo, "staging/parts/sandbox")
        os.makedirs(os.path.join(pkg_dir, "low"), exist_ok=True)
        os.makedirs(os.path.join(pkg_dir, "grounding"), exist_ok=True)

        low_file = os.path.join(pkg_dir, "low/sample.pyi")
        with open(low_file, "w") as f:
            f.write("# initial low\n")
        gt_file = os.path.join(pkg_dir, "grounding/sample.gt")
        with open(gt_file, "w") as f:
            f.write("# initial gt\n")

        # Set up two role workspaces in default workspaces container
        ws_low = cleanroom_workspace_tool.setup_workspace("//update_python_with_ai:low", repo_root=fake_repo, parts_dirs=["staging"])
        ws_grounding = cleanroom_workspace_tool.setup_workspace("//update_python_with_ai:grounding", repo_root=fake_repo, parts_dirs=["staging"])
        self.assertEqual(ws_low, os.path.join(self.test_dir, "role_workspaces", "fake_repo_multi_low"))
        self.assertEqual(ws_grounding, os.path.join(self.test_dir, "role_workspaces", "fake_repo_multi_grounding"))

        # Submit change from low workspace
        cleanroom_mailbox.submit("staging/parts/sandbox/low/sample.pyi", "Updated low spec", mailbox_dir=ws_low)

        # Run cleanroom_sync without role
        ret = cleanroom_workspace_tool.cleanroom_sync(role=None, repo_root=fake_repo)
        self.assertEqual(ret, 0)

        # Submitted file should have been synced to canonical repo
        self.assertTrue(os.path.exists(low_file))

    def test_find_existing_role_workspaces_new_and_legacy(self) -> None:
        """Tests that find_existing_role_workspaces finds both new role_workspaces/<repo>_<role> and legacy <repo>_workspaces/<role>."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_discovery")
        os.makedirs(fake_repo, exist_ok=True)

        # 1. Create a workspace in new location: role_workspaces/fake_repo_discovery_low
        new_ws = os.path.join(self.test_dir, "role_workspaces", "fake_repo_discovery_low")
        os.makedirs(new_ws, exist_ok=True)
        cleanroom_workspace_tool.save_role_metadata(new_ws, "//update_python_with_ai:low", "low", ["staging"])

        # 2. Create a workspace in legacy location: fake_repo_discovery_workspaces/test
        legacy_ws = os.path.join(self.test_dir, "fake_repo_discovery_workspaces", "test")
        os.makedirs(legacy_ws, exist_ok=True)
        cleanroom_workspace_tool.save_role_metadata(legacy_ws, "//update_python_with_ai:test", "test", ["staging"])

        found = cleanroom_workspace_tool.find_existing_role_workspaces(repo_root=fake_repo)
        found_dirs = [f[0] for f in found]
        self.assertIn(new_ws, found_dirs)
        self.assertIn(legacy_ws, found_dirs)

    def test_outbound_read_write_sync(self) -> None:
        """Tests that newer read-write files in canonical workspace are synced to role workspace."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_outbound")
        pkg_dir = os.path.join(fake_repo, "update_with_ai/parts/core/high")
        os.makedirs(pkg_dir, exist_ok=True)

        high_file = os.path.join(pkg_dir, "doc.md")
        with open(high_file, "w") as f:
            f.write("# version 1\n")

        high_ws = os.path.join(self.test_dir, "ws_high_outbound")
        cleanroom_workspace_tool.setup_workspace("high", dest=high_ws, repo_root=fake_repo)

        ws_file = os.path.join(high_ws, "update_with_ai/parts/core/high/doc.md")
        with open(ws_file, "r") as f:
            self.assertEqual(f.read(), "# version 1\n")

        # Update canonical repo file with later timestamp
        import time
        time.sleep(0.05)
        with open(high_file, "w") as f:
            f.write("# version 2 from workspace\n")

        # Converge workspace
        cleanroom_workspace_tool.converge_role_workspace(high_ws, fake_repo, "high")

        # Role workspace should receive updated file
        with open(ws_file, "r") as f:
            self.assertEqual(f.read(), "# version 2 from workspace\n")


    def test_lib_workspace_templates_and_build_update(self) -> None:
        """Verifies that lib workspace setup materializes missing templates and updates out-of-date lib/BUILD.bazel."""
        fake_repo = os.path.join(self.test_dir, "fake_lib_repo")
        part_dir = os.path.join(fake_repo, "update_with_ai/parts/my_feature")
        os.makedirs(os.path.join(part_dir, "grounding"), exist_ok=True)

        # 1. Author parent BUILD.bazel with update_python_with_ai
        with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write(
                'load("//update_python_with_ai/support/lib:update_python_with_ai.bzl", "update_python_with_ai")\n\n'
                'update_python_with_ai(\n'
                '    name = "feature_engine",\n'
                '    module_deps = [],\n'
                ')\n'
            )

        # 2. Author grounding spec .pyi
        with open(os.path.join(part_dir, "grounding/feature_engine.pyi"), "w", encoding="utf-8") as f:
            f.write(
                'from typing import Protocol\n\n'
                'class FeatureEngine(Protocol):\n'
                '    def process(self, data: str) -> bool: ...\n'
            )

        # Ensure lib/BUILD.bazel and lib/feature_engine.py do NOT exist initially
        self.assertFalse(os.path.exists(os.path.join(part_dir, "lib/feature_engine.py")))
        self.assertFalse(os.path.exists(os.path.join(part_dir, "lib/BUILD.bazel")))

        # 3. Setup lib workspace
        ws_lib = os.path.join(self.test_dir, "ws_lib_auto")
        cleanroom_workspace_tool.setup_workspace(
            role="lib",
            dest=ws_lib,
            repo_root=fake_repo,
            parts_dirs=["update_with_ai"],
        )

        # Canonical repo assertions: template materialized and BUILD.bazel generated
        repo_lib_py = os.path.join(part_dir, "lib/feature_engine.py")
        repo_lib_b = os.path.join(part_dir, "lib/BUILD.bazel")
        self.assertTrue(os.path.exists(repo_lib_py), "Empty/missing lib source file must be materialized with template")
        self.assertTrue(os.path.exists(repo_lib_b), "lib/BUILD.bazel must be generated directly from part BUILD.bazel")

        with open(repo_lib_py, "r", encoding="utf-8") as f:
            py_content = f.read()
        self.assertIn("class FeatureEngine", py_content)
        self.assertIn("def process(self", py_content)

        with open(repo_lib_b, "r", encoding="utf-8") as f:
            b_content = f.read()
        self.assertIn('name = "feature_engine"', b_content)

        # Workspace assertions: files copied with proper permissions
        ws_lib_py = os.path.join(ws_lib, "update_with_ai/parts/my_feature/lib/feature_engine.py")
        ws_lib_b = os.path.join(ws_lib, "update_with_ai/parts/my_feature/lib/BUILD.bazel")
        self.assertTrue(os.path.exists(ws_lib_py))
        self.assertTrue(os.path.exists(ws_lib_b))

        st_py = os.stat(ws_lib_py)
        self.assertNotEqual(st_py.st_mode & stat.S_IWUSR, 0, "Workspace lib source file must be writable")
        st_b = os.stat(ws_lib_b)
        self.assertEqual(st_b.st_mode & stat.S_IWUSR, 0, "Workspace BUILD file must be read-only")

        # 4. Out of date update test: add a second unit to parent BUILD.bazel
        with open(os.path.join(part_dir, "BUILD.bazel"), "a", encoding="utf-8") as f:
            f.write(
                '\nupdate_python_with_ai(\n'
                '    name = "feature_helper",\n'
                '    module_deps = [":feature_engine"],\n'
                ')\n'
            )
        with open(os.path.join(part_dir, "grounding/feature_helper.pyi"), "w", encoding="utf-8") as f:
            f.write(
                'class FeatureHelper:\n'
                '    def help_me(self) -> None: ...\n'
            )

        # Converge role workspace
        cleanroom_workspace_tool.converge_role_workspace(
            ws_lib,
            repo_root=fake_repo,
            role="lib",
            parts_dirs=["update_with_ai"],
        )

        # Both canonical and workspace BUILD files must now have feature_helper
        with open(repo_lib_b, "r", encoding="utf-8") as f:
            b_updated = f.read()
        self.assertIn('name = "feature_helper"', b_updated)
        self.assertIn(':feature_engine', b_updated)

        with open(ws_lib_b, "r", encoding="utf-8") as f:
            ws_b_updated = f.read()
        self.assertIn('name = "feature_helper"', ws_b_updated)

    def test_workspace_copies_node_deps_as_readonly(self) -> None:
        """Verifies that node_deps declared in define_role are copied to workspace as read-only files."""
        fake_repo = os.path.join(self.test_dir, "fake_repo_node_deps")
        pkg_dir = os.path.join(fake_repo, "update_python_with_ai/support/lib")
        os.makedirs(pkg_dir, exist_ok=True)
        with open(os.path.join(pkg_dir, "framework.pyi"), "w", encoding="utf-8") as f:
            f.write("# framework stubs\n")
        with open(os.path.join(pkg_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
            f.write('update_with_ai(name = "framework_spec", src = "framework.pyi")\n')

        role_def = {
            "name": "low",
            "pkg": "update_python_with_ai",
            "src_pattern": "{unit_dir}/low/{unit_name}.pyi",
            "node_deps": ["//update_python_with_ai/support/lib:framework_spec"],
            "workspace_files": [],
            "tools": [],
        }
        ws_dir = os.path.join(self.test_dir, "ws_low")
        os.makedirs(ws_dir, exist_ok=True)
        cleanroom_workspace_tool.copy_readonly_files_and_stubs(ws_dir, fake_repo, role_def, parts_bases=[])
        copied_file = os.path.join(ws_dir, "update_python_with_ai/support/lib/framework.pyi")
        self.assertTrue(os.path.isfile(copied_file))
        st = os.stat(copied_file)
        self.assertFalse(bool(st.st_mode & stat.S_IWUSR), "Expected framework.pyi to be read-only")


if __name__ == "__main__":
    unittest.main()


