# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 2795f4333839
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

"""Unit tests for control_attribution_impl."""

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib import agent_node_config, agent_session
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.control.lib import control_attribution
from update_with_ai.parts.control.lib.control_attribution_impl import AttributionCoordinator


class MockDagStorage:
    tier = system

    def __init__(self):
        self._dirty_nodes = set()
        self.dependencies = {}
        self.messages = {}

    def is_dirty(self, node):
        return node in self._dirty_nodes

    def mark_node_clean(self, node, change_description=None):
        self._dirty_nodes.discard(node)

    def mark_node_dirty(self, node):
        self._dirty_nodes.add(node)

    def get_dependencies(self, node):
        return self.dependencies.get(node, set())

    def add_message(self, message, to):
        if to not in self.messages:
            self.messages[to] = []
        self.messages[to].append(message)
        # Adding feedback marks the node dirty per contract
        self._dirty_nodes.add(to)


class ControlAttributionImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.coordinator = AttributionCoordinator()
        self.registry.register_instance(
            self.coordinator,
            keys=[control_attribution.AttributionCoordinator, AttributionCoordinator],
            tier=agent_session.agent_session,
        )
        self.storage = MockDagStorage()
        self.registry.register_instance(
            self.storage,
            keys=[dag_storage.DagStorage],
            tier=system,
        )

    def test_blame_requires_upstream_dependency(self) -> None:
        source = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("foo"),
            role_address=dag_storage.RoleAddress("lib"),
        )
        unrelated = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("bar"),
            role_address=dag_storage.RoleAddress("lib"),
        )
        self.storage.dependencies[source] = set()

        with enter_phase(agent_session.agent_session, registry=self.registry):
            outcome = self.coordinator.blame_target(source, unrelated, "Missing API function.")
            self.assertFalse(outcome.accepted)
            self.assertIn("not an upstream dependency", outcome.message)

    def test_blame_requires_single_paragraph(self) -> None:
        source = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("foo"),
            role_address=dag_storage.RoleAddress("lib"),
        )
        upstream = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("foo"),
            role_address=dag_storage.RoleAddress("low"),
        )
        self.storage.dependencies[source] = {
            dag_storage.DagDependency(node=upstream, is_silent=False)
        }

        with enter_phase(agent_session.agent_session, registry=self.registry):
            outcome = self.coordinator.blame_target(
                source, upstream, "Line 1.\nLine 2 is a separate paragraph."
            )
            self.assertFalse(outcome.accepted)
            self.assertIn("single paragraph without newlines", outcome.message)

    def test_blame_success_and_cascade(self) -> None:
        source = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("foo"),
            role_address=dag_storage.RoleAddress("lib"),
        )
        upstream = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("foo"),
            role_address=dag_storage.RoleAddress("low"),
        )
        dependent = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("foo"),
            role_address=dag_storage.RoleAddress("test"),
        )
        self.storage.dependencies[source] = {
            dag_storage.DagDependency(node=upstream, is_silent=False)
        }
        self.storage.mark_node_clean(upstream)

        with enter_phase(agent_session.agent_session, registry=self.registry):
            outcome = self.coordinator.blame_target(
                source,
                upstream,
                "Type signature missing return annotation.",
                in_batch_dependents=[dependent],
            )
            self.assertTrue(outcome.accepted)
            self.assertTrue(self.storage.is_dirty(upstream))
            self.assertIn(source, outcome.affected_nodes)
            self.assertIn(dependent, outcome.affected_nodes)
            self.assertEqual(len(self.storage.messages[upstream]), 1)

    def test_fail_target(self) -> None:
        target = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("foo"),
            role_address=dag_storage.RoleAddress("lib"),
        )
        with enter_phase(agent_session.agent_session, registry=self.registry):
            outcome = self.coordinator.fail_target(target, "Cannot satisfy constraints.")
            self.assertTrue(outcome.accepted)
            self.assertIn(target, outcome.affected_nodes)


if __name__ == "__main__":
    unittest.main()
