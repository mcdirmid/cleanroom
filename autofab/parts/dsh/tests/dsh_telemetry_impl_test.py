"""Unit tests for dsh_telemetry_impl."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from typing import Any
import unittest
from unittest.mock import patch

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from autofab.parts.agent.lib import session as agent_session
from autofab.parts.dsh.lib import dsh_telemetry, dsh_telemetry_impl


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
        m_local = parser.parse_stream_text(
            "Input tokens: 100\nOutput tokens: 100\n", model_name="qwen-7b"
        )
        self.assertEqual(m_local.cost_usd, 0.0)

        # GPT-4o model
        m_gpt = parser.parse_stream_text(
            "Input tokens: 1000\nOutput tokens: 1000\n", model_name="gpt-4o"
        )
        expected = (1000 * 0.0000025) + (1000 * 0.000010)
        self.assertAlmostEqual(m_gpt.cost_usd, expected, places=6)

        # Opus model
        m_opus = parser.parse_stream_text(
            "Input tokens: 1000\nOutput tokens: 1000\n", model_name="claude-3-opus"
        )
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

    @patch("autofab.parts.dsh.lib.dsh_telemetry_impl._call_web_bridge")
    @patch("autofab.parts.dsh.lib.dsh_telemetry_impl._discover_web_bridge")
    def test_is_server_available_true(self, mock_discover: Any, mock_call: Any) -> None:
        """Scenario 5: Evaluates server reachability as True when web bridge is active."""
        mock_discover.return_value = {"url": "http://127.0.0.1:47821", "port": 47821}
        mock_call.return_value = {"content": [{"type": "text", "text": "[]"}]}
        parser = dsh_telemetry_impl.DshTelemetryParser()
        self.assertTrue(parser.is_server_available())

    @patch("autofab.parts.dsh.lib.dsh_telemetry_impl._discover_web_bridge")
    def test_is_server_available_false(self, mock_discover: Any) -> None:
        """Scenario 5: Evaluates server reachability as False when web bridge is unreachable."""
        mock_discover.return_value = None
        parser = dsh_telemetry_impl.DshTelemetryParser()
        self.assertFalse(parser.is_server_available())



    def test_resolve_default_sessions_dir(self) -> None:
        """Verifies _resolve_default_sessions_dir defaults to ~/.dsh/sessions."""
        home = os.path.expanduser("~")
        dsh_cand = os.path.join(home, ".dsh", "sessions")

        with patch.dict(os.environ, {}, clear=True):
            resolved = dsh_telemetry_impl._resolve_default_sessions_dir()
            self.assertEqual(resolved, dsh_cand)

    @patch("autofab.parts.dsh.lib.dsh_telemetry_impl._call_web_bridge")
    @patch("autofab.parts.dsh.lib.dsh_telemetry_impl._discover_web_bridge")
    def test_dispatch_round_rpc_web_ungrouped(
        self, mock_discover: Any, mock_call: Any
    ) -> None:
        """Scenario 7: In Web mode, dispatches role round directly as an ungrouped session labeled [scope] role."""
        mock_discover.return_value = {"url": "http://127.0.0.1:47821", "port": 47821}

        def fake_call(
            bridge: Any, tool_name: str, args: Any, timeout: float = 10.0
        ) -> Any:
            if tool_name == "dsh_spawn":
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"sessionId": "worker-session-456"}),
                        }
                    ]
                }
            return None

        mock_call.side_effect = fake_call

        with patch.dict(os.environ, {"AUTOFAB_DSH_WEB": "1"}, clear=False):
            parser = dsh_telemetry_impl.DshTelemetryParser()
            handle = parser.dispatch_round_rpc(
                workspace_dir=self.test_dir,
                role_name="lib",
                prompt_text="Task work order",
                dir_scope="//ring_buffer",
                model_name="deepseek-flash",
            )
            self.assertIsNotNone(handle)
            self.assertIn("worker-session-456", handle or "")

            # Verify dsh_container was NOT called
            container_calls = [
                c for c in mock_call.call_args_list if c[0][1] == "dsh_container"
            ]
            self.assertEqual(len(container_calls), 0)

            # Verify dsh_spawn received label and no parent_session
            spawn_calls = [
                c for c in mock_call.call_args_list if c[0][1] == "dsh_spawn"
            ]
            self.assertEqual(len(spawn_calls), 1)
            spawn_args = spawn_calls[0][0][2]
            self.assertNotIn("parent_session", spawn_args)
            self.assertEqual(spawn_args.get("label"), "[ring_buffer] lib")
            task_name_1 = spawn_args.get("task_name", "")
            self.assertTrue(task_name_1.startswith("dsh_ring_buffer_lib_"))

            # Verify consecutive dispatches generate globally unique task names
            handle_2 = parser.dispatch_round_rpc(
                workspace_dir=self.test_dir,
                role_name="lib",
                prompt_text="Task work order 2",
                dir_scope="//ring_buffer",
                model_name="deepseek-flash",
            )
            self.assertIsNotNone(handle_2)
            spawn_calls_2 = [
                c for c in mock_call.call_args_list if c[0][1] == "dsh_spawn"
            ]
            self.assertEqual(len(spawn_calls_2), 2)
            task_name_2 = spawn_calls_2[1][0][2].get("task_name", "")
            self.assertNotEqual(task_name_1, task_name_2)

    @patch("autofab.parts.dsh.lib.dsh_telemetry_impl._call_web_bridge")
    @patch("autofab.parts.dsh.lib.dsh_telemetry_impl._discover_web_bridge")
    def test_poll_round_rpc_web_dict_status(
        self, mock_discover: Any, mock_call: Any
    ) -> None:
        """Scenario 6: Polls active round over Web bridge recognizing dict status {completed: ...}."""
        mock_discover.return_value = {"url": "http://127.0.0.1:47821", "port": 47821}
        mock_call.return_value = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        [
                            {
                                "task_name": "worker_task_1",
                                "sessionId": "session-123",
                                "status": {"completed": "Done with all tasks"},
                            }
                        ]
                    ),
                }
            ]
        }
        parser = dsh_telemetry_impl.DshTelemetryParser()
        status = parser.poll_round_rpc("dsh_rpc_web::session-123::worker_task_1")
        self.assertFalse(status.is_active)
        self.assertTrue(status.is_completed)

    @patch("autofab.parts.dsh.lib.dsh_telemetry_impl._call_web_bridge")
    @patch("autofab.parts.dsh.lib.dsh_telemetry_impl._discover_web_bridge")
    def test_poll_round_rpc_web_missing_worker_after_grace_period(
        self, mock_discover: Any, mock_call: Any
    ) -> None:
        """Scenario 6: Missing worker from Web bridge after grace period is marked completed with error."""
        mock_discover.return_value = {"url": "http://127.0.0.1:47821", "port": 47821}
        mock_call.return_value = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        [
                            {
                                "task_name": "other_worker",
                                "sessionId": "session-456",
                                "status": "running",
                            }
                        ]
                    ),
                }
            ]
        }
        parser = dsh_telemetry_impl.DshTelemetryParser()
        task_h = "dsh_rpc_web::session-123::worker_task_1"
        parser._active_rpc_turns[task_h] = {
            "start_time": time.time() - 20.0,
            "workspace_dir": self.test_dir,
        }
        status = parser.poll_round_rpc(task_h)
        self.assertFalse(status.is_active)
        self.assertTrue(status.is_completed)
        self.assertIn("missing", (status.error or "").lower())

    @patch("autofab.parts.dsh.lib.dsh_telemetry_impl._call_web_bridge")
    @patch("autofab.parts.dsh.lib.dsh_telemetry_impl._discover_web_bridge")
    def test_rename_session_web(self, mock_discover: Any, mock_call: Any) -> None:
        """Scenario 8: Renames session over Web bridge via dsh_rename_session."""
        mock_discover.return_value = {"url": "http://127.0.0.1:47821", "port": 47821}
        mock_call.return_value = {"content": [{"type": "text", "text": '{"ok": true}'}]}

        with patch.dict(os.environ, {"AUTOFAB_DSH_WEB": "1"}, clear=False):
            parser = dsh_telemetry_impl.DshTelemetryParser()
            ok = parser.rename_session("sess-1", "[benchmark_1] dead - lib")
            self.assertTrue(ok)
            rename_calls = [
                c for c in mock_call.call_args_list if c[0][1] == "dsh_rename_session"
            ]
            self.assertEqual(len(rename_calls), 1)
            self.assertEqual(
                rename_calls[0][0][2],
                {"sessionId": "sess-1", "title": "[benchmark_1] dead - lib"},
            )

    @patch("autofab.parts.dsh.lib.dsh_telemetry_impl._call_web_bridge")
    @patch("autofab.parts.dsh.lib.dsh_telemetry_impl._discover_web_bridge")
    def test_delete_session_web(self, mock_discover: Any, mock_call: Any) -> None:
        """Scenario 8: Deletes session over Web bridge via dsh_delete_session."""
        mock_discover.return_value = {"url": "http://127.0.0.1:47821", "port": 47821}
        mock_call.return_value = {"content": [{"type": "text", "text": '{"ok": true}'}]}

        with patch.dict(os.environ, {"AUTOFAB_DSH_WEB": "1"}, clear=False):
            parser = dsh_telemetry_impl.DshTelemetryParser()
            ok = parser.delete_session("sess-del-1")
            self.assertTrue(ok)
            del_calls = [
                c for c in mock_call.call_args_list if c[0][1] == "dsh_delete_session"
            ]
            self.assertEqual(len(del_calls), 1)
            self.assertEqual(del_calls[0][0][2], {"sessionId": "sess-del-1"})

    @patch("autofab.parts.dsh.lib.dsh_telemetry_impl._call_web_bridge")
    @patch("autofab.parts.dsh.lib.dsh_telemetry_impl._discover_web_bridge")
    def test_cleanup_scope_sessions_web(
        self, mock_discover: Any, mock_call: Any
    ) -> None:
        """Scenario 8: Cleans up sessions matching [<scope>] over Web bridge."""
        mock_discover.return_value = {"url": "http://127.0.0.1:47821", "port": 47821}

        def fake_bridge_call(
            bridge: Any, tool_name: str, args: Any, timeout: float = 10.0
        ) -> Any:
            if tool_name == "dsh_list_sessions":
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                [
                                    {"sessionId": "s1", "title": "[benchmark_1] lib"},
                                    {
                                        "sessionId": "s2",
                                        "title": "[benchmark_1] dead - pretense",
                                    },
                                    {"sessionId": "s3", "title": "[benchmark_10] lib"},
                                    {"sessionId": "s4", "title": "unrelated session"},
                                ]
                            ),
                        }
                    ]
                }
            if tool_name == "dsh_delete_session":
                return {"content": [{"type": "text", "text": '{"ok": true}'}]}
            return None

        mock_call.side_effect = fake_bridge_call

        with patch.dict(os.environ, {"AUTOFAB_DSH_WEB": "1"}, clear=False):
            parser = dsh_telemetry_impl.DshTelemetryParser()
            cleaned = parser.cleanup_scope_sessions("benchmark_1")
            self.assertEqual(cleaned, 2)
            del_calls = [
                c for c in mock_call.call_args_list if c[0][1] == "dsh_delete_session"
            ]
            self.assertEqual(len(del_calls), 2)
            del_sids = {c[0][2].get("sessionId") for c in del_calls}
            self.assertEqual(del_sids, {"s1", "s2"})

    def test_rename_and_delete_session_filesystem_storage(self) -> None:
        """Requirement: Renames and deletes sessions in filesystem storage fallback."""
        sessions_dir = os.path.join(self.test_dir, "harness", "sessions")
        sess_path = os.path.join(sessions_dir, "ws_1", "sess_desk_1")
        os.makedirs(sess_path, exist_ok=True)
        hdr_path = os.path.join(sess_path, "header.json")
        with open(hdr_path, "w", encoding="utf-8") as f:
            json.dump({"id": "sess_desk_1", "title": "Old Title"}, f)

        parser = dsh_telemetry_impl.DshTelemetryParser()

        # Rename
        renamed = parser.rename_session(
            "sess_desk_1", "[benchmark_5] dead - lib", sessions_dir=sessions_dir
        )
        self.assertTrue(renamed)
        with open(hdr_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data.get("title"), "[benchmark_5] dead - lib")

        # Delete
        deleted = parser.delete_session("sess_desk_1", sessions_dir=sessions_dir)
        self.assertTrue(deleted)
        self.assertFalse(os.path.exists(sess_path))


# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-11-09T23:45:00Z
# CHANGE: Add tests for rename_session, delete_session, and cleanup_scope_sessions
# SPEC_QA_AUDIT: 2026-10-19T22:33:00Z
# --- END CLEANROOM METADATA ---
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
