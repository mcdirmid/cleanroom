"""System integration tests for bazel_mcp_system_asm."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.agent.lib.agent_node_config import RoleConfig, NodeConfig
from update_with_ai.parts.bazel.lib import bazel_asm
from update_with_ai.parts.core.lib import runner_logger_impl
from update_with_ai.parts.core.lib.runner_logger import RunnerLogger
from update_with_ai.parts.dag.lib import dag_asm
from update_with_ai.parts.dag.lib.dag_config import DagConfig
from update_with_ai.parts.dag.lib.dag_storage import DagStorage
from update_with_ai.parts.dag.lib.dag_subgraph import DagSubgraph
from update_with_ai.parts.mcp.lib import mcp_asm
from update_with_ai.parts.mcp.lib.mcp_cache_arbiter import CacheArbiter
from update_with_ai.parts.mcp.lib.mcp_gate import AccessGate
from update_with_ai.parts.mcp.lib.mcp_server import McpServer
from update_with_ai.parts.mcp.lib.mcp_server_impl import McpServer as McpServerImpl
from update_with_ai.parts.mcp.lib.mcp_session import ConversationId, RoleSessionManager
from update_with_ai.parts.sandbox.lib import sandbox_asm
from update_with_ai.parts.sandbox.lib.sandbox import Sandbox
from update_with_ai.parts.sandbox.lib.sandbox_file_editor import EditManager
from update_with_ai.parts.sandbox.lib.sandbox_file_reader import ReadManager
from update_with_ai.parts.sandbox.lib.tool_provider import ToolManager
from update_with_ai.parts.systems.lib import bazel_mcp_system_asm


class BazelMcpSystemAsmTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        bazel_mcp_system_asm.__initialize__(self.registry)

    def test_assembly_constituents(self) -> None:
        """CUJ: Verify assembly constituents are correctly aggregated."""
        self.assertIn(bazel_asm, bazel_mcp_system_asm.CONSTITUENTS)
        self.assertIn(dag_asm, bazel_mcp_system_asm.CONSTITUENTS)
        self.assertIn(mcp_asm, bazel_mcp_system_asm.CONSTITUENTS)
        self.assertIn(runner_logger_impl, bazel_mcp_system_asm.CONSTITUENTS)
        self.assertIn(sandbox_asm, bazel_mcp_system_asm.CONSTITUENTS)

    def test_system_tier_singletons_resolution(self) -> None:
        """CUJ: Verify all system-tier singletons resolve cleanly without missing dependencies."""
        with enter_phase(system, registry=self.registry) as scope:
            # MCP singletons
            mcp_server = scope.get_singleton(McpServer)
            self.assertIsNotNone(mcp_server)
            session_mgr = scope.get_singleton(RoleSessionManager)
            self.assertIsNotNone(session_mgr)
            access_gate = scope.get_singleton(AccessGate)
            self.assertIsNotNone(access_gate)
            cache_arbiter = scope.get_singleton(CacheArbiter)
            self.assertIsNotNone(cache_arbiter)

            # Configuration singletons
            agent_cfg = scope.get_singleton(AgentConfig)
            self.assertIsNotNone(agent_cfg)
            self.assertTrue(agent_cfg.is_mcp_mode)
            dag_cfg = scope.get_singleton(DagConfig)
            self.assertIsNotNone(dag_cfg)
            self.assertEqual(dag_cfg.batch_size, 1)

            # DAG and Storage singletons
            dag_storage = scope.get_singleton(DagStorage)
            self.assertIsNotNone(dag_storage)
            dag_subgraph = scope.get_singleton(DagSubgraph)
            self.assertIsNotNone(dag_subgraph)

            # Logger and Sandbox singletons
            logger = scope.get_singleton(RunnerLogger)
            self.assertIsNotNone(logger)

    def test_session_lifecycle_and_scoped_singletons(self) -> None:
        """CUJ: Register a subagent session and verify session-tier singletons across all subsystems."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            session_mgr = sys_scope.get_singleton(RoleSessionManager)
            cid = ConversationId("antigravity-worker-1")
            scope = session_mgr.register_session(cid, "code_cleaner", "//pkg:cleaner")

            with scope.activate():
                # Verify RoleConfig in session tier
                role_cfg = scope.get_singleton(RoleConfig)
                self.assertEqual(role_cfg.role, "code_cleaner")

                # Verify NodeConfig in session tier
                node_cfg = scope.get_singleton(NodeConfig)
                self.assertIsNotNone(node_cfg)

                # Verify Sandbox and ToolManager in session tier
                sb = scope.get_singleton(Sandbox)
                self.assertIsNotNone(sb)
                tool_mgr = scope.get_singleton(ToolManager)
                self.assertIsNotNone(tool_mgr)

                # Verify ReadManager and EditManager in session tier
                read_mgr = scope.get_singleton(ReadManager)
                self.assertIsNotNone(read_mgr)
                edit_mgr = scope.get_singleton(EditManager)
                self.assertIsNotNone(edit_mgr)

                # Verify can_read and can_write are NOT installed in ToolManager (they are access gate operations),
                # and view_file and replace_file_content are omitted in MCP mode.
                tool_names = [t.name for t in tool_mgr.installed_tools]
                self.assertNotIn("can_read", tool_names)
                self.assertNotIn("can_write", tool_names)
                self.assertNotIn("view_file", tool_names)
                self.assertNotIn("replace_file_content", tool_names)

                # Verify registered domain tools are installed in ToolManager
                self.assertIn("get_work", tool_names)
                self.assertIn("submit", tool_names)
                self.assertIn("check_file", tool_names)
                self.assertIn("fail", tool_names)

            # Deregister and verify cleanup
            session_mgr.deregister_session(cid)
            self.assertNotIn(cid, session_mgr.active_sessions)

    def test_mcp_server_end_to_end_operations(self) -> None:
        """CUJ: Exercise McpServer registration, domain tool execution, access validation, and deregistration."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            mcp_server = sys_scope.get_singleton(McpServerImpl)
            cid = ConversationId("antigravity-worker-e2e")

            # Start MCP server
            mcp_server.start("stdio")
            self.assertTrue(mcp_server._running)
            self.assertIsNotNone(mcp_server._app)
            assert mcp_server._app is not None

            # Register role agent via McpServer
            reg_resp = mcp_server.register_role_agent(cid, "code_cleaner", "//pkg:cleaner")
            self.assertIn("Registered role agent session", reg_resp)

            # Domain tools installed in ToolManager are dynamically exported to FastMCP
            for t_name in ["get_work", "submit", "check_file", "fail"]:
                tool_obj = mcp_server._app._tool_manager.get_tool(t_name)
                self.assertIsNotNone(tool_obj)

            # Native file tools and internal gate operations are NOT exposed as MCP tools
            for non_mcp in ["view_file", "replace_file_content", "can_read", "can_write"]:
                self.assertNotIn(non_mcp, mcp_server._app._tool_manager._tools)

            # Validate access via McpServer
            access_resp = mcp_server.handle_validate_access(cid, "can_read", "pkg/test.py")
            self.assertIn("is_allowed", access_resp)

            # Filter directory via McpServer
            filtered = mcp_server.handle_filter_dir(cid, "pkg", ["test.py", "unrelated.py"])
            self.assertIsInstance(filtered, (list, tuple))

            # Execute domain tool (e.g. get_work) via McpServer
            work_resp = mcp_server.execute_domain_tool(cid, "get_work", {})
            self.assertIsInstance(work_resp, str)

            # Deregister via McpServer
            dereg_resp = mcp_server.deregister_role_agent(cid)
            self.assertIn("Deregistered role agent session", dereg_resp)

            # Stop MCP server
            mcp_server.stop()
            self.assertFalse(mcp_server._running)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
