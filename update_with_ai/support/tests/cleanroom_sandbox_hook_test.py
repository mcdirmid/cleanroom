"""Unit tests for cleanroom_sandbox_hook.py."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from update_with_ai.support.lib import cleanroom_sandbox_hook


class CleanroomSandboxHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.sentinel_path = os.path.join(self.tmp_dir.name, ".mcp.active")

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_is_process_alive(self) -> None:
        self.assertTrue(cleanroom_sandbox_hook.is_process_alive(os.getpid()))
        self.assertFalse(cleanroom_sandbox_hook.is_process_alive(None))
        self.assertFalse(cleanroom_sandbox_hook.is_process_alive(0))
        self.assertFalse(cleanroom_sandbox_hook.is_process_alive(-1))
        # Non-existent large PID
        self.assertFalse(cleanroom_sandbox_hook.is_process_alive(99999999))

    def test_get_sentinel_path_default_and_override(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CLEANROOM_SENTINEL_PATH", None)
            path = cleanroom_sandbox_hook.get_sentinel_path()
            self.assertTrue(path.endswith(".mcp.active"))

        with patch.dict(os.environ, {"CLEANROOM_SENTINEL_PATH": "/custom/path/.mcp.active"}):
            self.assertEqual(cleanroom_sandbox_hook.get_sentinel_path(), "/custom/path/.mcp.active")

    def test_sentinel_missing_allows_fast_path(self) -> None:
        raw_input = json.dumps({
            "conversationId": "subagent-1",
            "toolCall": {"name": "view_file", "args": {"AbsolutePath": "/some/file.py"}},
        })
        decision = cleanroom_sandbox_hook.process_hook_input(raw_input, sentinel_path=self.sentinel_path)
        self.assertEqual(decision, {"decision": "allow"})

    def test_sentinel_unreadable_allows(self) -> None:
        with open(self.sentinel_path, "w") as f:
            f.write("NOT_JSON")
        raw_input = json.dumps({
            "conversationId": "subagent-1",
            "toolCall": {"name": "view_file", "args": {"AbsolutePath": "/some/file.py"}},
        })
        decision = cleanroom_sandbox_hook.process_hook_input(raw_input, sentinel_path=self.sentinel_path)
        self.assertEqual(decision, {"decision": "allow"})

    def test_malformed_input_json_allows(self) -> None:
        with open(self.sentinel_path, "w") as f:
            json.dump({"pid": os.getpid(), "port": 8765, "subagents": ["sub-1"]}, f)
        decision = cleanroom_sandbox_hook.process_hook_input("INVALID_JSON", sentinel_path=self.sentinel_path)
        self.assertEqual(decision, {"decision": "allow"})

    def test_non_subagent_caller_with_live_server_allowed(self) -> None:
        with open(self.sentinel_path, "w") as f:
            json.dump({"pid": os.getpid(), "port": 8765, "subagents": ["subagent-1"]}, f)
        raw_input = json.dumps({
            "conversationId": "pair-programming-conv",
            "toolCall": {"name": "view_file", "args": {"AbsolutePath": "/some/file.py"}},
        })
        decision = cleanroom_sandbox_hook.process_hook_input(raw_input, sentinel_path=self.sentinel_path)
        self.assertEqual(decision, {"decision": "allow"})
        self.assertTrue(os.path.exists(self.sentinel_path))

    def test_non_subagent_caller_with_dead_server_cleans_stale_file(self) -> None:
        dead_pid = 99999999
        with open(self.sentinel_path, "w") as f:
            json.dump({"pid": dead_pid, "port": 8765, "subagents": ["subagent-1"]}, f)
        raw_input = json.dumps({
            "conversationId": "pair-programming-conv",
            "toolCall": {"name": "view_file", "args": {"AbsolutePath": "/some/file.py"}},
        })
        decision = cleanroom_sandbox_hook.process_hook_input(raw_input, sentinel_path=self.sentinel_path)
        self.assertEqual(decision, {"decision": "allow"})
        # Stale file should be cleaned up
        self.assertFalse(os.path.exists(self.sentinel_path))

    def test_registered_subagent_with_dead_server_fails_closed(self) -> None:
        dead_pid = 99999999
        with open(self.sentinel_path, "w") as f:
            json.dump({"pid": dead_pid, "port": 8765, "subagents": ["subagent-1"]}, f)
        raw_input = json.dumps({
            "conversationId": "subagent-1",
            "toolCall": {"name": "view_file", "args": {"AbsolutePath": "/some/file.py"}},
        })
        decision = cleanroom_sandbox_hook.process_hook_input(raw_input, sentinel_path=self.sentinel_path)
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("crashed or is not running", decision["reason"])

    def test_registered_subagent_with_live_server_allowed(self) -> None:
        with open(self.sentinel_path, "w") as f:
            json.dump({"pid": os.getpid(), "port": 8765, "subagents": ["subagent-1"]}, f)

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"is_allowed": True, "reason": "OK"}).encode()
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            raw_input = json.dumps({
                "conversationId": "subagent-1",
                "toolCall": {"name": "view_file", "args": {"AbsolutePath": "/allowed/file.py"}},
            })
            decision = cleanroom_sandbox_hook.process_hook_input(raw_input, sentinel_path=self.sentinel_path)
            self.assertEqual(decision, {"decision": "allow"})

    def test_registered_subagent_with_live_server_denied(self) -> None:
        with open(self.sentinel_path, "w") as f:
            json.dump({"pid": os.getpid(), "port": 8765, "subagents": ["subagent-1"]}, f)

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "is_allowed": False,
            "reason": "Path is outside authorized unit root.",
        }).encode()
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            raw_input = json.dumps({
                "conversationId": "subagent-1",
                "toolCall": {"name": "replace_file_content", "args": {"TargetFile": "/forbidden/file.py"}},
            })
            decision = cleanroom_sandbox_hook.process_hook_input(raw_input, sentinel_path=self.sentinel_path)
            self.assertEqual(decision["decision"], "deny")
            self.assertIn("outside authorized unit root", decision["reason"])

    def test_registered_subagent_with_http_error_fails_closed(self) -> None:
        with open(self.sentinel_path, "w") as f:
            json.dump({"pid": os.getpid(), "port": 8765, "subagents": ["subagent-1"]}, f)

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            raw_input = json.dumps({
                "conversationId": "subagent-1",
                "toolCall": {"name": "view_file", "args": {"AbsolutePath": "/allowed/file.py"}},
            })
            decision = cleanroom_sandbox_hook.process_hook_input(raw_input, sentinel_path=self.sentinel_path)
            self.assertEqual(decision["decision"], "deny")
            self.assertIn("communication error", decision["reason"])

    def test_main_cli_execution(self) -> None:
        raw_input = json.dumps({"conversationId": "pair-1", "toolCall": {"name": "view_file", "args": {}}})
        with patch.dict(os.environ, {"CLEANROOM_SENTINEL_PATH": self.sentinel_path}):
            with patch("sys.stdin", io.StringIO(raw_input)):
                with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                    cleanroom_sandbox_hook.main()
                    out = json.loads(mock_stdout.getvalue())
                    self.assertEqual(out, {"decision": "allow"})

    def test_invoke_subagent_role_worker_denied_for_non_coordinator(self) -> None:
        brain_root = os.path.join(self.tmp_dir.name, "brain")
        os.makedirs(os.path.join(brain_root, "conv-1", ".system_generated", "subagents"), exist_ok=True)
        desc_path = os.path.join(brain_root, "conv-1", ".system_generated", "subagents", "caller-1.json")
        with open(desc_path, "w") as f:
            json.dump({"subagentDescriptor": {"typeName": "research"}}, f)

        raw_input = json.dumps({
            "conversationId": "caller-1",
            "toolCall": {
                "name": "invoke_subagent",
                "args": {
                    "Subagents": [{"TypeName": "cleanroom_role_worker", "Prompt": "do work"}]
                },
            },
        })
        decision = cleanroom_sandbox_hook.process_hook_input(raw_input, brain_roots=[brain_root])
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("can only be spawned by 'cleanroom_coordinator'", decision["reason"])

    def test_invoke_subagent_role_worker_denied_for_main_chat(self) -> None:
        brain_root = os.path.join(self.tmp_dir.name, "brain")
        raw_input = json.dumps({
            "conversationId": "main-chat-conv",
            "toolCall": {
                "name": "invoke_subagent",
                "args": {
                    "Subagents": json.dumps([{"TypeName": "cleanroom_role_worker", "Prompt": "do work"}])
                },
            },
        })
        decision = cleanroom_sandbox_hook.process_hook_input(raw_input, brain_roots=[brain_root])
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("can only be spawned by 'cleanroom_coordinator'", decision["reason"])

    def test_invoke_subagent_role_worker_allowed_for_coordinator(self) -> None:
        brain_root = os.path.join(self.tmp_dir.name, "brain")
        os.makedirs(os.path.join(brain_root, "parent-conv", ".system_generated", "subagents"), exist_ok=True)
        desc_path = os.path.join(brain_root, "parent-conv", ".system_generated", "subagents", "coordinator-1.json")
        with open(desc_path, "w") as f:
            json.dump({"subagentDescriptor": {"typeName": "cleanroom_coordinator"}}, f)

        raw_input = json.dumps({
            "conversationId": "coordinator-1",
            "toolCall": {
                "name": "invoke_subagent",
                "args": {
                    "Subagents": [{"TypeName": "cleanroom_role_worker", "Prompt": "clean"}]
                },
            },
        })
        decision = cleanroom_sandbox_hook.process_hook_input(raw_input, brain_roots=[brain_root])
        self.assertEqual(decision, {"decision": "allow"})

    def test_invoke_subagent_other_types_allowed(self) -> None:
        brain_root = os.path.join(self.tmp_dir.name, "brain")
        raw_input = json.dumps({
            "conversationId": "main-chat-conv",
            "toolCall": {
                "name": "invoke_subagent",
                "args": {
                    "Subagents": [{"TypeName": "cleanroom_coordinator", "Prompt": "clean"}]
                },
            },
        })
        decision = cleanroom_sandbox_hook.process_hook_input(raw_input, brain_roots=[brain_root])
        self.assertEqual(decision, {"decision": "allow"})


if __name__ == "__main__":
    unittest.main()
