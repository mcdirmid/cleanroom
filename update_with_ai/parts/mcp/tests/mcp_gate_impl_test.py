"""Unit tests for mcp_gate_impl per its grounding specification."""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional, Sequence
import unittest
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleScope,
    begin_phase,
    enter_phase,
    system,
)
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.mcp.lib.mcp_gate import AccessDecision
from update_with_ai.parts.mcp.lib.mcp_gate_impl import (
    AccessGate,
    __initialize__,
)
from update_with_ai.parts.mcp.lib.mcp_session import ConversationId, RoleSessionManager
from update_with_ai.parts.sandbox.lib.sandbox_file_editor import EditManager
from update_with_ai.parts.sandbox.lib.sandbox_file_reader import ReadManager
from update_with_ai.parts.sandbox.lib.tool_provider import Response


class MockEditManager:
    def __init__(self) -> None:
        self.write_allowlist: set[str] = set()

    def can_write(self, path: str) -> Response:
        if path in self.write_allowlist:
            return Response(
                is_failed=False,
                is_terminated=False,
                content=f"Modification permitted for '{path}'.",
            )
        return Response(
            is_failed=True,
            is_terminated=False,
            content=f"File '{path}' is not writable.",
        )


class MockReadManager:
    def __init__(self) -> None:
        self.read_allowlist: set[str] = set()

    def can_read(self, path: str) -> Response:
        if path in self.read_allowlist:
            return Response(
                is_failed=False,
                is_terminated=False,
                content=f"Access permitted for '{path}'.",
            )
        return Response(
            is_failed=True,
            is_terminated=False,
            content=f"File '{path}' is not readable.",
        )


class MockRoleSessionManager:
    def __init__(self) -> None:
        self.scopes: dict[ConversationId, LifecycleScope] = {}

    def get_session_scope(
        self, conversation_id: ConversationId
    ) -> Optional[LifecycleScope]:
        return self.scopes.get(conversation_id)


class McpGateImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.mock_session_mgr = MockRoleSessionManager()
        self.mock_edit_mgr = MockEditManager()
        self.mock_read_mgr = MockReadManager()
        self.registry.register_instance(
            self.mock_session_mgr, keys=[RoleSessionManager], tier=system
        )
        self.registry.register_instance(
            self.mock_edit_mgr, keys=[EditManager], tier=agent_session
        )
        self.registry.register_instance(
            self.mock_read_mgr, keys=[ReadManager], tier=agent_session
        )
        __initialize__(self.registry)

    def test_validate_access_allowed_and_denied(self) -> None:
        """CUJ: Validate tool permissions inside session scope for write and read tools."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            gate = sys_scope.get_singleton(AccessGate)
            cid = ConversationId("agent-gate-1")
            session_scope = begin_phase(agent_session, registry=self.registry)
            self.mock_session_mgr.scopes[cid] = session_scope

            self.mock_edit_mgr.write_allowlist.add("src/target.py")
            self.mock_read_mgr.read_allowlist.add("src/target.pyi")

            # Requirement: [AccessGate] Validating access resolves tool permissions for the conversation and target file path, producing an access decision.
            decision = gate.validate_access(cid, "replace_file_content", "src/target.py")
            self.assertTrue(decision.is_allowed)
            self.assertTrue(decision.reason)

            # Write tool denied
            decision_denied = gate.validate_access(cid, "write_to_file", "src/other.py")
            self.assertFalse(decision_denied.is_allowed)
            self.assertTrue(decision_denied.reason)

            # Read tool allowed
            decision_read = gate.validate_access(cid, "view_file", "src/target.pyi")
            self.assertTrue(decision_read.is_allowed)

            # Read tool denied
            decision_read_denied = gate.validate_access(cid, "view_file", "src/unreadable.py")
            self.assertFalse(decision_read_denied.is_allowed)
            self.assertTrue(decision_read_denied.reason)

            session_scope.close()

    def test_validate_access_boundary_rejections(self) -> None:
        """CUJ: Verify access rejection for unknown sessions, outside paths, and unhandled tools."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            gate = sys_scope.get_singleton(AccessGate)
            cid = ConversationId("registered-agent")
            session_scope = begin_phase(agent_session, registry=self.registry)
            self.mock_session_mgr.scopes[cid] = session_scope

            # Unknown conversation
            # Requirement: [AccessGate] Validating access resolves tool permissions for the conversation and target file path, producing an access decision.
            decision_no_session = gate.validate_access(
                ConversationId("unknown"), "view_file", "src/target.pyi"
            )
            self.assertFalse(decision_no_session.is_allowed)
            self.assertTrue(decision_no_session.reason)

            # Unhandled tool
            decision_bad_tool = gate.validate_access(cid, "bash_exec", "src/target.py")
            self.assertFalse(decision_bad_tool.is_allowed)
            self.assertTrue(decision_bad_tool.reason)

            # Path outside workspace (relative)
            decision_traversal = gate.validate_access(
                cid, "view_file", "../outside_workspace.txt"
            )
            self.assertFalse(decision_traversal.is_allowed)

            # Path outside workspace (absolute)
            decision_abs_outside = gate.validate_access(
                cid, "view_file", "/var/outside_workspace.txt"
            )
            self.assertFalse(decision_abs_outside.is_allowed)

            # Path inside workspace (absolute)
            abs_inside = os.path.join(os.getcwd(), "src/target.py")
            self.mock_edit_mgr.write_allowlist.add("src/target.py")
            decision_abs_inside = gate.validate_access(
                cid, "write_to_file", abs_inside
            )
            self.assertTrue(decision_abs_inside.is_allowed)

            session_scope.close()

    def test_filter_directory_listing(self) -> None:
        """CUJ: Filter directory listing child entries against read permissions preserving role blindness."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            gate = sys_scope.get_singleton(AccessGate)
            cid = ConversationId("agent-filter")
            session_scope = begin_phase(agent_session, registry=self.registry)
            self.mock_session_mgr.scopes[cid] = session_scope

            self.mock_read_mgr.read_allowlist.add("src/visible.pyi")
            self.mock_read_mgr.read_allowlist.add("src/visible.py")

            entries = [
                "visible.pyi",
                "visible.py",
                "secret.py",
                "hidden.py",
                "../../escape.py",
                "/etc/outside.py",
            ]

            # Requirement: [AccessGate] Filtering directory listings sanitizes child entries for the conversation and target directory path, preserving role blindness.
            filtered = gate.filter_directory_listing(cid, "src", entries)
            self.assertEqual(filtered, ("visible.pyi", "visible.py"))

            # Unknown session fails closed
            empty_filtered = gate.filter_directory_listing(
                ConversationId("unknown"), "src", entries
            )
            self.assertEqual(empty_filtered, ())

            session_scope.close()


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
