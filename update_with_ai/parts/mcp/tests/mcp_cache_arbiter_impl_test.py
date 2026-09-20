"""Unit tests for mcp_cache_arbiter_impl per its grounding specification."""

from __future__ import annotations

import time
from typing import List, Mapping, Optional, Sequence
import unittest
from support.lib.lifecycle import LifecycleRegistry, LifecycleScope, enter_phase, system
from update_with_ai.parts.dag.lib.dag_storage import Node
from update_with_ai.parts.dag.lib.dag_subgraph import DagSubgraph
from update_with_ai.parts.mcp.lib.mcp_cache_arbiter import (
    ColdCacheRecycle,
    NoRoutingAction,
    WarmCacheWakeup,
)
from update_with_ai.parts.mcp.lib.mcp_cache_arbiter_impl import (
    CacheArbiter,
    __initialize__,
)
from update_with_ai.parts.mcp.lib.mcp_session import (
    Active,
    ConversationId,
    Idle,
    RoleAgentSession,
    RoleSessionManager,
)


class MockDagSubgraph:
    def __init__(self) -> None:
        self.ready_nodes: List[Node] = []

    def next_ready_batch(self) -> List[Node]:
        return list(self.ready_nodes)


class MockRoleSessionManager:
    def __init__(self) -> None:
        self.sessions: dict[ConversationId, RoleAgentSession] = {}

    @property
    def active_sessions(self) -> Mapping[ConversationId, RoleAgentSession]:
        return dict(self.sessions)

    def get_session(
        self, conversation_id: ConversationId
    ) -> Optional[RoleAgentSession]:
        return self.sessions.get(conversation_id)


class McpCacheArbiterImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.mock_subgraph = MockDagSubgraph()
        self.mock_session_mgr = MockRoleSessionManager()
        self.registry.register_instance(
            self.mock_subgraph, keys=[DagSubgraph], tier=system
        )
        self.registry.register_instance(
            self.mock_session_mgr, keys=[RoleSessionManager], tier=system
        )
        __initialize__(self.registry)

    def _create_mock_scope(self) -> LifecycleScope:
        # Minimal empty scope placeholder for test dataclasses
        return object.__new__(LifecycleScope)

    def test_evaluate_session_warm_cache_wakeup(self) -> None:
        """CUJ: Evaluate idle session with ready DAG work and <= 900s elapsed inactivity producing WarmCacheWakeup."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            arbiter = sys_scope.get_singleton(CacheArbiter)
            cid = ConversationId("worker-1")
            session = RoleAgentSession(
                conversation_id=cid,
                role_address="builder",
                unit_root="//pkg:builder",
                scope=self._create_mock_scope(),
                last_active_timestamp=time.time() - 300.0,
                status=Idle(),
            )
            self.mock_session_mgr.sessions[cid] = session
            self.mock_subgraph.ready_nodes = [
                Node(unit_address="//pkg:builder", role_address="builder")
            ]

            # Requirement: [CacheArbiter] Evaluating session readiness produces a warm cache wakeup when ready dirty nodes exist and elapsed inactivity is at most nine hundred seconds.
            action = arbiter.evaluate_session_readiness(cid)
            self.assertIsInstance(action, WarmCacheWakeup)
            assert isinstance(action, WarmCacheWakeup)
            self.assertEqual(action.conversation_id, cid)
            self.assertEqual(action.role_address, "builder")
            self.assertIn("get_work", action.wakeup_prompt)

    def test_evaluate_session_cold_cache_recycle(self) -> None:
        """CUJ: Evaluate idle session with ready DAG work and > 900s elapsed inactivity producing ColdCacheRecycle."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            arbiter = sys_scope.get_singleton(CacheArbiter)
            cid = ConversationId("worker-2")
            session = RoleAgentSession(
                conversation_id=cid,
                role_address="builder",
                unit_root="//pkg:builder",
                scope=self._create_mock_scope(),
                last_active_timestamp=time.time() - 950.0,
                status=Idle(),
            )
            self.mock_session_mgr.sessions[cid] = session
            self.mock_subgraph.ready_nodes = [
                Node(unit_address="//pkg:builder", role_address="builder")
            ]

            # Requirement: [CacheArbiter] Evaluating session readiness produces a cold cache recycle when ready dirty nodes exist and elapsed inactivity exceeds nine hundred seconds.
            action = arbiter.evaluate_session_readiness(cid)
            self.assertIsInstance(action, ColdCacheRecycle)
            assert isinstance(action, ColdCacheRecycle)
            self.assertEqual(action.conversation_id, cid)
            self.assertEqual(action.role_address, "builder")
            self.assertEqual(action.unit_root, "//pkg:builder")
            self.assertIn("expired", action.recycle_prompt)

    def test_evaluate_session_no_routing_conditions(self) -> None:
        """CUJ: Evaluate non-idle, absent, or no-work sessions producing NoRoutingAction."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            arbiter = sys_scope.get_singleton(CacheArbiter)
            cid = ConversationId("worker-active")
            session = RoleAgentSession(
                conversation_id=cid,
                role_address="builder",
                unit_root="//pkg:builder",
                scope=self._create_mock_scope(),
                last_active_timestamp=time.time() - 100.0,
                status=Active(),
            )
            self.mock_session_mgr.sessions[cid] = session
            self.mock_subgraph.ready_nodes = [
                Node(unit_address="//pkg:builder", role_address="builder")
            ]

            # Active session -> No routing
            action_active = arbiter.evaluate_session_readiness(cid)
            self.assertIsInstance(action_active, NoRoutingAction)

            # Idle session with no matching nodes for role -> No routing
            cid_idle = ConversationId("worker-idle-nowork")
            session_idle = RoleAgentSession(
                conversation_id=cid_idle,
                role_address="auditor",
                unit_root="//pkg:auditor",
                scope=self._create_mock_scope(),
                last_active_timestamp=time.time() - 100.0,
                status=Idle(),
            )
            self.mock_session_mgr.sessions[cid_idle] = session_idle
            action_nowork = arbiter.evaluate_session_readiness(cid_idle)
            self.assertIsInstance(action_nowork, NoRoutingAction)

            # Non-existent session -> No routing
            action_unknown = arbiter.evaluate_session_readiness(
                ConversationId("unknown")
            )
            self.assertIsInstance(action_unknown, NoRoutingAction)

    def test_evaluate_all_idle_sessions(self) -> None:
        """CUJ: Collect routing directives across all registered idle sessions with ready tasks."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            arbiter = sys_scope.get_singleton(CacheArbiter)
            cid_warm = ConversationId("worker-warm")
            cid_cold = ConversationId("worker-cold")
            cid_active = ConversationId("worker-running")
            cid_unmatched = ConversationId("worker-unmatched")

            now = time.time()
            self.mock_session_mgr.sessions[cid_warm] = RoleAgentSession(
                conversation_id=cid_warm,
                role_address="builder",
                unit_root="//pkg:builder",
                scope=self._create_mock_scope(),
                last_active_timestamp=now - 200.0,
                status=Idle(),
            )
            self.mock_session_mgr.sessions[cid_cold] = RoleAgentSession(
                conversation_id=cid_cold,
                role_address="builder",
                unit_root="//pkg:builder",
                scope=self._create_mock_scope(),
                last_active_timestamp=now - 1200.0,
                status=Idle(),
            )
            self.mock_session_mgr.sessions[cid_active] = RoleAgentSession(
                conversation_id=cid_active,
                role_address="builder",
                unit_root="//pkg:builder",
                scope=self._create_mock_scope(),
                last_active_timestamp=now - 50.0,
                status=Active(),
            )
            self.mock_session_mgr.sessions[cid_unmatched] = RoleAgentSession(
                conversation_id=cid_unmatched,
                role_address="other_role",
                unit_root="//pkg:other",
                scope=self._create_mock_scope(),
                last_active_timestamp=now - 200.0,
                status=Idle(),
            )

            self.mock_subgraph.ready_nodes = [
                Node(unit_address="//pkg:builder", role_address="builder")
            ]

            # Requirement: [CacheArbiter] Evaluating all idle sessions produces routing actions for all idle sessions with ready work.
            actions = arbiter.evaluate_all_idle_sessions()
            self.assertEqual(len(actions), 2)
            cids = {
                a.conversation_id
                for a in actions
                if isinstance(a, (WarmCacheWakeup, ColdCacheRecycle))
            }
            self.assertEqual(cids, {cid_warm, cid_cold})


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
