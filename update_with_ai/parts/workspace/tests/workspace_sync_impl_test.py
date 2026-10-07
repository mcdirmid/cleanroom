# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 287730271a4f
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

"""Unit tests for workspace_sync_impl."""

import json
import os
import stat
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.control.lib import src_metadata, src_metadata_impl
from update_with_ai.parts.workspace.lib import (
    workspace_registry,
    workspace_registry_impl,
    workspace_sync,
    workspace_sync_impl,
)


class WorkspaceSyncImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = get_default_registry()
        self.ws_registry = workspace_registry_impl.WorkspaceRegistry()
        self.registry.register_instance(
            self.ws_registry,
            keys=[
                workspace_registry.WorkspaceRegistry,
                workspace_registry_impl.WorkspaceRegistry,
            ],
            tier=agent_session.agent_session,
        )
        self.src_meta = src_metadata_impl.SourceMetadataCoordinator()
        self.registry.register_instance(
            self.src_meta,
            keys=[
                src_metadata.SourceMetadataCoordinator,
                src_metadata_impl.SourceMetadataCoordinator,
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


if __name__ == "__main__":
    unittest.main()
