# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T20:00:00Z
# CHANGE: author dsh_harness_impl unit tests
# CODE_HASH: 38a04972702c
# COVERAGE_AUDIT: 2026-10-13T20:42:16Z
# QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Unit tests for dsh_harness_impl."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from typing import Dict, List, Sequence

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.dsh.lib import dsh_harness
from update_with_ai.parts.dsh.lib.dsh_harness_impl import (
    DshHarnessAdapter,
    DshHarnessManager,
    DshTelemetryParser,
    __initialize__,
)
from update_with_ai.parts.subagent.lib import subagent_coordinator
from update_with_ai.parts.workspace.lib import workspace_work


class FakeWorkspaceWorkManager:
    """Test double implementing WorkspaceWorkManager for dsh harness tests."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.pending: Dict[str, List[str]] = {}

    def get_pending_work(self, workspace_dir: str) -> List[str]:
        return list(self.pending.get(workspace_dir, []))

    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None:
        self.pending[workspace_dir] = list(targets)

    def clear_pending_work(self, workspace_dir: str) -> None:
        self.pending.pop(workspace_dir, None)

    def remove_pending_target(self, workspace_dir: str, target: str) -> bool:
        items = self.pending.get(workspace_dir, [])
        if target in items:
            items.remove(target)
            return True
        return False


class DshHarnessImplTest(unittest.TestCase):
    """Test cases for DshTelemetryParser, DshHarnessAdapter, and DshHarnessManager."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.work_mgr = FakeWorkspaceWorkManager()
        self.registry.register_instance(
            self.work_mgr,
            keys=[workspace_work.WorkspaceWorkManager],
            tier=agent_session.agent_session,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_parse_stream_text_json(self) -> None:
        """Requirement: MUST parse JSON run events and calculate DeepSeek rate card cost."""
        stream_sample = (
            '{"type":"session","version":4,"id":"sess-1"}\n'
            '{"type":"assistant/message","data":{"usage":{"inputTokens":1000,"outputTokens":200,"cacheReadTokens":5000,"totalTokens":6200}}}\n'
            '{"type":"assistant/message","data":{"usage":{"inputTokens":500,"outputTokens":100,"cacheReadTokens":2000,"totalTokens":2600}}}\n'
        )

        parser = DshTelemetryParser()
        metrics = parser.parse_stream_text(
            stream_text=stream_sample,
            model_name="DeepSeek-V41-Flash",
        )

        self.assertEqual(metrics.input_tokens, 1500)
        self.assertEqual(metrics.cached_tokens, 7000)
        self.assertEqual(metrics.output_tokens, 300)
        self.assertEqual(metrics.total_tokens, 8800)
        # 1500 * 0.00000014 + 7000 * 0.000000014 + 300 * 0.00000028
        expected_cost = (1500 * 0.00000014) + (7000 * 0.000000014) + (300 * 0.00000028)
        self.assertAlmostEqual(metrics.cost_usd, expected_cost, places=6)
        self.assertEqual(metrics.model_name, "DeepSeek-V41-Flash")

    def test_parse_stream_text_regex_fallback(self) -> None:
        """Requirement: MUST parse token counts from text log and calculate cost."""
        log_sample = (
            "Starting agent run...\n"
            "Input tokens: 2500\n"
            "Cached tokens: 1000\n"
            "Output tokens: 500\n"
            "Finished run cleanly."
        )

        parser = DshTelemetryParser()
        metrics = parser.parse_stream_text(
            stream_text=log_sample,
            model_name="DeepSeek-V41-Flash",
        )

        self.assertEqual(metrics.input_tokens, 2500)
        self.assertEqual(metrics.cached_tokens, 1000)
        self.assertEqual(metrics.output_tokens, 500)
        self.assertEqual(metrics.total_tokens, 4000)

    def test_rate_card_cost_local_model(self) -> None:
        """Requirement: MUST charge $0.00 for local models (Qwen, MLX, etc.)."""
        stream_sample = '{"type":"assistant/message","data":{"usage":{"inputTokens":10000,"outputTokens":2000,"cacheReadTokens":50000,"totalTokens":62000}}}\n'
        parser = DshTelemetryParser()
        metrics = parser.parse_stream_text(
            stream_text=stream_sample,
            model_name="Qwen3.6-35B-A3B-oQ6-mtp",
        )
        self.assertEqual(metrics.cost_usd, 0.0)

    def test_dispatch_and_await_clean_turn_in_simulation(self) -> None:
        """Requirement: MUST execute turn and return clean status when work is completed."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=True,
            )

            # Setup pending work before turn
            self.work_mgr.set_pending_work(self.test_dir, ["high/unit_a.md", "high/unit_b.md"])

            dispatch = subagent_coordinator.RoleDispatch(
                role_name="high",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("high/unit_a.md",),
                batch_size=3,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)
            self.assertTrue(handle.startswith("dsh_high_"))

            # Simulate agent submitting target unit_a
            self.work_mgr.remove_pending_target(self.test_dir, "high/unit_a.md")

            result = adapter.await_role(handle)
            self.assertEqual(result.role, "high")
            self.assertEqual(result.status, "clean")
            self.assertEqual(result.submitted_targets, ("high/unit_a.md",))
            self.assertEqual(result.blamed_targets, ())

    def test_dispatch_and_await_blamed_turn_in_simulation(self) -> None:
        """Requirement: MUST return blamed status when blame buffer contains culprits."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=True,
            )

            self.work_mgr.set_pending_work(self.test_dir, ["low/unit_a.pyi"])

            # Write culprit file into blame buffer
            blame_buf = os.path.join(self.test_dir, ".cleanroom_blame_buffer.json")
            with open(blame_buf, "w", encoding="utf-8") as f:
                json.dump(["scenarios/unit_a.md"], f)

            dispatch = subagent_coordinator.RoleDispatch(
                role_name="low",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("low/unit_a.pyi",),
                batch_size=3,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)
            result = adapter.await_role(handle)

            self.assertEqual(result.role, "low")
            self.assertEqual(result.status, "blamed")
            self.assertEqual(result.blamed_targets, ("scenarios/unit_a.md",))

    def test_poll_role_in_simulation(self) -> None:
        """Requirement: MUST return completed turn result immediately in simulation mode."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = DshHarnessAdapter(
                model_name="DeepSeek-V41-Flash",
                simulation_mode=True,
            )

            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="//pkg",
                ready_targets=("lib/unit_a.py",),
                batch_size=3,
                task_prompt="",
            )

            handle = adapter.dispatch_role(dispatch)
            res = adapter.poll_role(handle)
            self.assertIsNotNone(res)
            assert res is not None
            self.assertEqual(res.role, "lib")
            self.assertEqual(res.status, "clean")

    def test_dsh_harness_manager_singleton(self) -> None:
        """Requirement: MUST construct configured DshHarnessAdapter instances from manager."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            mgr = scope.get_singleton(dsh_harness.DshHarnessManager)
            adapter = mgr.create_harness_adapter(
                model_name="DeepSeek-V41-Flash",
                timeout_seconds=120.0,
            )
            self.assertIsInstance(adapter, DshHarnessAdapter)
            parser = mgr.get_telemetry_parser()
            self.assertIsInstance(parser, DshTelemetryParser)


if __name__ == "__main__":
    unittest.main()
