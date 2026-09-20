"""Unit tests for mcp_server_impl per its grounding specification."""

from __future__ import annotations

import time
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
from update_with_ai.parts.mcp.lib.mcp_cache_arbiter import CacheArbiter
from update_with_ai.parts.mcp.lib.mcp_gate import AccessDecision, AccessGate
from update_with_ai.parts.mcp.lib.mcp_server_impl import (
    McpServer,
    __initialize__,
)
from update_with_ai.parts.mcp.lib.mcp_session import (
    Active,
    ConversationId,
    Idle,
    RoleAgentSession,
    RoleSessionManager,
    SessionStatus,
)
from update_with_ai.parts.sandbox.lib.tool_provider import Response, ToolManager


class MockRoleSessionManager:
    def __init__(self) -> None:
        self.registered: list[tuple[ConversationId, str, str]] = []
        self.deregistered: list[ConversationId] = []
        self.touched: list[ConversationId] = []
        self.scopes: dict[ConversationId, LifecycleScope] = {}
        self.sessions: dict[ConversationId, RoleAgentSession] = {}
        self.status_map: dict[ConversationId, SessionStatus] = {}

    @property
    def active_sessions(self) -> Mapping[ConversationId, RoleAgentSession]:
        return dict(self.sessions)

    def register_session(
        self,
        conversation_id: ConversationId,
        role_address: str,
        unit_root: str,
    ) -> LifecycleScope:
        self.registered.append((conversation_id, role_address, unit_root))
        scope = object.__new__(LifecycleScope)
        self.scopes[conversation_id] = scope
        self.sessions[conversation_id] = RoleAgentSession(
            conversation_id=conversation_id,
            role_address=role_address,
            unit_root=unit_root,
            scope=scope,
            last_active_timestamp=time.time(),
            status=Active(),
        )
        return scope

    def deregister_session(self, conversation_id: ConversationId) -> None:
        self.deregistered.append(conversation_id)
        self.scopes.pop(conversation_id, None)
        self.sessions.pop(conversation_id, None)

    def get_session_scope(
        self, conversation_id: ConversationId
    ) -> Optional[LifecycleScope]:
        return self.scopes.get(conversation_id)

    def touch_session(self, conversation_id: ConversationId) -> None:
        self.touched.append(conversation_id)

    def set_session_status(
        self, conversation_id: ConversationId, status: SessionStatus
    ) -> None:
        self.status_map[conversation_id] = status


class MockToolManager:
    def __init__(self) -> None:
        self.executed: list[tuple[str, Mapping[str, Any]]] = []
        self.responses: dict[str, Response] = {}

    def execute_tool_with_arguments(
        self, name: str, arguments: Mapping[str, Any]
    ) -> Response:
        self.executed.append((name, dict(arguments)))
        if name in self.responses:
            return self.responses[name]
        return Response(
            is_failed=False,
            is_terminated=False,
            content=f"Executed {name}",
        )


class MockAccessGate:
    def __init__(self) -> None:
        self.access_calls: list[tuple[ConversationId, str, str]] = []
        self.filter_calls: list[tuple[ConversationId, str, Sequence[str]]] = []

    def validate_access(
        self,
        conversation_id: ConversationId,
        tool_name: str,
        file_path: str,
    ) -> AccessDecision:
        self.access_calls.append((conversation_id, tool_name, file_path))
        return AccessDecision(is_allowed=True, reason="Authorized")

    def filter_directory_listing(
        self,
        conversation_id: ConversationId,
        directory_path: str,
        entries: Sequence[str],
    ) -> Sequence[str]:
        self.filter_calls.append((conversation_id, directory_path, entries))
        return [e for e in entries if not e.startswith(".")]


class MockCacheArbiter:
    def __init__(self) -> None:
        self.eval_count = 0

    def evaluate_all_idle_sessions(self) -> Sequence[Any]:
        self.eval_count += 1
        return ()


class McpServerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.mock_session_mgr = MockRoleSessionManager()
        self.mock_tool_mgr = MockToolManager()
        self.mock_gate = MockAccessGate()
        self.mock_arbiter = MockCacheArbiter()

        self.registry.register_instance(
            self.mock_session_mgr, keys=[RoleSessionManager], tier=system
        )
        self.registry.register_instance(
            self.mock_tool_mgr, keys=[ToolManager], tier=agent_session
        )
        self.registry.register_instance(
            self.mock_gate, keys=[AccessGate], tier=system
        )
        self.registry.register_instance(
            self.mock_arbiter, keys=[CacheArbiter], tier=system
        )
        __initialize__(self.registry)

    def test_lifecycle_tools_delegation(self) -> None:
        """CUJ: Register and deregister role agent sub-agents delegating to RoleSessionManager."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            server = sys_scope.get_singleton(McpServer)
            cid = ConversationId("subagent-alpha")

            # Requirement: [McpServer] Exposes register and deregister role agent tools that delegate session bounds to the role session manager.
            reg_msg = server.register_role_agent(cid, "code_cleaner", "//pkg:target")
            self.assertIn("Registered role agent", reg_msg)
            self.assertEqual(
                self.mock_session_mgr.registered,
                [(cid, "code_cleaner", "//pkg:target")],
            )

            # Deregister
            dereg_msg = server.deregister_role_agent(cid)
            self.assertIn("Deregistered role agent", dereg_msg)
            self.assertEqual(self.mock_session_mgr.deregistered, [cid])

    def test_domain_tool_execution_routing(self) -> None:
        """CUJ: Dispatch domain tools into caller session scope, tracking activity and idle transitions."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            server = sys_scope.get_singleton(McpServer)
            cid = ConversationId("worker-turn")
            session_scope = begin_phase(agent_session, registry=self.registry)
            self.mock_session_mgr.scopes[cid] = session_scope

            # Configure tool manager response for get_work with idle message
            self.mock_tool_mgr.responses["get_work"] = Response(
                is_failed=False,
                is_terminated=False,
                content="No dirty nodes are ready for cleaning.",
                reminder="Waiting for upstream tasks.",
            )

            # Requirement: [McpServer] Exposes domain tools from the session tool manager, routing incoming tool calls to the active session scope.
            output = server.execute_domain_tool(cid, "get_work", {})
            self.assertIn("No dirty nodes are ready", output)
            self.assertIn("Waiting for upstream tasks.", output)
            self.assertIn(cid, self.mock_session_mgr.touched)
            self.assertIsInstance(self.mock_session_mgr.status_map.get(cid), Idle)

            # Execute another domain tool
            self.mock_tool_mgr.responses["check_file"] = Response(
                is_failed=False,
                is_terminated=False,
                content="Check passed with 0 errors.",
            )
            check_out = server.execute_domain_tool(
                cid, "check_file", {"path": "foo.py"}
            )
            self.assertEqual(check_out, "Check passed with 0 errors.")
            self.assertEqual(
                self.mock_tool_mgr.executed[-1],
                ("check_file", {"path": "foo.py"}),
            )

            # Unregistered session produces error
            err_out = server.execute_domain_tool(
                ConversationId("unregistered"), "submit", {}
            )
            self.assertIn("Error: No active session registered", err_out)

            session_scope.close()

    def test_hook_endpoints_delegation(self) -> None:
        """CUJ: Route hook access validation and directory filtering to AccessGate."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            server = sys_scope.get_singleton(McpServer)
            cid = ConversationId("hook-caller")

            # Requirement: [McpServer] Hosts hook validation and directory filter endpoints, delegating access authorization to the access gate.
            result = server.handle_validate_access(
                cid, "replace_file_content", "pkg/foo.py"
            )
            self.assertEqual(result, {"is_allowed": True, "reason": "Authorized"})
            self.assertEqual(
                self.mock_gate.access_calls,
                [(cid, "replace_file_content", "pkg/foo.py")],
            )

            # Directory filter
            filtered = server.handle_filter_dir(
                cid, "pkg", ["foo.py", ".git", "bar.py"]
            )
            self.assertEqual(filtered, ["foo.py", "bar.py"])
            self.assertEqual(
                self.mock_gate.filter_calls,
                [(cid, "pkg", ["foo.py", ".git", "bar.py"])],
            )

    def test_server_start_and_stop(self) -> None:
        """CUJ: Start server to configure tools and endpoints, and stop server to close all active sessions."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            server = sys_scope.get_singleton(McpServer)
            cid1 = ConversationId("active-1")
            cid2 = ConversationId("active-2")
            server.register_role_agent(cid1, "role1", "//pkg:1")
            server.register_role_agent(cid2, "role2", "//pkg:2")

            # Requirement: [McpServer] Starting the server begins the transport loop, and stopping cleanly terminates sessions and endpoints.
            server.start("stdio")
            self.assertTrue(server._running)
            self.assertIsNotNone(server._app)

            # Stopping server cleans up all sessions
            server.stop()
            self.assertFalse(server._running)
            self.assertIn(cid1, self.mock_session_mgr.deregistered)
            self.assertIn(cid2, self.mock_session_mgr.deregistered)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
