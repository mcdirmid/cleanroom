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

import http.server
import json
import os
import shutil
import sqlite3
import tempfile
import threading
from typing import Any
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.dsh.lib import dsh_telemetry, dsh_telemetry_impl


class MockDshRpcHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_POST(self) -> None:
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8")
        try:
            req_data = json.loads(body)
        except Exception:
            req_data = {}

        method = req_data.get("method") or ""
        payload_args = req_data.get("payload", {}).get("args", {})

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        resp_data: dict[str, Any] = {"type": "server-response", "rpcId": req_data.get("rpcId")}
        if method == "initialize":
            resp_data["result"] = {"ok": True}
        elif method == "workspace/create":
            resp_data["result"] = {"ok": True, "value": {"workspace": {"workspaceId": "ws-mock-123"}}}
        elif method == "session/create":
            req_sid = payload_args.get("request", {}).get("sessionId") or payload_args.get("sessionId") or "mock-sess-created"
            resp_data["result"] = {"ok": True, "value": {"sessionId": req_sid}}
        elif method == "session/prompt":
            resp_data["result"] = {"ok": True, "value": {"accepted": True}, "messageId": "msg-mock-456"}
        elif method == "session/list":
            resp_data["result"] = {
                "ok": True,
                "value": {
                    "items": [
                        {
                            "sessionId": "running-session-1",
                            "cwd": "/mock/cwd",
                            "running": True,
                            "agentAvailable": True,
                            "blank": False,
                            "projections": {
                                "kind": "sequenced",
                                "values": {
                                    "tokenUsage": {"uncachedInputTokens": 100, "cacheReadTokens": 50, "outputTokens": 20},
                                    "turnOutline": [],
                                },
                            },
                        },
                        {
                            "sessionId": "completed-session-1",
                            "cwd": "/mock/cwd",
                            "running": False,
                            "agentAvailable": True,
                            "blank": False,
                            "projections": {
                                "kind": "sequenced",
                                "values": {
                                    "tokenUsage": {"uncachedInputTokens": 200, "cacheReadTokens": 100, "outputTokens": 50},
                                    "turnOutline": [{"turn": 1, "prompt": "Work", "response": "done"}],
                                },
                            },
                        },
                    ]
                },
            }
        elif method == "session/status":
            sid = payload_args.get("sessionId", "")
            if "running" in sid:
                resp_data["result"] = {
                    "status": "running",
                    "usage": {"inputTokens": 100, "cacheReadTokens": 50, "outputTokens": 20},
                }
            elif "error" in sid:
                resp_data["result"] = {
                    "status": "error",
                    "error": "Simulated RPC execution error",
                }
            else:
                resp_data["result"] = {
                    "status": "completed",
                    "usage": {"inputTokens": 200, "cacheReadTokens": 100, "outputTokens": 50},
                }
        else:
            resp_data["result"] = {"ok": True}

        self.wfile.write(json.dumps(resp_data).encode("utf-8"))


class DshTelemetryImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        dsh_telemetry_impl.__initialize__(self.registry)
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.phase_cm.__enter__()

        self.http_server = http.server.HTTPServer(("127.0.0.1", 0), MockDshRpcHandler)
        self.server_port = self.http_server.server_address[1]
        self.server_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        self.server_thread.start()

    def tearDown(self) -> None:
        self.http_server.shutdown()
        self.http_server.server_close()
        self.phase_cm.__exit__(None, None, None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_mock_cookies_db(self, sessions_dir: str, port: int) -> None:
        harness_dir = os.path.dirname(sessions_dir)
        desktop_dir = os.path.dirname(harness_dir)
        os.makedirs(desktop_dir, exist_ok=True)
        cookies_path = os.path.join(desktop_dir, "Cookies")
        conn = sqlite3.connect(cookies_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE cookies (name TEXT, value TEXT, source_port INTEGER, last_access_utc INTEGER)")
        cur.execute(
            "INSERT INTO cookies VALUES ('dsh-auth-session', 'mock-token-xyz', ?, 100000)",
            (port,),
        )
        conn.commit()
        conn.close()

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

    def test_is_desktop_server_available_true(self) -> None:
        """Scenario 5: Evaluates desktop server reachability as True when server is active."""
        sessions_dir = os.path.join(self.test_dir, "harness", "sessions")
        self._create_mock_cookies_db(sessions_dir, self.server_port)
        parser = dsh_telemetry_impl.DshTelemetryParser()
        self.assertTrue(parser.is_desktop_server_available(sessions_dir))

    def test_is_desktop_server_available_false_when_unreachable(self) -> None:
        """Scenario 5: Evaluates desktop server reachability as False when server port is dead."""
        sessions_dir = os.path.join(self.test_dir, "harness", "sessions")
        self._create_mock_cookies_db(sessions_dir, 65530)
        parser = dsh_telemetry_impl.DshTelemetryParser()
        self.assertFalse(parser.is_desktop_server_available(sessions_dir))

    def test_is_desktop_server_available_false_when_no_cookies(self) -> None:
        """Scenario 5: Evaluates desktop server reachability as False when cookies DB does not exist."""
        parser = dsh_telemetry_impl.DshTelemetryParser()
        self.assertFalse(parser.is_desktop_server_available(os.path.join(self.test_dir, "empty", "sessions")))

    def test_dispatch_turn_rpc_success(self) -> None:
        """Scenario 5: Dispatches role turn over RPC bridge and returns valid task handle."""
        sessions_dir = os.path.join(self.test_dir, "harness", "sessions")
        self._create_mock_cookies_db(sessions_dir, self.server_port)
        parser = dsh_telemetry_impl.DshTelemetryParser()
        handle = parser.dispatch_turn_rpc(
            workspace_dir=self.test_dir,
            role_name="lib",
            prompt_text="Implement contracts",
            sessions_dir=sessions_dir,
        )
        self.assertIsNotNone(handle)
        assert handle is not None
        self.assertTrue(handle.startswith("dsh_rpc::"))

    def test_dispatch_turn_rpc_server_unavailable(self) -> None:
        """Scenario 5: Returns None when dispatching role turn to unavailable server."""
        sessions_dir = os.path.join(self.test_dir, "harness", "sessions")
        self._create_mock_cookies_db(sessions_dir, 65530)
        parser = dsh_telemetry_impl.DshTelemetryParser()
        handle = parser.dispatch_turn_rpc(
            workspace_dir=self.test_dir,
            role_name="lib",
            prompt_text="Implement contracts",
            sessions_dir=sessions_dir,
        )
        self.assertIsNone(handle)

    def test_poll_turn_rpc_status_flows(self) -> None:
        """Scenario 6: Polls active, completed, and error turn status records over RPC bridge."""
        sessions_dir = os.path.join(self.test_dir, "harness", "sessions")
        self._create_mock_cookies_db(sessions_dir, self.server_port)
        parser = dsh_telemetry_impl.DshTelemetryParser()

        # 1. Active / running status
        h_run = parser.dispatch_turn_rpc(
            workspace_dir=self.test_dir,
            role_name="lib",
            prompt_text="Work",
            session_id="running-session-1",
            sessions_dir=sessions_dir,
        )
        assert h_run is not None
        st_run = parser.poll_turn_rpc(h_run, sessions_dir=sessions_dir)
        self.assertTrue(st_run.is_active)
        self.assertFalse(st_run.is_completed)
        self.assertIsNotNone(st_run.metrics)
        assert st_run.metrics is not None
        self.assertEqual(st_run.metrics.input_tokens, 100)

        # 2. Completed status
        h_done = parser.dispatch_turn_rpc(
            workspace_dir=self.test_dir,
            role_name="lib",
            prompt_text="Work",
            session_id="completed-session-1",
            sessions_dir=sessions_dir,
        )
        assert h_done is not None
        st_done = parser.poll_turn_rpc(h_done, sessions_dir=sessions_dir)
        self.assertFalse(st_done.is_active)
        self.assertTrue(st_done.is_completed)
        self.assertIsNotNone(st_done.metrics)
        assert st_done.metrics is not None
        self.assertEqual(st_done.metrics.input_tokens, 200)

        # 3. Error status
        h_err = parser.dispatch_turn_rpc(
            workspace_dir=self.test_dir,
            role_name="lib",
            prompt_text="Work",
            session_id="error-session-1",
            sessions_dir=sessions_dir,
        )
        assert h_err is not None
        st_err = parser.poll_turn_rpc(h_err, sessions_dir=sessions_dir)
        self.assertFalse(st_err.is_active)
        self.assertTrue(st_err.is_completed)
        self.assertIn("Simulated RPC execution error", st_err.error or "")

        # 4. Unknown task handle
        st_unk = parser.poll_turn_rpc("invalid_handle", sessions_dir=sessions_dir)
        self.assertFalse(st_unk.is_active)
        self.assertTrue(st_unk.is_completed)
        self.assertIn("Unknown task handle", st_unk.error or "")

