# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:55:00Z
# CHANGE: Author unit tests for dsh_telemetry_impl
# CODE_HASH: 32cb6df4b30a
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Unit tests for dsh_telemetry_impl."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.dsh.lib import dsh_telemetry, dsh_telemetry_impl


class DshTelemetryImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        dsh_telemetry_impl.__initialize__(self.registry)
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.phase_cm.__enter__()

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_parse_stream_text_json(self) -> None:
        stream_sample = (
            '{"type":"session","version":4,"id":"sess-1"}\n'
            '{"type":"assistant/message","data":{"usage":{"inputTokens":1000,"outputTokens":200,"cacheReadTokens":5000,"totalTokens":6200}}}\n'
            '{"type":"assistant/message","data":{"usage":{"inputTokens":500,"outputTokens":100,"cacheReadTokens":2000,"totalTokens":2600}}}\n'
        )
        parser = dsh_telemetry_impl.DshTelemetryParser()
        metrics = parser.parse_stream_text(
            stream_text=stream_sample,
            model_name="DeepSeek-V41-Flash",
        )
        self.assertEqual(metrics.input_tokens, 1500)
        self.assertEqual(metrics.cached_tokens, 7000)
        self.assertEqual(metrics.output_tokens, 300)
        self.assertEqual(metrics.total_tokens, 8800)
        expected_cost = (1500 * 0.00000014) + (7000 * 0.000000014) + (300 * 0.00000028)
        self.assertAlmostEqual(metrics.cost_usd, expected_cost, places=6)

    def test_parse_stream_text_regex_fallback(self) -> None:
        log_sample = (
            "Starting agent run...\n"
            "Input tokens: 2500\n"
            "Cached tokens: 1000\n"
            "Output tokens: 500\n"
            "Finished run cleanly."
        )
        parser = dsh_telemetry_impl.DshTelemetryParser()
        metrics = parser.parse_stream_text(
            stream_text=log_sample,
            model_name="DeepSeek-V41-Flash",
        )
        self.assertEqual(metrics.input_tokens, 2500)
        self.assertEqual(metrics.cached_tokens, 1000)
        self.assertEqual(metrics.output_tokens, 500)
        self.assertEqual(metrics.total_tokens, 4000)

    def test_rate_card_cost_models(self) -> None:
        parser = dsh_telemetry_impl.DshTelemetryParser()
        # Local model: 0.0
        m_local = parser.parse_stream_text("Input tokens: 100\nOutput tokens: 100\n", model_name="qwen-7b")
        self.assertEqual(m_local.cost_usd, 0.0)

        # GPT-4o model
        m_gpt = parser.parse_stream_text("Input tokens: 1000\nOutput tokens: 1000\n", model_name="gpt-4o")
        expected = (1000 * 0.0000025) + (1000 * 0.000010)
        self.assertAlmostEqual(m_gpt.cost_usd, expected, places=6)

        # Opus model
        m_opus = parser.parse_stream_text("Input tokens: 1000\nOutput tokens: 1000\n", model_name="claude-3-opus")
        expected_opus = (1000 * 0.000015) + (1000 * 0.000075)
        self.assertAlmostEqual(m_opus.cost_usd, expected_opus, places=6)

    def test_parse_session_storage_absent_directory(self) -> None:
        parser = dsh_telemetry_impl.DshTelemetryParser()
        metrics = parser.parse_session_storage(
            sessions_dir=os.path.join(self.test_dir, "nonexistent"),
            workspace_dir=self.test_dir,
            model_name="test-model",
        )
        self.assertEqual(metrics.total_tokens, 0)
        self.assertEqual(metrics.model_name, "test-model")

    def test_sync_desktop_session_creates_structure(self) -> None:
        sessions_dir = os.path.join(self.test_dir, "harness", "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        parser = dsh_telemetry_impl.DshTelemetryParser()
        parser.sync_desktop_session(
            sessions_dir=sessions_dir,
            workspace_dir=self.test_dir,
            role_name="lib",
            dir_scope="//pkg",
            start_time=1000.0,
        )
        ws_file = os.path.join(self.test_dir, "harness", "storages", "workspace.json")
        self.assertTrue(os.path.isfile(ws_file))
        with open(ws_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("tables", data)
        self.assertIn("workspaces", data["tables"])
