from __future__ import annotations

import json
import shutil
import tempfile
from typing import Any
import unittest
from unittest.mock import MagicMock, patch

from update_with_ai.parts.antigravity.lib.antigravity_coordinator import (
    ActionPlan,
    CoordinatorConfig,
    CoordinatorState,
    WorkerState,
)
from update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl import AntigravityCoordinator


class AntigravityCoordinatorImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.coordinator = AntigravityCoordinator()
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

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_worker_eligible_under_5min_under_200k(self) -> None:
        # Requirement: The antigravity coordinator checks whether a worker state qualifies for reuse given target units, coordinator config, and a current timestamp.
        # Requirement: Evaluating worker eligibility for reuse verifies idle status and tiered context limits based on worker age.
        # Requirement: When the worker age is less than the ttl fresh sec duration, the worker qualifies if its context tokens are below the cap fresh tokens ceiling.
        now = 1000.0
        worker = WorkerState(
            conv_id="w1",
            role="//update_python_with_ai:lib",
            session_id="s_1",
            created_at=now - 120.0,  # 2m old
            last_active_at=now - 10.0,
            unit_footprint=["//pkg:unit_a"],
            context_tokens=150_000,  # 150k < 200k
            status="idle",
        )
        self.assertTrue(self.coordinator.is_worker_eligible_for_reuse(worker, ["//pkg:unit_a"], self.config, now))

    def test_worker_not_eligible_under_5min_over_200k(self) -> None:
        # Requirement: When the worker age is less than the ttl fresh sec duration, the worker qualifies if its context tokens are below the cap fresh tokens ceiling.
        now = 1000.0
        worker = WorkerState(
            conv_id="w1",
            role="//update_python_with_ai:lib",
            session_id="s_1",
            created_at=now - 120.0,
            last_active_at=now - 10.0,
            unit_footprint=["//pkg:unit_a"],
            context_tokens=250_000,  # 250k > 200k
            status="idle",
        )
        self.assertFalse(self.coordinator.is_worker_eligible_for_reuse(worker, ["//pkg:unit_a"], self.config, now))

    def test_worker_eligible_between_5_and_10min_under_100k(self) -> None:
        # Requirement: When the worker age is between the ttl fresh sec duration and the ttl max sec duration, the worker qualifies if its context tokens are below the cap warm tokens ceiling.
        now = 1000.0
        worker = WorkerState(
            conv_id="w1",
            role="//update_python_with_ai:lib",
            session_id="s_1",
            created_at=now - 400.0,  # 6.6m old
            last_active_at=now - 10.0,
            unit_footprint=["//pkg:unit_a"],
            context_tokens=80_000,  # 80k < 100k
            status="idle",
        )
        self.assertTrue(self.coordinator.is_worker_eligible_for_reuse(worker, ["//pkg:unit_a"], self.config, now))

    def test_worker_not_eligible_over_10min(self) -> None:
        # Requirement: Workers exceeding the ttl max sec duration or not in idle status do not qualify for reuse.
        now = 1000.0
        worker = WorkerState(
            conv_id="w1",
            role="//update_python_with_ai:lib",
            session_id="s_1",
            created_at=now - 700.0,  # > 10m old
            last_active_at=now - 10.0,
            unit_footprint=["//pkg:unit_a"],
            context_tokens=10_000,
            status="idle",
        )
        self.assertFalse(self.coordinator.is_worker_eligible_for_reuse(worker, ["//pkg:unit_a"], self.config, now))

    def test_evaluate_pruning(self) -> None:
        # Requirement: The antigravity coordinator determines worker identifiers to terminate based on worker failure status, idle timeouts, and context token caps.
        # Requirement: Evaluating pruning identifies workers with failed status or exceeding idle timeouts or token limits.
        # Requirement: Workers with failed status are immediately marked for termination.
        # Requirement: Workers idle longer than the idle prune ttl sec timeout are marked for termination.
        # Requirement: Workers whose context tokens exceed the idle prune warm cap tokens ceiling and whose idle duration exceeds the idle prune warm ttl sec timeout are marked for termination.
        # Requirement: Pruned workers are removed from active coordinator state.
        now = 2000.0
        w1 = WorkerState(conv_id="w1", role="r", session_id="s1", created_at=now-1000, last_active_at=now-650, unit_footprint=[], context_tokens=10_000, status="idle")  # idle > 10m
        w2 = WorkerState(conv_id="w2", role="r", session_id="s2", created_at=now-600, last_active_at=now-350, unit_footprint=[], context_tokens=150_000, status="idle")  # > 100k & idle > 5m
        w3 = WorkerState(conv_id="w3", role="r", session_id="s3", created_at=now-600, last_active_at=now-100, unit_footprint=[], context_tokens=150_000, status="idle")  # > 100k but idle < 5m
        w4 = WorkerState(conv_id="w4", role="r", session_id="s4", created_at=now-200, last_active_at=now-100, unit_footprint=[], context_tokens=30_000, status="idle")  # healthy
        wf = WorkerState(conv_id="wf", role="r", session_id="sf", created_at=now-50, last_active_at=now-10, unit_footprint=[], context_tokens=1000, status="failed")  # failed worker

        st = CoordinatorState(target="//pkg:asm", session_counter=0, workers={"w1": w1, "w2": w2, "w3": w3, "w4": w4, "wf": wf}, pending_spawns={})
        to_kill = self.coordinator.evaluate_pruning(st, self.config, now)

        self.assertIn("w1", to_kill)
        self.assertIn("w2", to_kill)
        self.assertIn("wf", to_kill)
        self.assertNotIn("w3", to_kill)
        self.assertNotIn("w4", to_kill)

    def test_partition_batches(self) -> None:
        # Requirement: The antigravity coordinator divides a ready batch into clusters bounded by batch size.
        # Requirement: Partitioning batches divides ready units into contiguous sub-batches bounded by the batch size limit to enable concurrent worker execution across independent units.
        small_batch = [{"unit": f"//pkg:u{i}", "role": "r"} for i in range(5)]
        self.assertEqual(len(self.coordinator.partition_batches(small_batch, batch_size=10)), 1)

        large_batch = [{"unit": f"//pkg:u{i}", "role": "r"} for i in range(25)]
        chunks = self.coordinator.partition_batches(large_batch, batch_size=10)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[0]), 10)
        self.assertEqual(len(chunks[1]), 10)
        self.assertEqual(len(chunks[2]), 5)

    @patch("update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl.AntigravityCoordinator.ensure_server_running", return_value=True)
    @patch("update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl.get_singleton")
    def test_plan_next_step_revives_overlapping_worker(self, mock_get: MagicMock, mock_ensure: MagicMock) -> None:
        # Requirement: The antigravity coordinator computes an action plan for a target, an active worker reports mapping, coordinator config, workspace root, timestamp, and a server port.
        # Requirement: When a ready batch is returned, the batch is partitioned by batch size. For each partition, eligible warm workers matching the ready role are evaluated, preferring workers with unit footprint overlap and selecting the worker with the least conversation context tokens, falling back to eligible non-overlapping workers with least conversation context tokens. Assigned units are additively merged into the revived worker's unit footprint. If no eligible warm worker is found, a fresh worker is spawned.
        now = 2000.0
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
        st = CoordinatorState(target="//pkg:asm_qa", session_counter=1, workers={"w1": w1}, pending_spawns={})
        self.coordinator.save_state(st, self.tmpdir)

        mock_mcp = MagicMock()
        mock_mcp.next_batch.return_value = json.dumps({
            "is_complete": False,
            "ready_role": "//update_python_with_ai:lib",
            "batch": [{"unit": "//pkg:unit_a", "role": "//update_python_with_ai:lib"}],
            "dirty_nodes": ["//pkg:unit_a://update_python_with_ai:lib"],
        })
        mock_gate = MagicMock()
        mock_telemetry = MagicMock()
        mock_telemetry.get_conversation_stats.return_value = None

        def get_single(cls: type) -> Any:
            from update_with_ai.parts.antigravity.lib import antigravity_mcp_client, antigravity_sandbox_gate, antigravity_telemetry
            if cls == antigravity_mcp_client.AntigravityMcpClient:
                return mock_mcp
            if cls == antigravity_sandbox_gate.AntigravitySandboxGate:
                return mock_gate
            return mock_telemetry

        mock_get.side_effect = get_single

        plan = self.coordinator.plan_next_step("//pkg:asm_qa", {}, self.config, self.tmpdir, now, 8765)
        self.assertEqual(len(plan.revives), 1)
        self.assertEqual(plan.revives[0]["recipient"], "w1")
        self.assertEqual(len(plan.spawns), 0)

    @patch("update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl.AntigravityCoordinator.ensure_server_running", return_value=True)
    @patch("update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl.get_singleton")
    def test_plan_next_step_selects_least_tokens_and_merges_footprint(self, mock_get: MagicMock, mock_ensure: MagicMock) -> None:
        # Requirement: When a ready batch is returned, the batch is partitioned by batch size. For each partition, eligible warm workers matching the ready role are evaluated, preferring workers with unit footprint overlap and selecting the worker with the least conversation context tokens, falling back to eligible non-overlapping workers with least conversation context tokens. Assigned units are additively merged into the revived worker's unit footprint. If no eligible warm worker is found, a fresh worker is spawned.
        now = 2000.0
        # Two non-overlapping idle workers: w1 has 50k tokens, w2 has 20k tokens
        w1 = WorkerState(
            conv_id="w1",
            role="//update_python_with_ai:lib",
            session_id="s_1",
            created_at=now - 60.0,
            last_active_at=now - 10.0,
            unit_footprint=["//pkg:unit_b"],
            context_tokens=50_000,
            status="idle",
        )
        w2 = WorkerState(
            conv_id="w2",
            role="//update_python_with_ai:lib",
            session_id="s_2",
            created_at=now - 60.0,
            last_active_at=now - 10.0,
            unit_footprint=["//pkg:unit_c"],
            context_tokens=20_000,
            status="idle",
        )
        st = CoordinatorState(target="//pkg:asm_qa", session_counter=2, workers={"w1": w1, "w2": w2}, pending_spawns={})
        self.coordinator.save_state(st, self.tmpdir)

        mock_mcp = MagicMock()
        mock_mcp.next_batch.return_value = json.dumps({
            "is_complete": False,
            "ready_role": "//update_python_with_ai:lib",
            "batch": [{"unit": "//pkg:unit_a", "role": "//update_python_with_ai:lib"}],
            "dirty_nodes": ["//pkg:unit_a://update_python_with_ai:lib"],
        })
        mock_gate = MagicMock()
        mock_telemetry = MagicMock()
        mock_telemetry.get_conversation_stats.return_value = None

        def get_single(cls: type) -> Any:
            from update_with_ai.parts.antigravity.lib import antigravity_mcp_client, antigravity_sandbox_gate, antigravity_telemetry
            if cls == antigravity_mcp_client.AntigravityMcpClient:
                return mock_mcp
            if cls == antigravity_sandbox_gate.AntigravitySandboxGate:
                return mock_gate
            return mock_telemetry

        mock_get.side_effect = get_single

        # w2 should be chosen because it has least context tokens (20k < 50k)
        plan = self.coordinator.plan_next_step("//pkg:asm_qa", {}, self.config, self.tmpdir, now, 8765)
        self.assertEqual(len(plan.revives), 1)
        self.assertEqual(plan.revives[0]["recipient"], "w2")

        # Verify additive footprint: w2 footprint should now contain unit_c AND unit_a
        st_after = self.coordinator.load_state(self.tmpdir, "//pkg:asm_qa")
        self.assertIn("//pkg:unit_c", st_after.workers["w2"].unit_footprint)
        self.assertIn("//pkg:unit_a", st_after.workers["w2"].unit_footprint)

    @patch("update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl.AntigravityCoordinator.ensure_server_running", return_value=True)
    @patch("update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl.get_singleton")
    def test_register_spawned_workers_inherits_metadata(self, mock_get: MagicMock, mock_ensure: MagicMock) -> None:
        # Requirement: The antigravity coordinator associates newly spawned conversation identifiers with assigned sessions in coordinator state.
        # Requirement: Registering spawned workers associates newly spawned conversation identifiers with their assigned sessions, copying role and unit footprint from pending spawns into active worker state records.
        now = 2000.0
        mock_mcp = MagicMock()
        mock_mcp.next_batch.return_value = json.dumps({
            "is_complete": False,
            "ready_role": "//update_python_with_ai:lib",
            "batch": [{"unit": "//pkg:unit_x", "role": "//update_python_with_ai:lib"}],
            "dirty_nodes": ["//pkg:unit_x://update_python_with_ai:lib"],
        })
        mock_gate = MagicMock()
        mock_telemetry = MagicMock()
        mock_telemetry.get_conversation_stats.return_value = None

        def get_single(cls: type) -> Any:
            from update_with_ai.parts.antigravity.lib import antigravity_mcp_client, antigravity_sandbox_gate, antigravity_telemetry
            if cls == antigravity_mcp_client.AntigravityMcpClient:
                return mock_mcp
            if cls == antigravity_sandbox_gate.AntigravitySandboxGate:
                return mock_gate
            return mock_telemetry

        mock_get.side_effect = get_single

        plan = self.coordinator.plan_next_step("//pkg:asm_qa", {}, self.config, self.tmpdir, now, 8765)
        self.assertEqual(len(plan.spawns), 1)
        session_id = plan.spawns[0]["session_id"]

        self.coordinator.register_spawned_workers({"worker_cid_999": session_id}, self.tmpdir, now + 1.0)
        reloaded = self.coordinator.load_state(self.tmpdir, "")
        self.assertIn("worker_cid_999", reloaded.workers)
        w = reloaded.workers["worker_cid_999"]
        self.assertEqual(w.role, "//update_python_with_ai:lib")
        self.assertEqual(list(w.unit_footprint), ["//pkg:unit_x"])
        self.assertEqual(w.session_id, session_id)

    @patch("update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl.AntigravityCoordinator.ensure_server_running", return_value=True)
    @patch("update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl.get_singleton")
    def test_plan_next_step_failure_retried_then_aborted(self, mock_get: MagicMock, mock_ensure: MagicMock) -> None:
        # Requirement: When worker reports indicate failures, failure counts for assigned units are incremented. If any unit exceeds the max retries per unit limit, DAG convergence is aborted and all workers are terminated. When worker reports indicate successful completion, failure counts for assigned units are cleared.
        now = 3000.0
        mock_mcp = MagicMock()
        mock_mcp.next_batch.return_value = json.dumps({
            "is_complete": False,
            "ready_role": "//update_python_with_ai:lib",
            "batch": [{"unit": "//pkg:unit_fail", "role": "//update_python_with_ai:lib"}],
            "dirty_nodes": ["//pkg:unit_fail://update_python_with_ai:lib"],
        })
        mock_gate = MagicMock()
        mock_telemetry = MagicMock()
        mock_telemetry.get_conversation_stats.return_value = None

        def get_single(cls: type) -> Any:
            from update_with_ai.parts.antigravity.lib import antigravity_mcp_client, antigravity_sandbox_gate, antigravity_telemetry
            if cls == antigravity_mcp_client.AntigravityMcpClient:
                return mock_mcp
            if cls == antigravity_sandbox_gate.AntigravitySandboxGate:
                return mock_gate
            return mock_telemetry

        mock_get.side_effect = get_single

        # Initial state with worker w_fail
        init_state = CoordinatorState(
            target="//pkg:asm_qa",
            session_counter=1,
            workers={
                "w_fail": WorkerState(
                    conv_id="w_fail",
                    role="//update_python_with_ai:lib",
                    session_id="s_fail",
                    created_at=now - 50.0,
                    last_active_at=now - 10.0,
                    unit_footprint=["//pkg:unit_fail"],
                    context_tokens=10_000,
                    status="busy",
                )
            },
            pending_spawns={},
            failure_counts={},
        )
        self.coordinator.save_state(init_state, self.tmpdir)

        # 1st failure: allowed retry
        plan1 = self.coordinator.plan_next_step(
            "//pkg:asm_qa",
            {"w_fail": "status: failed: compiler syntax error"},
            self.config,
            self.tmpdir,
            now,
            8765,
        )
        self.assertFalse(plan1.is_complete)
        self.assertNotIn("aborted", plan1.summary.lower())

        st1 = self.coordinator.load_state(self.tmpdir, "//pkg:asm_qa")
        self.assertEqual(st1.failure_counts.get("//pkg:unit_fail"), 1)

        # Re-save with active worker for 2nd failure
        st1_with_worker = CoordinatorState(
            target="//pkg:asm_qa",
            session_counter=st1.session_counter,
            workers={
                "w_fail_2": WorkerState(
                    conv_id="w_fail_2",
                    role="//update_python_with_ai:lib",
                    session_id="s_fail_2",
                    created_at=now,
                    last_active_at=now,
                    unit_footprint=["//pkg:unit_fail"],
                    context_tokens=10_000,
                    status="busy",
                )
            },
            pending_spawns={},
            failure_counts=st1.failure_counts,
        )
        self.coordinator.save_state(st1_with_worker, self.tmpdir)

        # 2nd failure: exceeds max_retries_per_unit (1) -> aborts
        plan2 = self.coordinator.plan_next_step(
            "//pkg:asm_qa",
            {"w_fail_2": "status: failed: second failure"},
            self.config,
            self.tmpdir,
            now + 10.0,
            8765,
        )
        self.assertFalse(plan2.is_complete)
        self.assertIn("DAG convergence aborted", plan2.summary)
        self.assertIn("//pkg:unit_fail", plan2.summary)
        self.assertIn("w_fail_2", plan2.kill)

        # Verify state after abort
        st2 = self.coordinator.load_state(self.tmpdir, "//pkg:asm_qa")
        self.assertEqual(len(st2.workers), 0)
        self.assertEqual(st2.failure_counts.get("//pkg:unit_fail"), 2)

    def test_record_worker_status(self) -> None:
        # Requirement: The antigravity coordinator updates worker lifecycle status to idle or failed and updates unit failure counts for a session identifier in coordinator state.
        # Requirement: Recording worker status transitions a worker matching the session identifier to failed status upon failure or idle status upon completion, updates last active timestamp, and records unit failure counts or clears failure counts based on completion or failure status.
        now = 1000.0
        st = CoordinatorState(
            target="//pkg:asm_qa",
            session_counter=1,
            workers={
                "w1": WorkerState(
                    conv_id="w1",
                    role="//update_python_with_ai:lib",
                    session_id="s_1",
                    created_at=now,
                    last_active_at=now,
                    unit_footprint=["//pkg:unit_a"],
                    context_tokens=10_000,
                    status="busy",
                )
            },
            pending_spawns={},
            failure_counts={"//pkg:unit_a": 1},
        )
        self.coordinator.save_state(st, self.tmpdir)

        # Worker completes: status becomes idle, failure count cleared
        self.coordinator.record_worker_status("s_1", "complete", self.tmpdir, now=now + 50.0)
        st_after = self.coordinator.load_state(self.tmpdir, "//pkg:asm_qa")
        self.assertEqual(st_after.workers["w1"].status, "idle")
        self.assertEqual(st_after.workers["w1"].last_active_at, now + 50.0)
        self.assertEqual(st_after.failure_counts.get("//pkg:unit_a"), 0)

        # Worker fails: status becomes failed, failure count incremented
        self.coordinator.record_worker_status("s_1", "failed", self.tmpdir, now=now + 60.0, unit="//pkg:unit_a")
        st_fail = self.coordinator.load_state(self.tmpdir, "//pkg:asm_qa")
        self.assertEqual(st_fail.workers["w1"].status, "failed")
        self.assertEqual(st_fail.failure_counts.get("//pkg:unit_a"), 1)

    @patch("update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl.get_singleton")
    def test_in_flight_busy_worker_not_respawned_or_revived(self, mock_get_singleton: MagicMock) -> None:
        # Requirement: Workers currently in busy status are in-flight; only idle workers are eligible for reuse or revives. If ready units are already assigned to in-flight busy workers, no redundant spawns or revives are generated. Newly spawned and revived workers are marked with busy status.
        mock_client = MagicMock()
        mock_telemetry = MagicMock()
        mock_gate = MagicMock()

        def singleton_dispatch(cls_or_key: Any) -> Any:
            name = getattr(cls_or_key, "__name__", str(cls_or_key))
            if "AntigravityMcpClient" in name:
                return mock_client
            if "AntigravityTelemetry" in name:
                return mock_telemetry
            if "AntigravitySandboxGate" in name:
                return mock_gate
            return MagicMock()

        mock_get_singleton.side_effect = singleton_dispatch
        mock_telemetry.get_conversation_stats.return_value = None
        mock_client.next_batch.return_value = json.dumps({
            "is_complete": False,
            "dirty_nodes": ["//pkg:unit_a://update_python_with_ai:lib"],
            "ready_role": "//update_python_with_ai:lib",
            "batch": [{"unit": "//pkg:unit_a", "role": "//update_python_with_ai:lib"}],
        })

        now = 1000.0
        st = CoordinatorState(
            target="//pkg:asm_qa",
            session_counter=1,
            workers={
                "w1": WorkerState(
                    conv_id="w1",
                    role="//update_python_with_ai:lib",
                    session_id="s_1",
                    created_at=now,
                    last_active_at=now,
                    unit_footprint=["//pkg:unit_a"],
                    context_tokens=10_000,
                    status="busy",
                )
            },
            pending_spawns={},
            failure_counts={},
        )
        self.coordinator.save_state(st, self.tmpdir)

        with patch.object(self.coordinator, "ensure_server_running", return_value=True):
            plan = self.coordinator.plan_next_step(
                "//pkg:asm_qa",
                {},
                self.config,
                self.tmpdir,
                now + 10.0,
                8765,
            )

        self.assertFalse(plan.is_complete)
        self.assertEqual(len(plan.spawns), 0)
        self.assertEqual(len(plan.revives), 0)
        self.assertIn("Waiting for in-flight workers", plan.summary)


if __name__ == "__main__":
    unittest.main()
