"""Unit tests for mcp_server_impl per its grounding specification."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from typing import Any, Mapping, Optional, Sequence
import unittest
from unittest.mock import patch
from mcp.server.fastmcp import Context
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleScope,
    begin_phase,
    enter_phase,
    system,
)
from update_with_ai.parts.agent.lib.agent_node_config import RoleConfig
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.dag.lib.dag_storage import Change, DagStorage, Feedback, Node
from update_with_ai.parts.dag.lib.dag_subgraph import DagSubgraph
from update_with_ai.parts.mcp.lib.mcp_cache_arbiter import CacheArbiter
from update_with_ai.parts.mcp.lib.mcp_gate import AccessDecision, AccessGate
from update_with_ai.parts.mcp.lib.mcp_server_impl import (
    McpServer,
    __initialize__,
)
from update_with_ai.parts.sandbox.lib.sandbox_run_control import RunController
from update_with_ai.parts.mcp.lib.mcp_session import (
    Active,
    ConversationId,
    Idle,
    RoleAgentSession,
    RoleSessionManager,
    SessionStatus,
)
from update_with_ai.parts.sandbox.lib.tool_provider import (
    ActualParameterBindings,
    IdentityParameterType,
    Parameter,
    Response,
    Tool,
    ToolManager,
)


class DummyTool:
    def __init__(
        self, name: str = "custom_tool", description: str = "A custom tool"
    ) -> None:
        self._name = name
        self._description = description
        self._parameters = {
            Parameter(
                name="target",
                description="Target path",
                parameter_type=IdentityParameterType(str),
                is_required=True,
            ),
            Parameter(
                name="extra",
                description="Extra notes",
                parameter_type=IdentityParameterType(str),
                is_required=False,
                default_value="default_note",
            ),
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> set[Parameter]:
        return self._parameters

    def execute_tool(
        self, actual_parameter_bindings: ActualParameterBindings
    ) -> Response:
        return Response(
            is_failed=False, is_terminated=False, content="Executed DummyTool"
        )


class MockStorage:
    def __init__(self) -> None:
        self.registered_deps: list[Node] = []
        self.cleared_nodes: list[Node] = []
        self.messages: dict[Node, list[Any]] = {}

    def register_dependent(self, node: Node) -> None:
        self.registered_deps.append(node)

    def clear_messages(self, node: Node) -> None:
        self.cleared_nodes.append(node)

    def get_dependents(self, node: Node) -> list[Node]:
        return []

    def add_message(self, msg: Any, to: Node) -> None:
        self.messages.setdefault(to, []).append(msg)


class MockSubgraph:
    def __init__(self) -> None:
        self.visited: list[Node] = []

    def record_visit(self, nodes: Sequence[Node]) -> None:
        self.visited.extend(nodes)


class MockRoleConfig:
    def __init__(self, nodes: Sequence[Node]) -> None:
        self.nodes = tuple(nodes)


class MockRunController:
    def __init__(self, submitted_nodes: set[Node]) -> None:
        self._submitted = submitted_nodes

    def get_node_state(self, node: Node) -> str:
        return "SUBMITTED" if node in self._submitted else "OPEN"

    def is_clean_in_turn(self, node: Node) -> bool:
        return node in self._submitted


class MockHttpRequest:
    def __init__(self, data: Mapping[str, Any]) -> None:
        self._data = data

    async def json(self) -> Mapping[str, Any]:
        return self._data


class MockContext:
    def __init__(self, client_id: str) -> None:
        self.client_id = client_id


class MockRoleSessionManager:
    def __init__(self, registry: Optional[LifecycleRegistry] = None) -> None:
        self.registry = registry
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
        if self.registry is not None:
            scope = begin_phase(agent_session, registry=self.registry)
        else:
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
        self.sessions.pop(conversation_id, None)
        scope = self.scopes.pop(conversation_id, None)
        if scope is not None and hasattr(scope, "close"):
            scope.close()

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
        self.installed_tools: list[Any] = []

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
        self.mock_session_mgr = MockRoleSessionManager(self.registry)
        self.mock_tool_mgr = MockToolManager()
        self.mock_gate = MockAccessGate()
        self.mock_arbiter = MockCacheArbiter()
        self.mock_storage = MockStorage()
        self.mock_subgraph = MockSubgraph()
        self.mock_role_cfg = MockRoleConfig([])
        self.mock_rc = MockRunController(set())

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
        self.registry.register_instance(
            self.mock_storage, keys=[DagStorage], tier=system
        )
        self.registry.register_instance(
            self.mock_subgraph, keys=[DagSubgraph], tier=system
        )
        self.registry.register_instance(
            self.mock_role_cfg, keys=[RoleConfig], tier=agent_session
        )
        self.registry.register_instance(
            self.mock_rc, keys=[RunController], tier=agent_session
        )
        __initialize__(self.registry)

    def test_lifecycle_tools_delegation(self) -> None:
        """CUJ: Register and deregister role agent sub-agents delegating to RoleSessionManager."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            server = sys_scope.get_singleton(McpServer)
            cid = ConversationId("subagent-alpha")

            # Requirement: [McpServer] Exposes a register role agent tool that accepts a role address, a unit root, and an optional conversation identifier, registering the session with the role session manager.
            reg_msg = server.register_role_agent(cid, "code_cleaner", "//pkg:target")
            self.assertIn("Registered role agent", reg_msg)
            self.assertEqual(
                self.mock_session_mgr.registered,
                [(cid, "code_cleaner", "//pkg:target")],
            )

            # Requirement: [McpServer] Exposes a deregister role agent tool that accepts an optional conversation identifier, deregistering the session with the role session manager.
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

            # Requirement: [McpServer] Exposes domain tools from the session tool manager, accepting an optional conversation identifier and routing incoming tool calls to the active session scope for the caller conversation identifier.
            output = server.execute_domain_tool(cid, "get_work", {})
            self.assertIn("No dirty nodes are ready", output)
            self.assertIn("Waiting for upstream tasks.", output)
            self.assertIn(cid, self.mock_session_mgr.touched)
            self.assertIsInstance(self.mock_session_mgr.status_map.get(cid), Idle)

            # Execute get_work with ready tasks to transition status to Active
            self.mock_tool_mgr.responses["get_work"] = Response(
                is_failed=False,
                is_terminated=False,
                content="Assigned 2 dirty nodes.",
            )
            out_active = server.execute_domain_tool(cid, "get_work", {})
            self.assertIn("Assigned 2 dirty nodes", out_active)
            self.assertIsInstance(self.mock_session_mgr.status_map.get(cid), Active)

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

            # Execute submit tool and verify DAG synchronization
            test_node = Node(unit_address="//pkg:unit", role_address="cleaner")
            self.mock_role_cfg.nodes = (test_node,)
            self.mock_rc._submitted = {test_node}

            self.mock_tool_mgr.responses["submit"] = Response(
                is_failed=False,
                is_terminated=False,
                content="Session completed successfully.",
            )
            sub_out = server.execute_domain_tool(
                cid, "submit", {"change_summary": "Cleaned up"}
            )
            self.assertIn("Session completed successfully.", sub_out)
            self.assertEqual(self.mock_storage.cleared_nodes, [test_node])
            self.assertEqual(self.mock_subgraph.visited, [test_node])

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
        async def _run() -> None:
            with enter_phase(system, registry=self.registry) as sys_scope:
                server = sys_scope.get_singleton(McpServer)
                cid1 = ConversationId("active-1")
                cid2 = ConversationId("active-2")

                # Configure mock tool manager with a dynamic tool having required and optional params
                self.mock_tool_mgr.installed_tools = [DummyTool()]

                server.register_role_agent(cid1, "role1", "//pkg:1")
                server.register_role_agent(cid2, "role2", "//pkg:2")
                server.register_role_agent(
                    ConversationId("default"), "default_role", "//pkg:default"
                )

                # Requirement: [McpServer] Starting the server begins the transport loop, and stopping cleanly terminates sessions and endpoints.
                server.start("stdio")
                self.assertTrue(server._running)
                self.assertIsNotNone(server._app)
                assert server._app is not None

                # Allow background cache monitor loop to cycle
                await asyncio.sleep(0.01)

                # Verify dynamic tool export onto FastMCP and execution
                tool_obj = server._app._tool_manager.get_tool("custom_tool")
                self.assertIsNotNone(tool_obj)
                assert tool_obj is not None
                self.assertEqual(tool_obj.name, "custom_tool")
                # Requirement: [McpServer] Exposes domain tools from the session tool manager, accepting an optional conversation identifier and routing incoming tool calls to the active session scope for the caller conversation identifier.
                res_tool = await tool_obj.run({"target": "pkg:1", "extra": "custom", "conversation_id": "active-1"})
                self.assertIn("Executed custom_tool", res_tool)

                # Execute FastMCP lifecycle tools
                # Requirement: [McpServer] Exposes a register role agent tool that accepts a role address, a unit root, and an optional conversation identifier, registering the session with the role session manager.
                reg_tool = server._app._tool_manager.get_tool("register_role_agent")
                assert reg_tool is not None
                res_reg = await reg_tool.run({"role": "role3", "unit_root": "//pkg:3", "conversation_id": "conv-3"})
                self.assertIn("Registered role agent session 'conv-3'", res_reg)

                # Dynamically export tool while server is already running
                server.export_domain_tools([DummyTool(name="runtime_tool")])
                runtime_obj = server._app._tool_manager.get_tool("runtime_tool")
                self.assertIsNotNone(runtime_obj)

                # Requirement: [McpServer] Exposes a deregister role agent tool that accepts an optional conversation identifier, deregistering the session with the role session manager.
                dereg_tool = server._app._tool_manager.get_tool("deregister_role_agent")
                assert dereg_tool is not None
                res_dereg = await dereg_tool.run({"conversation_id": "conv-3"})
                self.assertIn("Deregistered role agent session 'conv-3'", res_dereg)

                # Test direct tool callable with MockContext
                fn = server._create_fastmcp_tool_callable(DummyTool())
                res_ctx = fn(target="pkg:1", ctx=MockContext("active-1"))
                self.assertIn("Executed custom_tool", res_ctx)

                # Test lifecycle FastMCP tools with MockContext
                reg_tool_raw = server._app._tool_manager.get_tool("register_role_agent")
                if reg_tool_raw is not None and hasattr(reg_tool_raw, "fn"):
                    res_reg_ctx = reg_tool_raw.fn(
                        role="role_ctx", unit_root="//pkg:ctx", ctx=MockContext("active-ctx")
                    )
                    self.assertIn("Registered role agent session", res_reg_ctx)

                dereg_tool_raw = server._app._tool_manager.get_tool("deregister_role_agent")
                if dereg_tool_raw is not None and hasattr(dereg_tool_raw, "fn"):
                    res_dereg_ctx = dereg_tool_raw.fn(ctx=MockContext("active-ctx"))
                    self.assertIn("Deregistered role agent session", res_dereg_ctx)

                # Test custom routes
                routes = {r.path: r for r in getattr(server._app, "_custom_starlette_routes", [])}
                if "/validate_access" in routes:
                    req = MockHttpRequest({
                        "conversation_id": "active-1",
                        "tool_name": "view_file",
                        "file_path": "pkg/file.py",
                    })
                    v_resp = await routes["/validate_access"].endpoint(req)
                    self.assertIn(b"is_allowed", v_resp.body)

                if "/filter_dir" in routes:
                    req_f = MockHttpRequest({
                        "conversation_id": "active-1",
                        "directory_path": "pkg",
                        "entries": ["file.py", ".hidden"],
                    })
                    f_resp = await routes["/filter_dir"].endpoint(req_f)
                    self.assertIn(b"entries", f_resp.body)

                # Requirement: [McpServer] Starting the server begins the transport loop and writes the workspace sentinel, updating registered subagents on registration and deregistration, and stopping cleanly terminates sessions, endpoints, and removes the sentinel.
                with tempfile.TemporaryDirectory() as tmpdir:
                    sentinel_path = os.path.join(tmpdir, ".mcp.active")
                    with patch.dict(os.environ, {"CLEANROOM_SENTINEL_PATH": sentinel_path}):
                        server.start("stdio")
                        self.assertTrue(os.path.exists(sentinel_path))
                        with open(sentinel_path, "r") as f:
                            data = json.load(f)
                        self.assertEqual(data["pid"], os.getpid())
                        self.assertEqual(data["port"], 8765)
                        self.assertIn(str(cid1), data["subagents"])
                        self.assertIn(str(cid2), data["subagents"])

                        # Register role agent updates sentinel
                        server.register_role_agent(ConversationId("sub-new"), "role_new", "//pkg:new")
                        with open(sentinel_path, "r") as f:
                            data2 = json.load(f)
                        self.assertIn("sub-new", data2["subagents"])

                        # Deregister role agent updates sentinel
                        server.deregister_role_agent(ConversationId("sub-new"))
                        with open(sentinel_path, "r") as f:
                            data3 = json.load(f)
                        self.assertNotIn("sub-new", data3["subagents"])

                        # Requirement: [McpServer] Exposes a shutdown tool that stops the server and removes the workspace sentinel.
                        shutdown_tool = server._app._tool_manager.get_tool("shutdown")
                        assert shutdown_tool is not None
                        res_shut = await shutdown_tool.run({})
                        self.assertIn("shutting down", res_shut)
                        self.assertFalse(server._running)
                        self.assertFalse(os.path.exists(sentinel_path))

                # Test SSE transport branch
                server.start("sse")

                # Stopping server cleans up all sessions
                server.stop()
                self.assertFalse(server._running)
                self.assertIn(cid1, self.mock_session_mgr.deregistered)
                self.assertIn(cid2, self.mock_session_mgr.deregistered)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
