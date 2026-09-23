from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from update_with_ai.parts.antigravity.lib.antigravity_mcp_client_impl import AntigravityMcpClient


class AntigravityMcpClientImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = AntigravityMcpClient()

    @patch("urllib.request.urlopen")
    def test_call_tool_success(self, mock_urlopen: MagicMock) -> None:
        # Requirement: The antigravity mcp client dispatches a tool name with an arguments mapping to a server port.
        # Requirement: Calling a tool connects to the server at the configured host and port, transmitting a JSON-encoded request specifying tool name and arguments.
        # Requirement: When the server responds with a success status, the client extracts and returns the content text.
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "content": [{"type": "text", "text": "Task assigned successfully."}]
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = self.client.call_tool("get_work", {"conversation_id": "s_1"}, port=8765)
        self.assertEqual(res, "Task assigned successfully.")

    @patch.object(AntigravityMcpClient, "call_tool")
    def test_domain_operations(self, mock_call: MagicMock) -> None:
        # Requirement: Registering a session dispatches the server registration tool binding session identifier, role, and unit.
        # Requirement: Deregistering a session notifies the server to release resources associated with the session.
        # Requirement: Retrieving work invokes the domain get work tool within the session scope, returning task descriptions and incoming change notifications.
        # Requirement: Running check files executes batch verification across all files assigned to the session.
        # Requirement: Submitting commits modifications for an open target with the provided change summary.
        # Requirement: Recording blame flags an upstream defect with an explanation.
        # Requirement: Shutting down sends the server shutdown command.
        # Requirement: Querying the next batch executes the server wave resolution tool for the resolved target unit.
        mock_call.return_value = "OK"

        self.client.register_session("s_1", "//role", "//unit")
        mock_call.assert_called_with("register_role_agent", {"conversation_id": "s_1", "role": "//role", "unit_root": "//unit"}, port=8765)

        self.client.deregister_session("s_1")
        mock_call.assert_called_with("deregister_role_agent", {"conversation_id": "s_1"}, port=8765)

        self.client.get_work("s_1")
        mock_call.assert_called_with("get_work", {"conversation_id": "s_1"}, port=8765)

        self.client.check_files("s_1")
        mock_call.assert_called_with("check_files", {"conversation_id": "s_1"}, port=8765)

        self.client.submit("s_1", "//target", "All tests passed")
        mock_call.assert_called_with("submit", {"conversation_id": "s_1", "target": "//target", "change_summary": "All tests passed"}, port=8765)

        self.client.blame("s_1", "//target", "//failing", "contract mismatch")
        mock_call.assert_called_with("blame", {"conversation_id": "s_1", "target": "//target", "blame_target": "//failing", "explanation": "contract mismatch"}, port=8765)

        self.client.shutdown()
        mock_call.assert_called_with("shutdown", {}, port=8765)

        self.client.next_batch("//pkg:asm_qa")
        mock_call.assert_called_with("next_batch", {"unit_address": "//pkg:asm", "role_address": "//update_python_with_ai:qa"}, port=8765)


if __name__ == "__main__":
    unittest.main()
