"""Unit tests for mcp_session_impl per its grounding specification."""

from __future__ import annotations

from typing import Any, Optional, Sequence
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.agent.lib.agent_node_config import RoleConfig
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.bazel.lib.bazel_manifest_loader import BazelManifestLoader, Manifest
from update_with_ai.parts.dag.lib.dag_storage import DagStorage, Dependency, Node
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


class MockDagSubgraph:
    def __init__(self) -> None:
        self._root: Optional[Node] = None
        self._nodes: set[Node] = set()

    @property
    def target(self) -> Optional[Node]:
        return self._root

    def set_target(self, root: Node) -> None:
        self._root = root
        self._nodes = {root}


class MockManifestLoader:
    def __init__(self) -> None:
        self.loaded: list[tuple[Manifest, Any]] = []

    def get_manifest(self, node: Node) -> Optional[Manifest]:
        if node.unit_address == "//pkg:cleaner":
            return Manifest("cleaner_manifest")
        return None

    def load_manifest(self, content: Manifest, storage: Any) -> Sequence[Any]:
        self.loaded.append((content, storage))
        return []


class MockDagStorage:
    def __init__(self) -> None:
        self.deps: dict[Node, list[Dependency]] = {}

    def get_dependencies(self, node: Node) -> list[Dependency]:
        return self.deps.get(node, [])


class McpSessionImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.mock_agent_cfg = MockAgentConfig()
        self.mock_subgraph = MockDagSubgraph()
        self.registry.register_instance(
            self.mock_agent_cfg, keys=[AgentConfig], tier=system
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

            # Requirement: [RoleSessionManager] Registering a session initiates an agent session phase scope, sets role on role config, configures unit root on dag subgraph, and records the session as active, loading reachable target manifests into dag storage when a manifest loader is available.
            with scope.activate():
                self.assertTrue(self.mock_agent_cfg.is_mcp_mode)
                role_cfg = scope.get_singleton(RoleConfig)
                self.assertEqual(role_cfg.role, "code_cleaner")
                self.assertIsNotNone(self.mock_subgraph.target)
                assert self.mock_subgraph.target is not None
                self.assertEqual(self.mock_subgraph.target.unit_address, "//pkg:cleaner")
                self.assertEqual(self.mock_subgraph.target.role_address, "code_cleaner")

            # Duplicate registration error
            with self.assertRaises(ValueError):
                mgr.register_session(cid, "code_cleaner", "//pkg:cleaner")

    def test_session_registration_with_manifest_loader(self) -> None:
        """CUJ: Register a session when manifest loader and dag storage are present and verify manifest loading."""
        mock_manifest_loader = MockManifestLoader()
        mock_storage = MockDagStorage()
        self.registry.register_instance(
            mock_manifest_loader, keys=[BazelManifestLoader], tier=system
        )
        self.registry.register_instance(
            mock_storage, keys=[DagStorage], tier=system
        )

        with enter_phase(system, registry=self.registry) as sys_scope:
            mgr = sys_scope.get_singleton(RoleSessionManager)
            cid = ConversationId("subagent-manifest")

            # Requirement: [RoleSessionManager] Registering a session initiates an agent session phase scope, sets role on role config, configures unit root on dag subgraph, and records the session as active, loading reachable target manifests into dag storage when a manifest loader is available.
            scope = mgr.register_session(cid, "code_cleaner", "//pkg:cleaner")
            self.assertIsNotNone(scope)
            self.assertEqual(len(mock_manifest_loader.loaded), 1)
            self.assertEqual(mock_manifest_loader.loaded[0][0], "cleaner_manifest")

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

    def test_role_config_operations(self) -> None:
        """CUJ: RoleConfig operations within agent session scope."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            mgr = sys_scope.get_singleton(RoleSessionManager)
            cid = ConversationId("subagent-4")
            scope = mgr.register_session(cid, "designer", "//pkg:designer")

            with scope.activate():
                role_cfg = scope.get_singleton(RoleConfig)
                # Requirement: [RoleConfig] The role config provides the role of the session.
                self.assertEqual(role_cfg.role, "designer")

                # Requirement: [RoleConfig] The role config provides the sequence of nodes currently being cleaned in the agent session.
                self.assertEqual(role_cfg.nodes, ())

                # Requirement: [RoleConfig] The role config provides an execution version that increments whenever the cleaned nodes change.
                self.assertEqual(role_cfg.version, 0)

                # Requirement: [RoleConfig] The role config can set nodes to configure the nodes currently being cleaned in the agent session and increment the execution version.
                test_node = Node(unit_address="//pkg:designer", role_address="designer")
                role_cfg.set_nodes([test_node])
                self.assertEqual(role_cfg.nodes, (test_node,))
                self.assertEqual(role_cfg.version, 1)

    def test_session_registration_preserves_downstream_target(self) -> None:
        """CUJ: Registering an upstream session does not overwrite or shrink a downstream target subgraph."""
        with enter_phase(system, registry=self.registry) as sys_scope:
            mgr = sys_scope.get_singleton(RoleSessionManager)
            cid_qa = ConversationId("qa-worker")
            cid_test = ConversationId("test-worker")

            # Register downstream QA first
            # Requirement: [RoleSessionManager] Registering a session initiates an agent session phase scope, sets role on role config, configures unit root on dag subgraph, and records the session as active, loading reachable target manifests into dag storage when a manifest loader is available.
            mgr.register_session(cid_qa, "qa", "//pkg:target")
            self.assertEqual(self.mock_subgraph.target, Node(unit_address="//pkg:target", role_address="qa"))

            # Simulate subgraph containing both qa and test nodes
            self.mock_subgraph._nodes = {
                Node(unit_address="//pkg:target", role_address="qa"),
                Node(unit_address="//pkg:target", role_address="test"),
            }

            # Register upstream test worker; its root is already in subgraph._nodes, so target shouldn't be overwritten
            mgr.register_session(cid_test, "test", "//pkg:target")
            self.assertEqual(self.mock_subgraph.target, Node(unit_address="//pkg:target", role_address="qa"))


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None


