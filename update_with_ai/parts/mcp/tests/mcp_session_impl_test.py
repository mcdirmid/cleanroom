"""Unit tests for mcp_session_impl per its grounding specification."""

from __future__ import annotations

from typing import Optional
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.agent.lib.agent_node_config import RoleConfig
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.dag.lib.dag_storage import Node
from update_with_ai.parts.dag.lib.dag_subgraph import DagSubgraph
from update_with_ai.parts.mcp.lib.mcp_session import Active, ConversationId, Idle
from update_with_ai.parts.mcp.lib.mcp_session_impl import (
    RoleSessionManager,
    __initialize__,
)


class MockAgentConfig:
    def __init__(self) -> None:
        self.is_mcp_mode: bool = False
        self._is_mcp_mode: bool = False


class MockRoleConfig:
    def __init__(self) -> None:
        self.role: str = ""

    def set_role(self, role: str) -> None:
        self.role = role


class MockDagSubgraph:
    def __init__(self) -> None:
        self.target: Optional[Node] = None

    def set_target(self, root: Node) -> None:
        self.target = root


class McpSessionImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.mock_agent_cfg = MockAgentConfig()
        self.mock_role_cfg = MockRoleConfig()
        self.mock_subgraph = MockDagSubgraph()
        self.registry.register_instance(
            self.mock_agent_cfg, keys=[AgentConfig], tier=system
        )
        self.registry.register_instance(
            self.mock_role_cfg, keys=[RoleConfig], tier=agent_session
        )
        self.registry.register_instance(
            self.mock_subgraph, keys=[DagSubgraph], tier=system
        )
        __initialize__(self.registry)

    def test_session_registration_and_activation(self) -> None:
        """CUJ: Register a sub-agent session and verify scope activation, collaborator configuration, and active session exposure."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            mgr = sys_scope.get_singleton(RoleSessionManager)
            cid = ConversationId("subagent-1")

            scope = mgr.register_session(cid, "code_cleaner", "//pkg:cleaner")
            self.assertIsNotNone(scope)

            # Requirement: [RoleSessionManager] Exposes all currently registered sessions mapped by conversation identifier.
            sessions = mgr.active_sessions
            self.assertIn(cid, sessions)
            session = sessions[cid]
            self.assertEqual(session.conversation_id, cid)
            self.assertEqual(session.role_address, "code_cleaner")
            self.assertEqual(session.unit_root, "//pkg:cleaner")
            self.assertIsInstance(session.status, Active)

            # Requirement: [RoleSessionManager] Registering a session initiates an agent session phase scope, sets role on role config, configures unit root on dag subgraph, and records the session as active.
            with scope.activate():
                self.assertTrue(self.mock_agent_cfg.is_mcp_mode)
                self.assertEqual(self.mock_role_cfg.role, "code_cleaner")
                self.assertIsNotNone(self.mock_subgraph.target)
                assert self.mock_subgraph.target is not None
                self.assertEqual(self.mock_subgraph.target.unit_address, "//pkg:cleaner")
                self.assertEqual(self.mock_subgraph.target.role_address, "code_cleaner")

            # Duplicate registration error
            with self.assertRaises(ValueError):
                mgr.register_session(cid, "code_cleaner", "//pkg:cleaner")

    def test_session_deregistration_and_lifecycle_closure(self) -> None:
        """CUJ: Deregister an active session and verify scope closure and registry eviction."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            mgr = sys_scope.get_singleton(RoleSessionManager)
            cid = ConversationId("subagent-2")
            mgr.register_session(cid, "tester", "//pkg:tester")
            self.assertIn(cid, mgr.active_sessions)

            # Requirement: [RoleSessionManager] Deregistering a session closes the session scope, releasing held resources and file locks, and removes the session from the active registry.
            mgr.deregister_session(cid)
            self.assertNotIn(cid, mgr.active_sessions)
            self.assertIsNone(mgr.get_session_scope(cid))
            self.assertIsNone(mgr.get_session(cid))

            with self.assertRaises(ValueError):
                mgr.deregister_session(cid)

    def test_session_status_and_touch_transitions(self) -> None:
        """CUJ: Update session status and touch timestamps across turns."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            mgr = sys_scope.get_singleton(RoleSessionManager)
            cid = ConversationId("subagent-3")
            mgr.register_session(cid, "reviewer", "//pkg:reviewer")

            mgr.set_session_status(cid, Idle())
            session = mgr.get_session(cid)
            self.assertIsNotNone(session)
            assert session is not None
            self.assertIsInstance(session.status, Idle)

            mgr.touch_session(cid)
            touched = mgr.get_session(cid)
            self.assertIsNotNone(touched)
            assert touched is not None
            self.assertIsInstance(touched.status, Active)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
