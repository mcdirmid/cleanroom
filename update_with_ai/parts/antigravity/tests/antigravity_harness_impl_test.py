# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_harness_impl unit tests
# CODE_HASH: aead38fd0e51
# COVERAGE_AUDIT: 2026-10-13T20:42:16Z
# QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Unit tests for antigravity_harness_impl."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.antigravity.lib import (
    antigravity_harness,
    antigravity_harness_impl,
)
from update_with_ai.parts.subagent.lib import subagent_coordinator


class AntigravityHarnessImplTest(unittest.TestCase):
    """Test cases for AntigravityHarnessManager and AntigravityHarnessAdapter."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        antigravity_harness_impl.__initialize__(self.registry)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_transcript_parser_flash_pricing(self) -> None:
        """Scenario 2: Verifies transcript parsing and rate card calculation for Gemini Flash."""
        parser = antigravity_harness_impl.TranscriptTelemetryParser()

        transcript_file = os.path.join(self.test_dir, "transcript.jsonl")
        step1 = {
            "step_index": 1,
            "type": "MODEL",
            "usage": {
                "input_tokens": 100_000,
                "cached_tokens": 400_000,
                "output_tokens": 50_000,
            },
        }
        step2 = {
            "step_index": 2,
            "type": "PLANNER_RESPONSE",
            "usage": {
                "input_tokens": 100_000,
                "cached_tokens": 600_000,
                "output_tokens": 50_000,
            },
        }
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(step1) + "\n")
            f.write(json.dumps(step2) + "\n")

        # Total: input=200k, cached=1000k, output=100k
        # Flash: input $0.10/M, cached $0.025/M, output $0.40/M
        # Cost: (200k * 0.10 / 1M) + (1000k * 0.025 / 1M) + (100k * 0.40 / 1M)
        # Cost: 0.02 + 0.025 + 0.04 = $0.085
        metrics = parser.parse_transcript_file(transcript_file, model_name="gemini-3.8-flash")
        self.assertEqual(metrics.input_tokens, 200_000)
        self.assertEqual(metrics.cached_tokens, 1_000_000)
        self.assertEqual(metrics.output_tokens, 100_000)
        self.assertEqual(metrics.total_tokens, 1_300_000)
        self.assertAlmostEqual(metrics.cost_usd, 0.085, places=5)

    def test_transcript_parser_pro_pricing(self) -> None:
        """Scenario 2b: Verifies transcript parsing and rate card calculation for Gemini Pro."""
        parser = antigravity_harness_impl.TranscriptTelemetryParser()

        transcript_file = os.path.join(self.test_dir, "transcript.jsonl")
        step = {
            "step_index": 1,
            "type": "MODEL",
            "usage": {
                "input_tokens": 1_000_000,
                "cached_tokens": 1_000_000,
                "output_tokens": 100_000,
            },
        }
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(step) + "\n")

        # Pro: input $1.25/M, cached $0.3125/M, output $5.00/M
        # Cost: 1.25 + 0.3125 + 0.50 = 2.0625
        metrics = parser.parse_transcript_file(transcript_file, model_name="gemini-3.8-pro")
        self.assertEqual(metrics.input_tokens, 1_000_000)
        self.assertEqual(metrics.cached_tokens, 1_000_000)
        self.assertEqual(metrics.output_tokens, 100_000)
        self.assertAlmostEqual(metrics.cost_usd, 2.0625, places=4)

    def test_dispatch_and_await_role_turn(self) -> None:
        """Scenario 1 & 3: Verifies dispatching and awaiting role turn via custom command."""
        adapter = antigravity_harness_impl.AntigravityHarnessAdapter(
            model_name="gemini-flash",
            custom_cmd="echo [SUBMITTED] lib/test_unit.py",
        )
        dispatch = subagent_coordinator.RoleDispatch(
            role_name="lib",
            workspace_dir=self.test_dir,
            dir_scope="pkg_a",
            ready_targets=("lib/test_unit.py",),
        )
        handle = adapter.dispatch_role(dispatch)
        self.assertTrue(handle.startswith("antigravity-task-"))

        result = adapter.await_role(handle)
        self.assertEqual(result.role, "lib")
        self.assertEqual(result.status, "complete")
        self.assertIn("lib/test_unit.py", result.submitted_targets)

    def test_await_role_turn_with_blame_buffer(self) -> None:
        """Scenario 3b: Verifies blame detection from workspace blame buffer."""
        buf_file = os.path.join(self.test_dir, ".cleanroom_blame_buffer.json")
        with open(buf_file, "w", encoding="utf-8") as f:
            json.dump([{"culprit_target": "high/foo.md", "critique": "ambiguity"}], f)

        adapter = antigravity_harness_impl.AntigravityHarnessAdapter(
            model_name="gemini-flash",
            custom_cmd="echo simulation",
        )
        dispatch = subagent_coordinator.RoleDispatch(
            role_name="lib",
            workspace_dir=self.test_dir,
            dir_scope="pkg_a",
            ready_targets=("lib/test_unit.py",),
        )
        handle = adapter.dispatch_role(dispatch)
        result = adapter.await_role(handle)

        self.assertEqual(result.status, "blamed")
        self.assertIn("high/foo.md", result.blamed_targets)

    def test_harness_manager_in_lifecycle(self) -> None:
        """Verifies AntigravityHarnessManager singleton lifecycle resolution."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            mgr = scope.get_singleton(antigravity_harness.AntigravityHarnessManager)
            self.assertIsNotNone(mgr)

            adapter = mgr.create_harness_adapter(model_name="gemini-flash")
            self.assertIsNotNone(adapter)

            parser = mgr.get_transcript_parser()
            self.assertIsNotNone(parser)

    def test_poll_role_turn(self) -> None:
        """Scenario 5: Verifies non-blocking polling of role turn."""
        adapter = antigravity_harness_impl.AntigravityHarnessAdapter(
            model_name="gemini-flash",
            custom_cmd="echo [SUBMITTED] lib/test_unit.py",
        )
        dispatch = subagent_coordinator.RoleDispatch(
            role_name="lib",
            workspace_dir=self.test_dir,
            dir_scope="pkg_a",
            ready_targets=("lib/test_unit.py",),
        )
        handle = adapter.dispatch_role(dispatch)
        result = None
        for _ in range(50):
            result = adapter.poll_role(handle)
            if result is not None:
                break
            time.sleep(0.05)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.role, "lib")
        self.assertEqual(result.status, "complete")
        self.assertIn("lib/test_unit.py", result.submitted_targets)


if __name__ == "__main__":
    unittest.main()
