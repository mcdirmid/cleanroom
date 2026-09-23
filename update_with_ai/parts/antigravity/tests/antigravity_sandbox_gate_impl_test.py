from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from update_with_ai.parts.antigravity.lib.antigravity_sandbox_gate_impl import (
    AntigravitySandboxGate,
)


class AntigravitySandboxGateImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.gate = AntigravitySandboxGate()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_validate_worker_command_whitelisted(self) -> None:
        # Requirement: The antigravity sandbox gate inspects a command line and determines whether execution is permitted.
        # Requirement: Commands executing whitelisted subcommands (`register`, `deregister`, `get-work`, `check-files`, `check-file`, `submit`, `blame`, `fail`) are allowed.
        cmd = "python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session s_1 get-work"
        allowed, reason = self.gate.validate_worker_command(cmd)
        self.assertTrue(allowed)
        self.assertEqual(reason, "")

        cmd2 = "python3 -m update_with_ai.parts.antigravity.lib.antigravity_mcp_client --session s_1 check-files"
        allowed2, reason2 = self.gate.validate_worker_command(cmd2)
        self.assertTrue(allowed2)
        self.assertEqual(reason2, "")

    def test_validate_worker_command_prohibited_patterns(self) -> None:
        # Requirement: Commands containing shell metacharacters or chaining operators are denied.
        for bad_cmd in [
            "python3 cleanroom_mcp_client.py get-work; rm -rf /",
            "python3 cleanroom_mcp_client.py get-work && ls",
            "python3 cleanroom_mcp_client.py get-work | cat",
            "python3 cleanroom_mcp_client.py `whoami`",
            "python3 cleanroom_mcp_client.py $(id)",
        ]:
            allowed, reason = self.gate.validate_worker_command(bad_cmd)
            self.assertFalse(allowed)
            self.assertIn("Cleanroom security violation", reason)

    def test_validate_worker_command_unauthorized_scripts(self) -> None:
        # Requirement: Commands executing unauthorized scripts or missing python binaries are denied.
        bad_cmd = "python3 evil_script.py get-work"
        allowed, reason = self.gate.validate_worker_command(bad_cmd)
        self.assertFalse(allowed)
        self.assertIn("Cleanroom security violation", reason)

        bad_binary = "bash cleanroom_mcp_client.py get-work"
        allowed2, reason2 = self.gate.validate_worker_command(bad_binary)
        self.assertFalse(allowed2)

    @patch("update_with_ai.parts.antigravity.lib.antigravity_sandbox_gate_impl.get_worker_sessions_path")
    def test_save_read_remove_worker_session(self, mock_path: MagicMock) -> None:
        # Requirement: The antigravity sandbox gate associates a worker identifier with a session identifier.
        # Requirement: The antigravity sandbox gate disassociates a worker identifier.
        # Requirement: The antigravity sandbox gate returns all active worker session associations.
        # Requirement: Managing worker sessions records active worker identifiers alongside their assigned session identifiers in an atomic session state file in the workspace root.
        sess_file = os.path.join(self.tmpdir, ".mcp.worker_sessions.json")
        mock_path.return_value = sess_file

        self.assertEqual(self.gate.read_worker_sessions(), {})

        self.gate.save_worker_session("worker-1", "s_10")
        self.assertEqual(self.gate.read_worker_sessions(), {"worker-1": "s_10"})

        self.gate.save_worker_session("worker-2", "s_20")
        self.assertEqual(self.gate.read_worker_sessions(), {"worker-1": "s_10", "worker-2": "s_20"})

        self.gate.remove_worker_session("worker-1")
        self.assertEqual(self.gate.read_worker_sessions(), {"worker-2": "s_20"})

    @patch("update_with_ai.parts.antigravity.lib.antigravity_sandbox_gate_impl.get_caller_descriptor")
    def test_process_hook_input_invoke_subagent_denies_non_coordinator(self, mock_desc: MagicMock) -> None:
        # Requirement: When the tool is `invoke_subagent` spawning a role worker, the gate verifies that the caller is a coordinator subagent, denying unauthorized spawns.
        mock_desc.return_value = {"typeName": "cleanroom_role_worker"}
        payload = json.dumps({
            "conversationId": "worker-1",
            "toolCall": {
                "name": "invoke_subagent",
                "args": {
                    "Subagents": [{"TypeName": "cleanroom_role_worker", "Role": "worker"}]
                },
            },
        })
        decision = self.gate.process_hook_input(payload)
        self.assertEqual(decision.decision, "deny")
        self.assertIn("Cleanroom security violation", decision.reason)

    def test_validate_coordinator_command_whitelisted(self) -> None:
        # Requirement: The antigravity sandbox gate inspects a command line and determines whether coordinator execution is permitted.
        # Requirement: Commands executing whitelisted coordinator subcommands are allowed.
        cmd1 = 'python3 -m update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl step "//testing/parts:asm"'
        allowed1, reason1 = self.gate.validate_coordinator_command(cmd1)
        self.assertTrue(allowed1)
        self.assertEqual(reason1, "")

        cmd2 = "python3 -m update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl register-spawned --mapping c1 s1"
        allowed2, reason2 = self.gate.validate_coordinator_command(cmd2)
        self.assertTrue(allowed2)
        self.assertEqual(reason2, "")

        cmd3 = "python3 -m update_with_ai.parts.antigravity.lib.antigravity_telemetry_impl --format markdown"
        allowed3, reason3 = self.gate.validate_coordinator_command(cmd3)
        self.assertTrue(allowed3)
        self.assertEqual(reason3, "")

    def test_validate_coordinator_command_denied(self) -> None:
        # Requirement: Commands containing shell metacharacters or chaining operators are denied.
        # Requirement: Commands executing unauthorized scripts or missing python binaries are denied.
        denied_cmds = [
            "grep -rn 'check_files' .",
            "ps aux",
            "kill 96744",
            "sed -n '1,10p' file.py",
            "python3 -c 'import sys; print(1)'",
            "python3 -m update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl step '//pkg' && rm -rf /",
        ]
        for cmd in denied_cmds:
            allowed, reason = self.gate.validate_coordinator_command(cmd)
            self.assertFalse(allowed, f"Expected {cmd} to be denied")
            self.assertIn("Cleanroom security violation", reason)

    @patch("update_with_ai.parts.antigravity.lib.antigravity_sandbox_gate_impl.get_caller_descriptor")
    def test_process_hook_input_coordinator_gating(self, mock_desc: MagicMock) -> None:
        # Requirement: When the caller is a coordinator executing `run_command`, the gate validates the command line against a strict coordinator whitelist, denying arbitrary commands, troubleshooting utilities, and file modifications.
        mock_desc.return_value = {"typeName": "cleanroom_coordinator"}

        # File tool denied
        payload_file = json.dumps({
            "conversationId": "coord-1",
            "toolCall": {"name": "replace_file_content", "args": {"TargetFile": "/path"}},
        })
        dec_file = self.gate.process_hook_input(payload_file)
        self.assertEqual(dec_file.decision, "deny")

        # Whitelisted run_command allowed
        payload_run_ok = json.dumps({
            "conversationId": "coord-1",
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": 'python3 -m update_with_ai.parts.antigravity.lib.antigravity_coordinator_impl step "//target"'},
            },
        })
        dec_run_ok = self.gate.process_hook_input(payload_run_ok)
        self.assertEqual(dec_run_ok.decision, "allow")

        # Arbitrary run_command denied
        payload_run_bad = json.dumps({
            "conversationId": "coord-1",
            "toolCall": {"name": "run_command", "args": {"CommandLine": "grep foo bar"}},
        })
        dec_run_bad = self.gate.process_hook_input(payload_run_bad)
        self.assertEqual(dec_run_bad.decision, "deny")


if __name__ == "__main__":
    unittest.main()
