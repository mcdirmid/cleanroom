#!/usr/bin/env python3
"""coordinator_engine_test.py — Unit tests for Cleanroom Coordinator deterministic engine.

Tests:
  - Tiered worker retention (<5m / 200k, 5-10m / 100k)
  - Idle timeout pruning (>10m, and >100k with >5m idle)
  - Intra-role batch partitioning (>10 units)
  - Non-overlapping worker retention (no premature kills)
  - Multiple concurrent subagents per role
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
for _p in [_repo_root, os.path.join(_repo_root, "update_with_ai"), os.path.join(_repo_root, "update_python_with_ai")]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from update_with_ai.support.lib.coordinator_config import CoordinatorConfig
from update_with_ai.support.lib.cleanroom_coordinator_engine import (
    CoordinatorState,
    WorkerState,
    evaluate_pruning,
    is_worker_eligible_for_reuse,
    partition_batches_if_needed,
)


class CoordinatorEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = CoordinatorConfig(
            ttl_fresh_sec=300.0,
            ttl_max_sec=600.0,
            cap_fresh_tokens=200_000,
            cap_warm_tokens=100_000,
            idle_prune_ttl_sec=600.0,
            idle_prune_warm_ttl_sec=300.0,
            idle_prune_warm_cap_tokens=100_000,
            batch_size=10,
        )

    def test_worker_eligible_under_5min_under_200k(self) -> None:
        """Worker < 5m old is eligible for reuse up to 200k tokens."""
        now = 1000.0
        worker = WorkerState(
            conv_id="w1",
            role="//update_python_with_ai:lib",
            session_id="s_1",
            created_at=now - 120.0,  # 2 minutes old
            last_active_at=now - 30.0,
            unit_footprint=["//pkg:unit_a"],
            context_tokens=150_000,  # 150k < 200k
            status="idle",
        )
        self.assertTrue(is_worker_eligible_for_reuse(worker, ["//pkg:unit_a"], config=self.config, now=now))

    def test_worker_ineligible_under_5min_over_200k(self) -> None:
        """Worker < 5m old exceeding 200k tokens is not eligible for reuse."""
        now = 1000.0
        worker = WorkerState(
            conv_id="w1",
            role="//update_python_with_ai:lib",
            session_id="s_1",
            created_at=now - 120.0,  # 2 minutes old
            last_active_at=now - 30.0,
            unit_footprint=["//pkg:unit_a"],
            context_tokens=205_000,  # 205k > 200k
            status="idle",
        )
        self.assertFalse(is_worker_eligible_for_reuse(worker, ["//pkg:unit_a"], config=self.config, now=now))

    def test_worker_eligible_between_5_and_10min_under_100k(self) -> None:
        """Worker between 5 and 10 minutes old is eligible for reuse up to 100k tokens."""
        now = 1000.0
        worker = WorkerState(
            conv_id="w1",
            role="//update_python_with_ai:lib",
            session_id="s_1",
            created_at=now - 420.0,  # 7 minutes old
            last_active_at=now - 60.0,
            unit_footprint=["//pkg:unit_a"],
            context_tokens=85_000,  # 85k < 100k
            status="idle",
        )
        self.assertTrue(is_worker_eligible_for_reuse(worker, ["//pkg:unit_a"], config=self.config, now=now))

    def test_worker_ineligible_between_5_and_10min_over_100k(self) -> None:
        """Worker between 5 and 10 minutes old exceeding 100k tokens is not eligible."""
        now = 1000.0
        worker = WorkerState(
            conv_id="w1",
            role="//update_python_with_ai:lib",
            session_id="s_1",
            created_at=now - 420.0,  # 7 minutes old
            last_active_at=now - 60.0,
            unit_footprint=["//pkg:unit_a"],
            context_tokens=110_000,  # 110k > 100k
            status="idle",
        )
        self.assertFalse(is_worker_eligible_for_reuse(worker, ["//pkg:unit_a"], config=self.config, now=now))

    def test_worker_ineligible_past_10min(self) -> None:
        """Worker older than 10 minutes is not eligible for reuse."""
        now = 1000.0
        worker = WorkerState(
            conv_id="w1",
            role="//update_python_with_ai:lib",
            session_id="s_1",
            created_at=now - 650.0,  # 10m 50s old
            last_active_at=now - 60.0,
            unit_footprint=["//pkg:unit_a"],
            context_tokens=50_000,
            status="idle",
        )
        self.assertFalse(is_worker_eligible_for_reuse(worker, ["//pkg:unit_a"], config=self.config, now=now))

    def test_worker_ineligible_zero_overlap(self) -> None:
        """Worker with zero unit overlap is not eligible for reuse."""
        now = 1000.0
        worker = WorkerState(
            conv_id="w1",
            role="//update_python_with_ai:lib",
            session_id="s_1",
            created_at=now - 60.0,
            last_active_at=now - 10.0,
            unit_footprint=["//pkg:unit_a"],
            context_tokens=10_000,
            status="idle",
        )
        self.assertFalse(is_worker_eligible_for_reuse(worker, ["//pkg:unit_b"], config=self.config, now=now))

    def test_pruning_rules(self) -> None:
        """Evaluates idle pruning rules (>10m idle, and >100k context with >5m idle)."""
        now = 1000.0
        state = CoordinatorState(target="//pkg:asm_qa")

        # Worker 1: idle 12 minutes -> must be killed
        w1 = WorkerState("w1", "role", "s1", created_at=now - 800, last_active_at=now - 720, context_tokens=40_000)
        # Worker 2: >100k context and idle 6 minutes (>5m) -> must be killed
        w2 = WorkerState("w2", "role", "s2", created_at=now - 500, last_active_at=now - 360, context_tokens=120_000)
        # Worker 3: >100k context but idle only 2 minutes (<5m) -> kept
        w3 = WorkerState("w3", "role", "s3", created_at=now - 500, last_active_at=now - 120, context_tokens=150_000)
        # Worker 4: <100k context and idle 6 minutes (<10m) -> kept
        w4 = WorkerState("w4", "role", "s4", created_at=now - 500, last_active_at=now - 360, context_tokens=50_000)

        state.workers = {"w1": w1, "w2": w2, "w3": w3, "w4": w4}
        to_kill = evaluate_pruning(state, config=self.config, now=now)

        self.assertIn("w1", to_kill)
        self.assertIn("w2", to_kill)
        self.assertNotIn("w3", to_kill)
        self.assertNotIn("w4", to_kill)
        self.assertEqual(set(state.workers.keys()), {"w3", "w4"})

    def test_batch_partitioning(self) -> None:
        """Batches exceeding batch_size are partitioned into smaller chunks."""
        small_batch = [{"unit": f"//pkg:u{i}", "role": "r"} for i in range(7)]
        self.assertEqual(len(partition_batches_if_needed(small_batch, batch_size=10)), 1)

        large_batch = [{"unit": f"//pkg:u{i}", "role": "r"} for i in range(25)]
        chunks = partition_batches_if_needed(large_batch, batch_size=10)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[0]), 10)
        self.assertEqual(len(chunks[1]), 10)
        self.assertEqual(len(chunks[2]), 5)

    @patch("update_with_ai.support.lib.cleanroom_coordinator_engine._call_tool")
    @patch("update_with_ai.support.lib.cleanroom_coordinator_engine.ensure_mcp_server_running", return_value=True)
    def test_plan_next_step_revives_overlapping_worker(self, mock_server: MagicMock, mock_call: MagicMock) -> None:
        """Eligible overlapping workers are revived rather than spawning cold workers."""
        from update_with_ai.support.lib.cleanroom_coordinator_engine import plan_next_step, load_state, save_state
        import json, tempfile, shutil

        tmpdir = tempfile.mkdtemp()
        try:
            now = 2000.0
            st = CoordinatorState(target="//pkg:asm_qa")
            w1 = WorkerState(
                conv_id="w1",
                role="//update_python_with_ai:lib",
                session_id="s_1",
                created_at=now - 60.0,
                last_active_at=now - 10.0,
                unit_footprint=["//pkg:unit_a"],
                context_tokens=30_000,
                status="idle",
            )
            st.workers = {"w1": w1}
            save_state(st, tmpdir)

            mock_call.return_value = json.dumps({
                "is_complete": False,
                "ready_role": "//update_python_with_ai:lib",
                "batch": [{"unit": "//pkg:unit_a", "role": "//update_python_with_ai:lib"}],
                "dirty_nodes": ["//pkg:unit_a://update_python_with_ai:lib"],
            })

            plan = plan_next_step("//pkg:asm_qa", workspace_root=tmpdir, now=now, config=self.config)
            self.assertEqual(len(plan["revives"]), 1)
            self.assertEqual(plan["revives"][0]["recipient"], "w1")
            self.assertEqual(len(plan["spawns"]), 0)
            self.assertEqual(len(plan["kill"]), 0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @patch("update_with_ai.support.lib.cleanroom_coordinator_engine._call_tool")
    @patch("update_with_ai.support.lib.cleanroom_coordinator_engine.ensure_mcp_server_running", return_value=True)
    def test_plan_next_step_non_overlapping_spawns_without_killing_existing(self, mock_server: MagicMock, mock_call: MagicMock) -> None:
        """Non-overlapping batches spawn a new worker without terminating existing role workers."""
        from update_with_ai.support.lib.cleanroom_coordinator_engine import plan_next_step, load_state, save_state
        import json, tempfile, shutil

        tmpdir = tempfile.mkdtemp()
        try:
            now = 2000.0
            st = CoordinatorState(target="//pkg:asm_qa")
            w1 = WorkerState(
                conv_id="w1",
                role="//update_python_with_ai:lib",
                session_id="s_1",
                created_at=now - 60.0,
                last_active_at=now - 10.0,
                unit_footprint=["//pkg:unit_a"],
                context_tokens=30_000,
                status="idle",
            )
            st.workers = {"w1": w1}
            save_state(st, tmpdir)

            mock_call.return_value = json.dumps({
                "is_complete": False,
                "ready_role": "//update_python_with_ai:lib",
                "batch": [{"unit": "//pkg:unit_b", "role": "//update_python_with_ai:lib"}],
                "dirty_nodes": ["//pkg:unit_b://update_python_with_ai:lib"],
            })

            plan = plan_next_step("//pkg:asm_qa", workspace_root=tmpdir, now=now, config=self.config)
            self.assertEqual(len(plan["spawns"]), 1)
            self.assertEqual(len(plan["revives"]), 0)
            self.assertNotIn("w1", plan["kill"])

            # Verify w1 is still in state.workers (warm retention maintained)
            reloaded = load_state(tmpdir)
            self.assertIn("w1", reloaded.workers)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @patch("update_with_ai.support.lib.cleanroom_coordinator_engine._call_tool")
    @patch("update_with_ai.support.lib.cleanroom_coordinator_engine.ensure_mcp_server_running", return_value=True)
    def test_register_spawned_workers_inherits_metadata(self, mock_server: MagicMock, mock_call: MagicMock) -> None:
        """Registering spawned workers associates conversation IDs with role and unit footprint."""
        from update_with_ai.support.lib.cleanroom_coordinator_engine import (
            plan_next_step,
            register_spawned_workers,
            load_state,
        )
        import json, tempfile, shutil

        tmpdir = tempfile.mkdtemp()
        try:
            now = 2000.0
            mock_call.return_value = json.dumps({
                "is_complete": False,
                "ready_role": "//update_python_with_ai:lib",
                "batch": [{"unit": "//pkg:unit_x", "role": "//update_python_with_ai:lib"}],
                "dirty_nodes": ["//pkg:unit_x://update_python_with_ai:lib"],
            })

            plan = plan_next_step("//pkg:asm_qa", workspace_root=tmpdir, now=now, config=self.config)
            self.assertEqual(len(plan["spawns"]), 1)
            session_id = plan["spawns"][0]["session_id"]

            register_spawned_workers({"worker_cid_123": session_id}, workspace_root=tmpdir, now=now + 1.0)

            st = load_state(tmpdir)
            self.assertIn("worker_cid_123", st.workers)
            w = st.workers["worker_cid_123"]
            self.assertEqual(w.role, "//update_python_with_ai:lib")
            self.assertEqual(w.unit_footprint, ["//pkg:unit_x"])
            self.assertEqual(w.session_id, session_id)
            self.assertEqual(w.status, "busy")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
