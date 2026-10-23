"""Unit tests for pending_impl aligned with low-level specifications."""

import json
import os
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.metadata.lib import src_metadata
from update_with_ai.parts.workspace_cli.lib import (
    pending,
    pending_impl,
)


class WorkspacePendingImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.pending_mgr = pending_impl.WorkspacePendingManager()
        self.registry.register_instance(
            self.pending_mgr,
            keys=[
                pending.WorkspacePendingManager,
                pending_impl.WorkspacePendingManager,
            ],
            tier=agent_session.agent_session,
        )
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.phase_cm.__enter__()
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_get_pending_work_empty(self) -> None:
        ws_dir = os.path.join(self.test_dir, "empty_ws")
        os.makedirs(ws_dir, exist_ok=True)
        res = self.pending_mgr.get_pending_work(ws_dir)
        self.assertEqual(res, ())

    def test_set_and_get_pending_work(self) -> None:
        ws_dir = os.path.join(self.test_dir, "ws")
        os.makedirs(ws_dir, exist_ok=True)
        targets = ["staging/parts/agent/lib/foo.py", "staging/parts/agent/lib/bar.py"]
        self.pending_mgr.set_pending_work(ws_dir, targets)
        res = self.pending_mgr.get_pending_work(ws_dir)
        self.assertEqual(list(res), targets)

        buf_p = os.path.join(ws_dir, ".cleanroom_pending_work.json")
        self.assertTrue(os.path.isfile(buf_p))
        with open(buf_p, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("assigned_at", data)
        self.assertEqual(data["targets"], targets)

    def test_remove_pending_target(self) -> None:
        ws_dir = os.path.join(self.test_dir, "ws_rem")
        os.makedirs(ws_dir, exist_ok=True)
        targets = ["staging/parts/agent/lib/foo.py", "staging/parts/agent/lib/bar.py"]
        self.pending_mgr.set_pending_work(ws_dir, targets)

        self.pending_mgr.remove_pending_target(ws_dir, "staging/parts/agent/lib/foo.py")
        res = self.pending_mgr.get_pending_work(ws_dir)
        self.assertEqual(list(res), ["staging/parts/agent/lib/bar.py"])

    def test_clear_pending_work(self) -> None:
        ws_dir = os.path.join(self.test_dir, "ws_clear")
        os.makedirs(ws_dir, exist_ok=True)
        self.pending_mgr.set_pending_work(ws_dir, ["staging/parts/agent/lib/foo.py"])
        buf_p = os.path.join(ws_dir, ".cleanroom_pending_work.json")
        self.assertTrue(os.path.isfile(buf_p))

        self.pending_mgr.clear_pending_work(ws_dir)
        self.assertFalse(os.path.isfile(buf_p))
        self.assertEqual(self.pending_mgr.get_pending_work(ws_dir), ())

    def test_is_pending_target_dirty_missing_file(self) -> None:
        ws_dir = os.path.join(self.test_dir, "ws_dirty")
        os.makedirs(ws_dir, exist_ok=True)
        # Missing file evaluates dirty
        is_dirty = self.pending_mgr.is_pending_target_dirty("nonexistent.py", ws_dir)
        self.assertTrue(is_dirty)

    def test_is_pending_target_dirty_metadata(self) -> None:
        ws_dir = os.path.join(self.test_dir, "ws_dirty_meta")
        os.makedirs(ws_dir, exist_ok=True)
        target = os.path.join(ws_dir, "test.py")

        # Dirty flag
        src_metadata.update_metadata(target, dirty="Fix error")
        self.assertTrue(self.pending_mgr.is_pending_target_dirty("test.py", ws_dir))

        # Clean
        src_metadata.update_metadata(
            target,
            last_cleaned="2026-10-10T12:00:00Z",
            last_changed="2026-10-10T12:00:00Z",
            clear_dirty=True,
        )
        meta = src_metadata.extract_metadata(target)
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertIsNone(meta.dirty)
        self.assertFalse(self.pending_mgr.is_pending_target_dirty("test.py", ws_dir))

    def test_is_pending_target_dirty_projected_workspace_metadata(self) -> None:
        """Verifies that pending dirty evaluation resolves canonical metadata when workspace has projected metadata."""
        canonical_repo = os.path.join(self.test_dir, "canonical_repo")
        role_ws = os.path.join(self.test_dir, "role_ws")
        part_rel = os.path.join("parts", "foo", "lib")
        os.makedirs(os.path.join(canonical_repo, part_rel), exist_ok=True)
        os.makedirs(os.path.join(role_ws, part_rel), exist_ok=True)

        rel_target = os.path.join("parts", "foo", "lib", "bar.py")
        main_target = os.path.join(canonical_repo, rel_target)
        ws_target = os.path.join(role_ws, rel_target)

        # Clean in canonical repo
        src_metadata.update_metadata(
            main_target,
            last_cleaned="2026-10-10T12:00:00Z",
            last_changed="2026-10-10T12:00:00Z",
            clear_dirty=True,
        )

        # Projected in role workspace (no LAST_CLEANED)
        with open(ws_target, "w", encoding="utf-8") as f:
            f.write("# --- CLEANROOM METADATA ---\n# CODE_HASH: 123456\n# --- END CLEANROOM METADATA ---\n")

        # When evaluated with main_root pointing to canonical_repo:
        self.assertFalse(
            self.pending_mgr.is_pending_target_dirty(
                rel_target,
                workspace_dir=role_ws,
                main_root=canonical_repo,
                role_name="lib",
            )
        )

        # If canonical target becomes dirty:
        src_metadata.update_metadata(main_target, dirty="Defect found")
        self.assertTrue(
            self.pending_mgr.is_pending_target_dirty(
                rel_target,
                workspace_dir=role_ws,
                main_root=canonical_repo,
                role_name="lib",
            )
        )

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:40:00Z
# CHANGE: Unit tests for pending_impl
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
