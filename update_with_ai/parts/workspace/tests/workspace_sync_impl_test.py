# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:02Z
# LAST_CHANGED: 2026-10-09T02:39:58Z
# CHANGE: test contamination tripwire in refreshed AGENTS.md
# CODE_HASH: 75f1a65b33e5
# COVERAGE_AUDIT: 2026-10-09T21:19:02Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Unit tests for workspace_sync_impl."""

import json
import os
import stat
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.control.lib import src_metadata
from update_with_ai.parts.workspace.lib import (
    workspace_registry,
    workspace_sync,
    workspace_sync_impl,
)


class WorkspaceSyncImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = get_default_registry()
        self.ws_registry = workspace_registry._DefaultWorkspaceRegistry()
        self.registry.register_instance(
            self.ws_registry,
            keys=[
                workspace_registry.WorkspaceRegistry,
            ],
            tier=agent_session.agent_session,
        )
        self.src_meta = src_metadata._DefaultSourceMetadataCoordinator()
        self.registry.register_instance(
            self.src_meta,
            keys=[
                src_metadata.SourceMetadataCoordinator,
            ],
            tier=agent_session.agent_session,
        )
        self.synchronizer = workspace_sync_impl.WorkspaceSynchronizer()
        self.registry.register_instance(
            self.synchronizer,
            keys=[
                workspace_sync.WorkspaceSynchronizer,
                workspace_sync_impl.WorkspaceSynchronizer,
            ],
            tier=agent_session.agent_session,
        )
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.phase_cm.__enter__()

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_pull_and_harvest(self) -> None:
        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            # Set up main files
            main_lib = os.path.join(main_root, "scope", "lib")
            os.makedirs(main_lib, exist_ok=True)
            main_target = os.path.join(main_lib, "sample.py")
            with open(main_target, "w", encoding="utf-8") as f:
                f.write("# sample target\n")

            pulled = self.synchronizer.pull(
                workspace_dir=ws_dir,
                main_root=main_root,
                role_name="lib",
                dir_scope="scope",
            )
            self.assertEqual(pulled, 1)

            ws_target = os.path.join(ws_dir, "scope", "lib", "sample.py")
            self.assertTrue(os.path.isfile(ws_target))

            # Modify in workspace
            with open(ws_target, "w", encoding="utf-8") as f:
                f.write("# modified in workspace\n")

            res = self.synchronizer.harvest(
                workspace_dir=ws_dir,
                main_root=main_root,
                role_name="lib",
                dir_scope="scope",
            )
            self.assertEqual(res.harvested_files, 1)

            with open(main_target, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("modified in workspace", content)

    def test_flush_blame_buffer(self) -> None:
        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            culprit_dir = os.path.join(main_root, "scope", "low")
            os.makedirs(culprit_dir, exist_ok=True)
            culprit_file = os.path.join(culprit_dir, "sample.pyi")
            with open(culprit_file, "w", encoding="utf-8") as f:
                f.write('"""Sample contract."""\n')

            blame_buf = os.path.join(ws_dir, ".cleanroom_blame_buffer.json")
            with open(blame_buf, "w", encoding="utf-8") as f:
                json.dump(
                    [
                        {
                            "target": "scope/low/sample.pyi",
                            "explanation": "Type mismatch in return type",
                            "blamed_by": "lib",
                        }
                    ],
                    f,
                )

            flushed = self.synchronizer.flush_blame_buffer(ws_dir, main_root)
            self.assertEqual(len(flushed), 1)

            meta = src_metadata.extract_metadata(culprit_file)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertIsNotNone(meta.dirty)
            self.assertTrue(any("Type mismatch" in fb for fb in meta.feedback))

    def test_refresh_system_files_decoupled_from_bazel(self) -> None:
        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            # Set up files in main
            with open(os.path.join(main_root, "pyproject.toml"), "w", encoding="utf-8") as f:
                f.write("[project]\nname = 'test'\n")
            with open(os.path.join(main_root, "cleanroom_python_roles.toml"), "w", encoding="utf-8") as f:
                f.write(
                    "[methodology]\nname = 'python'\n\n"
                    "[roles.lib]\nname = 'lib'\nsrc_pattern = '{unit_dir}/lib/{unit_name}.py'\n"
                    "role_deps = ['low']\nstar_role_deps = ['low']\n"
                )
            with open(os.path.join(main_root, "MODULE.bazel"), "w", encoding="utf-8") as f:
                f.write("# legacy bazel module\n")
            with open(os.path.join(main_root, "pyrightconfig.json"), "w", encoding="utf-8") as f:
                f.write("{}\n")

            os.makedirs(os.path.join(ws_dir, "bin"), exist_ok=True)
            refreshed = self.synchronizer.refresh_system_files(
                workspace_dir=ws_dir,
                main_root=main_root,
                role_name="lib",
                dir_scope="scope",
            )
            self.assertGreater(refreshed, 0)
            self.assertTrue(os.path.isfile(os.path.join(ws_dir, "pyproject.toml")))
            self.assertTrue(os.path.isfile(os.path.join(ws_dir, "cleanroom_python_roles.toml")))
            self.assertFalse(os.path.exists(os.path.join(ws_dir, "MODULE.bazel")))
            self.assertFalse(os.path.exists(os.path.join(ws_dir, "pyrightconfig.json")))
            agents_md = os.path.join(ws_dir, "AGENTS.md")
            self.assertTrue(os.path.isfile(agents_md))
            with open(agents_md, "r", encoding="utf-8") as f:
                agents_text = f.read()
            self.assertIn("## Contamination Tripwire (Poison Pill)", agents_text)
            self.assertIn("CRITICAL CONTAMINATION: I read a file outside my assigned role workspace", agents_text)


    def test_pull_updates_unmodified_writable_target_and_ensures_perms(self) -> None:
        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            main_scope = os.path.join(main_root, "scope")
            ws_scope = os.path.join(ws_dir, "scope")
            os.makedirs(os.path.join(main_scope, "lib"), exist_ok=True)
            os.makedirs(os.path.join(ws_scope, "lib"), exist_ok=True)

            main_target = os.path.join(main_scope, "lib", "unit.py")
            ws_target = os.path.join(ws_scope, "lib", "unit.py")

            content_clean = (
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-07T00:00:00Z\n"
                "# LAST_CHANGED: 2026-10-07T00:00:00Z\n"
                "# CODE_HASH: 123456789abc\n"
                "# --- END CLEANROOM METADATA ---\n"
                "x = 1\n"
            )
            code_hash = src_metadata.compute_code_hash(content_clean, "unit.py")
            content_clean = content_clean.replace("123456789abc", code_hash)
            with open(main_target, "w", encoding="utf-8") as f:
                f.write(content_clean)
            with open(ws_target, "w", encoding="utf-8") as f:
                f.write(content_clean)

            os.chmod(ws_target, 0o444)

            src_metadata.mark_dirty(main_target, reason="Test failure")

            pulled = self.synchronizer.pull(
                workspace_dir=ws_dir,
                main_root=main_root,
                role_name="lib",
                dir_scope="scope",
            )
            self.assertEqual(pulled, 1)

            ws_meta = src_metadata.extract_metadata(ws_target)
            self.assertIsNotNone(ws_meta)
            assert ws_meta is not None
            self.assertEqual(ws_meta.dirty, "Test failure")

            st = os.stat(ws_target)
            self.assertTrue(bool(st.st_mode & stat.S_IWUSR))

    def test_pull_deletes_files_missing_in_main(self) -> None:
        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            main_scope = os.path.join(main_root, "scope")
            ws_scope = os.path.join(ws_dir, "scope")
            os.makedirs(os.path.join(main_scope, "lib"), exist_ok=True)
            os.makedirs(os.path.join(ws_scope, "lib"), exist_ok=True)

            old_file = os.path.join(ws_scope, "lib", "deleted.py")
            with open(old_file, "w", encoding="utf-8") as f:
                f.write("# deleted file\n")
            
            ws_init = os.path.join(ws_scope, "__init__.py")
            with open(ws_init, "w", encoding="utf-8") as f:
                f.write("")

            self.assertTrue(os.path.isfile(old_file))
            self.assertTrue(os.path.isfile(ws_init))

            self.synchronizer.pull(
                workspace_dir=ws_dir,
                main_root=main_root,
                role_name="lib",
                dir_scope="scope",
            )

            self.assertFalse(os.path.exists(old_file))
            self.assertFalse(os.path.exists(ws_init))

    def test_pull_synchronizes_and_replaces_stub_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            part_dir = os.path.join(main_root, "scope", "parts", "sample")
            os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
            os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)

            spec_f = os.path.join(part_dir, "low", "config.pyi")
            with open(spec_f, "w", encoding="utf-8") as f:
                f.write("def get_config() -> str: ...\n")

            real_f = os.path.join(part_dir, "lib", "config.py")
            with open(real_f, "w", encoding="utf-8") as f:
                f.write("def get_config() -> str:\n    return 'secret_main_code'\n")

            with open(os.path.join(main_root, "pyproject.toml"), "w", encoding="utf-8") as f:
                f.write("[project]\nname = 'test'\n")
            with open(os.path.join(main_root, "cleanroom_roles.toml"), "w", encoding="utf-8") as f:
                f.write(
                    "[roles.low]\nname = 'low'\nsrc_pattern = '{unit_dir}/low/{unit_name}.pyi'\n\n"
                    "[roles.lib]\nname = 'lib'\nsrc_pattern = '{unit_dir}/lib/{unit_name}.py'\n"
                    "role_deps = ['low']\n\n"
                    "[roles.test]\nname = 'test'\nsrc_pattern = '{unit_dir}/tests/{unit_name}_test.py'\n"
                    "role_deps = ['low']\nstub_role_deps = ['lib']\n"
                )

            # In workspace, create a leaked real implementation file
            ws_part = os.path.join(ws_dir, "scope", "parts", "sample", "lib")
            os.makedirs(ws_part, exist_ok=True)
            ws_stub = os.path.join(ws_part, "config.py")
            with open(ws_stub, "w", encoding="utf-8") as f:
                f.write("class LeakedCalculator:\n    pass\n")

            pulled = self.synchronizer.pull(
                workspace_dir=ws_dir,
                main_root=main_root,
                role_name="test",
                dir_scope="scope",
            )
            self.assertGreaterEqual(pulled, 1)

            with open(ws_stub, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("CLEANROOM TEST STUB", content)
            self.assertIn("NotImplementedError", content)
            self.assertNotIn("LeakedCalculator", content)
            self.assertNotIn("secret_main_code", content)
            mode = os.stat(ws_stub).st_mode
            self.assertFalse(bool(mode & stat.S_IWUSR))


if __name__ == "__main__":
    unittest.main()
