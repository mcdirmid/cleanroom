"""Empirical unit tests for cleanroom_sandbox_hook.py."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import uuid

from update_with_ai.support.lib import cleanroom_sandbox_hook


class CleanroomSandboxHookEmpiricalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.workspace_dir = os.path.join(self.tmp_dir.name, "workspace")
        self.brain_root = os.path.join(self.tmp_dir.name, "brain")
        os.makedirs(self.workspace_dir, exist_ok=True)
        os.makedirs(self.brain_root, exist_ok=True)

        self.sentinel_path = os.path.join(self.workspace_dir, ".mcp.active")
        self.coordinator_uuid = str(uuid.uuid4())
        self.worker_uuid = str(uuid.uuid4())
        self.human_uuid = str(uuid.uuid4())

        # Register coordinator and worker in brain
        self._register_subagent(
            parent_conv_id=self.human_uuid,
            subagent_conv_id=self.coordinator_uuid,
            type_name="cleanroom_coordinator",
            role="Cleanroom Coordinator",
        )
        self._register_subagent(
            parent_conv_id=self.coordinator_uuid,
            subagent_conv_id=self.worker_uuid,
            type_name="cleanroom_role_worker",
            role="QA Worker",
        )

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _register_subagent(
        self,
        parent_conv_id: str,
        subagent_conv_id: str,
        type_name: str,
        role: str,
    ) -> str:
        subagent_dir = os.path.join(self.brain_root, parent_conv_id, ".system_generated", "subagents")
        os.makedirs(subagent_dir, exist_ok=True)
        desc_path = os.path.join(subagent_dir, f"{subagent_conv_id}.json")
        with open(desc_path, "w", encoding="utf-8") as f:
            json.dump({
                "conversationId": subagent_conv_id,
                "subagentDescriptor": {
                    "typeName": type_name,
                    "role": role,
                },
            }, f)
        return desc_path

    def _make_payload(
        self,
        conversation_id: str,
        tool_name: str,
        args: dict,
    ) -> str:
        return json.dumps({
            "conversationId": conversation_id,
            "toolCall": {
                "name": tool_name,
                "args": args,
            },
            "workspacePaths": [self.workspace_dir],
            "artifactDirectoryPath": os.path.join(self.brain_root, conversation_id),
            "transcriptPath": os.path.join(
                self.brain_root, conversation_id, ".system_generated", "logs", "transcript.jsonl"
            ),
        })

    # --- Mandatory Negative Tests: Worker Attempting Forbidden Commands ---

    def test_worker_run_command_git_status_denied(self) -> None:
        raw_input = self._make_payload(
            self.worker_uuid,
            "run_command",
            {"CommandLine": "git status"},
        )
        decision = cleanroom_sandbox_hook.process_hook_input(
            raw_input,
            sentinel_path=self.sentinel_path,
            brain_roots=[self.brain_root],
        )
        self.assertEqual(decision["decision"], "deny")
        self.assertEqual(
            decision["reason"],
            "Cleanroom security violation: Role workers are strictly forbidden from executing arbitrary shell commands.",
        )

    def test_worker_run_command_unittest_denied(self) -> None:
        raw_input = self._make_payload(
            self.worker_uuid,
            "run_command",
            {"CommandLine": "python3 -m unittest update_with_ai/support/tests/cleanroom_sandbox_hook_test.py"},
        )
        decision = cleanroom_sandbox_hook.process_hook_input(
            raw_input,
            sentinel_path=self.sentinel_path,
            brain_roots=[self.brain_root],
        )
        self.assertEqual(decision["decision"], "deny")
        self.assertEqual(
            decision["reason"],
            "Cleanroom security violation: Role workers are strictly forbidden from executing arbitrary shell commands.",
        )

    def test_worker_run_command_chained_command_denied(self) -> None:
        raw_input = self._make_payload(
            self.worker_uuid,
            "run_command",
            {
                "CommandLine": (
                    "python3 update_with_ai/support/lib/cleanroom_mcp_client.py submit && rm -rf /"
                )
            },
        )
        decision = cleanroom_sandbox_hook.process_hook_input(
            raw_input,
            sentinel_path=self.sentinel_path,
            brain_roots=[self.brain_root],
        )
        self.assertEqual(decision["decision"], "deny")
        self.assertEqual(
            decision["reason"],
            "Cleanroom security violation: Role workers are strictly forbidden from executing arbitrary shell commands.",
        )

    def test_worker_run_command_shell_metacharacters_denied(self) -> None:
        metachar_commands = [
            "python3 update_with_ai/support/lib/cleanroom_mcp_client.py submit; ls",
            "python3 update_with_ai/support/lib/cleanroom_mcp_client.py submit | cat",
            "python3 update_with_ai/support/lib/cleanroom_mcp_client.py submit || ls",
            "python3 update_with_ai/support/lib/cleanroom_mcp_client.py submit > output.txt",
            "python3 update_with_ai/support/lib/cleanroom_mcp_client.py submit < input.txt",
            "python3 update_with_ai/support/lib/cleanroom_mcp_client.py submit $(whoami)",
            "python3 update_with_ai/support/lib/cleanroom_mcp_client.py submit `whoami`",
            "python3 update_with_ai/support/lib/cleanroom_mcp_client.py submit\nls",
        ]
        for cmd in metachar_commands:
            with self.subTest(cmd=cmd):
                raw_input = self._make_payload(self.worker_uuid, "run_command", {"CommandLine": cmd})
                decision = cleanroom_sandbox_hook.process_hook_input(
                    raw_input,
                    sentinel_path=self.sentinel_path,
                    brain_roots=[self.brain_root],
                )
                self.assertEqual(decision["decision"], "deny")
                self.assertIn("Cleanroom security violation", decision["reason"])

    def test_worker_run_command_arbitrary_utilities_denied(self) -> None:
        forbidden = [
            "ls -la",
            "bash -c 'echo pwned'",
            "cat update_with_ai/support/lib/cleanroom_sandbox_hook.py",
            "find . -name '*.py'",
            "grep -rn 'foo' .",
            "python3 -c 'import sys; print(sys.version)'",
            "python3 update_with_ai/support/lib/cleanroom_mcp_client.py",  # missing subcommand
            "python3 update_with_ai/support/lib/cleanroom_mcp_client.py next-batch",  # coordinator only
            "python3 update_with_ai/support/lib/cleanroom_mcp_client.py shutdown",  # coordinator only
        ]
        for cmd in forbidden:
            with self.subTest(cmd=cmd):
                raw_input = self._make_payload(self.worker_uuid, "run_command", {"CommandLine": cmd})
                decision = cleanroom_sandbox_hook.process_hook_input(
                    raw_input,
                    sentinel_path=self.sentinel_path,
                    brain_roots=[self.brain_root],
                )
                self.assertEqual(decision["decision"], "deny")
                self.assertIn("Cleanroom security violation", decision["reason"])

    # --- Mandatory Positive Tests: Whitelisted Worker Commands ---

    def test_worker_run_command_valid_check_files_allowed(self) -> None:
        raw_input = self._make_payload(
            self.worker_uuid,
            "run_command",
            {"CommandLine": "python3 update_with_ai/support/lib/cleanroom_mcp_client.py check-files"},
        )
        decision = cleanroom_sandbox_hook.process_hook_input(
            raw_input,
            sentinel_path=self.sentinel_path,
            brain_roots=[self.brain_root],
        )
        self.assertEqual(decision, {"decision": "allow"})

    def test_worker_run_command_all_valid_subcommands_allowed(self) -> None:
        valid_cmds = [
            'python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session qa register --role "//update_python_with_ai:qa" --unit "//testing/parts/sandbox:sandbox_asm"',
            "python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session qa get-work",
            "python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session qa check-files",
            'python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session qa check-file --file "testing/parts/sandbox/lib/sandbox_asm.py"',
            'python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session qa submit --target "testing/parts/sandbox/lib/sandbox_asm.py" --change-summary "verified"',
            'python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session qa blame --target "testing/parts/sandbox/lib/sandbox_asm.py" --blame-target "upstream.py" --explanation "defect"',
            'python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session qa fail --target "testing/parts/sandbox/lib/sandbox_asm.py" --explanation "test failed"',
            "python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session qa deregister",
        ]
        for cmd in valid_cmds:
            with self.subTest(cmd=cmd):
                raw_input = self._make_payload(self.worker_uuid, "run_command", {"CommandLine": cmd})
                decision = cleanroom_sandbox_hook.process_hook_input(
                    raw_input,
                    sentinel_path=self.sentinel_path,
                    brain_roots=[self.brain_root],
                )
                self.assertEqual(decision, {"decision": "allow"})

    def test_worker_run_command_json_escaped_string_handled(self) -> None:
        # Antigravity sometimes passes arguments with inner JSON escaped quotes
        json_quoted = '"python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session qa check-files"'
        raw_input = self._make_payload(self.worker_uuid, "run_command", {"CommandLine": json_quoted})
        decision = cleanroom_sandbox_hook.process_hook_input(
            raw_input,
            sentinel_path=self.sentinel_path,
            brain_roots=[self.brain_root],
        )
        self.assertEqual(decision, {"decision": "allow"})

    # --- Mandatory Positive Tests: Non-Worker (Coordinator & Human) Permitted ---

    def test_non_worker_coordinator_run_command_git_status_allowed(self) -> None:
        raw_input = self._make_payload(
            self.coordinator_uuid,
            "run_command",
            {"CommandLine": "git status"},
        )
        decision = cleanroom_sandbox_hook.process_hook_input(
            raw_input,
            sentinel_path=self.sentinel_path,
            brain_roots=[self.brain_root],
        )
        self.assertEqual(decision, {"decision": "allow"})

    def test_non_worker_human_run_command_git_status_allowed(self) -> None:
        raw_input = self._make_payload(
            self.human_uuid,
            "run_command",
            {"CommandLine": "git status"},
        )
        decision = cleanroom_sandbox_hook.process_hook_input(
            raw_input,
            sentinel_path=self.sentinel_path,
            brain_roots=[self.brain_root],
        )
        self.assertEqual(decision, {"decision": "allow"})

    def test_non_worker_coordinator_run_command_next_batch_allowed(self) -> None:
        raw_input = self._make_payload(
            self.coordinator_uuid,
            "run_command",
            {"CommandLine": "python3 update_with_ai/support/lib/cleanroom_mcp_client.py next-batch //target:node"},
        )
        decision = cleanroom_sandbox_hook.process_hook_input(
            raw_input,
            sentinel_path=self.sentinel_path,
            brain_roots=[self.brain_root],
        )
        self.assertEqual(decision, {"decision": "allow"})

    # --- Strict File Gating for Workers ---

    def test_worker_file_access_denied_when_server_not_running(self) -> None:
        if os.path.exists(self.sentinel_path):
            os.remove(self.sentinel_path)
        raw_input = self._make_payload(
            self.worker_uuid,
            "replace_file_content",
            {"TargetFile": "/some/file.py"},
        )
        decision = cleanroom_sandbox_hook.process_hook_input(
            raw_input,
            sentinel_path=self.sentinel_path,
            brain_roots=[self.brain_root],
        )
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("Cleanroom MCP server is not running", decision["reason"])

    def test_worker_file_access_denied_when_server_crashed(self) -> None:
        dead_pid = 99999999
        with open(self.sentinel_path, "w") as f:
            json.dump({"pid": dead_pid, "port": 8765, "subagents": ["qa"]}, f)
        raw_input = self._make_payload(
            self.worker_uuid,
            "replace_file_content",
            {"TargetFile": "/some/file.py"},
        )
        decision = cleanroom_sandbox_hook.process_hook_input(
            raw_input,
            sentinel_path=self.sentinel_path,
            brain_roots=[self.brain_root],
        )
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("crashed or is not running", decision["reason"])

    def test_worker_file_access_allowed_for_assigned_target(self) -> None:
        # Register session via run_command
        reg_input = self._make_payload(
            self.worker_uuid,
            "run_command",
            {"CommandLine": "python3 update_with_ai/support/lib/cleanroom_mcp_client.py --session qa register --role //update_python_with_ai:qa --unit //testing:unit"},
        )
        cleanroom_sandbox_hook.process_hook_input(reg_input, sentinel_path=self.sentinel_path, brain_roots=[self.brain_root])

        with open(self.sentinel_path, "w") as f:
            json.dump({"pid": os.getpid(), "port": 8765, "subagents": ["qa"]}, f)

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"is_allowed": True, "reason": "OK"}).encode()
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            raw_input = self._make_payload(
                self.worker_uuid,
                "replace_file_content",
                {"TargetFile": "testing/parts/sandbox/lib/sandbox_asm.py"},
            )
            decision = cleanroom_sandbox_hook.process_hook_input(
                raw_input,
                sentinel_path=self.sentinel_path,
                brain_roots=[self.brain_root],
            )
            self.assertEqual(decision, {"decision": "allow"})

    def test_worker_file_access_denied_for_unassigned_target(self) -> None:
        with open(self.sentinel_path, "w") as f:
            json.dump({"pid": os.getpid(), "port": 8765, "subagents": ["qa"]}, f)

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "is_allowed": False,
            "reason": "Error: update_with_ai/parts/mcp/lib/mcp_server.py is not a read-write file.",
        }).encode()
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            raw_input = self._make_payload(
                self.worker_uuid,
                "replace_file_content",
                {"TargetFile": "update_with_ai/parts/mcp/lib/mcp_server.py"},
            )
            decision = cleanroom_sandbox_hook.process_hook_input(
                raw_input,
                sentinel_path=self.sentinel_path,
                brain_roots=[self.brain_root],
            )
            self.assertEqual(decision["decision"], "deny")
            self.assertIn("not a read-write file", decision["reason"])

    def test_worker_file_access_denied_when_no_active_session_registered(self) -> None:
        with open(self.sentinel_path, "w") as f:
            json.dump({"pid": os.getpid(), "port": 8765, "subagents": []}, f)

        raw_input = self._make_payload(
            self.worker_uuid,
            "replace_file_content",
            {"TargetFile": "testing/parts/sandbox/lib/sandbox_asm.py"},
        )
        decision = cleanroom_sandbox_hook.process_hook_input(
            raw_input,
            sentinel_path=self.sentinel_path,
            brain_roots=[self.brain_root],
        )
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("No active role session registered", decision["reason"])

    def test_non_worker_file_access_allowed_and_cleans_dead_sentinel(self) -> None:
        dead_pid = 99999999
        with open(self.sentinel_path, "w") as f:
            json.dump({"pid": dead_pid, "port": 8765, "subagents": ["qa"]}, f)

        raw_input = self._make_payload(
            self.human_uuid,
            "replace_file_content",
            {"TargetFile": "testing/parts/sandbox/lib/sandbox_asm.py"},
        )
        decision = cleanroom_sandbox_hook.process_hook_input(
            raw_input,
            sentinel_path=self.sentinel_path,
            brain_roots=[self.brain_root],
        )
        self.assertEqual(decision, {"decision": "allow"})
        self.assertFalse(os.path.exists(self.sentinel_path))

    # --- Spawning Control Tests (invoke_subagent) ---

    def test_invoke_subagent_role_worker_denied_for_human(self) -> None:
        raw_input = self._make_payload(
            self.human_uuid,
            "invoke_subagent",
            {"Subagents": [{"TypeName": "cleanroom_role_worker", "Prompt": "do work"}]},
        )
        decision = cleanroom_sandbox_hook.process_hook_input(
            raw_input,
            brain_roots=[self.brain_root],
        )
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("can only be spawned by 'cleanroom_coordinator'", decision["reason"])

    def test_invoke_subagent_role_worker_allowed_for_coordinator(self) -> None:
        raw_input = self._make_payload(
            self.coordinator_uuid,
            "invoke_subagent",
            {"Subagents": [{"TypeName": "cleanroom_role_worker", "Prompt": "do work"}]},
        )
        decision = cleanroom_sandbox_hook.process_hook_input(
            raw_input,
            brain_roots=[self.brain_root],
        )
        self.assertEqual(decision["decision"], "allow")

    # --- CLI Main Execution Test ---

    def test_main_cli_execution_with_stdin_stdout(self) -> None:
        raw_input = self._make_payload(
            self.human_uuid,
            "run_command",
            {"CommandLine": "git status"},
        )
        with patch.dict(os.environ, {"CLEANROOM_SENTINEL_PATH": self.sentinel_path}):
            with patch("sys.stdin", io.StringIO(raw_input)):
                with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                    cleanroom_sandbox_hook.main()
                    out = json.loads(mock_stdout.getvalue())
                    self.assertEqual(out, {"decision": "allow"})


if __name__ == "__main__":
    unittest.main()
