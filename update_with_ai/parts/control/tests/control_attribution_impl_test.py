# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:42:12Z
# CHANGE: Provide dag_storage.DagStorage.add_feedback_message in MockDagStorage and assert FeedbackMessage content/target recording for blame_target and fail_target
# CODE_HASH: 59dab2d386d0
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
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
        self.dirty_reasons = {}
        self.dependencies = {}
        self.messages = {}
        self.feedback_messages = {}

    def is_dirty(self, node):
        return node in self._dirty_nodes

    def mark_node_clean(self, node, change_description=None):
        self._dirty_nodes.discard(node)

    def mark_node_dirty(self, node, reason=None):
        self._dirty_nodes.add(node)
        if reason is not None:
            self.dirty_reasons[node] = reason

    def get_dependencies(self, node):
        return self.dependencies.get(node, set())

    def add_feedback_message(self, node, message):
        if node not in self.feedback_messages:
            self.feedback_messages[node] = []
        self.feedback_messages[node].append(message)
        # Recording feedback marks the target node dirty per dag_storage.DagStorage.is_dirty
        self._dirty_nodes.add(node)

    def add_message(self, message, to):
        if to not in self.messages:
            self.messages[to] = []
        self.messages[to].append(message)


class MockRoleDef:
    def __init__(self, feedback_role_deps):
        self.feedback_role_deps = feedback_role_deps


class MockNodeConfig:
    tier = agent_session.agent_session

    def __init__(self):
        self.role_definitions = {
            "lib": MockRoleDef(feedback_role_deps=[]),
            "spec_qa": MockRoleDef(feedback_role_deps=["planning", "low"]),
            "qa": MockRoleDef(feedback_role_deps=["lib", "test"]),
        }
        self.blame_targets_by_node = {}


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
        self.node_config = MockNodeConfig()
        self.registry.register_instance(
            self.node_config,
            keys=[agent_node_config.NodeConfig],
            tier=agent_session.agent_session,
        )

    def test_blame_requires_upstream_dependency(self) -> None:
        source = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("foo"),
            role_address=dag_storage.RoleAddress("spec_qa"),
        )
        unrelated = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("bar"),
            role_address=dag_storage.RoleAddress("low"),
        )
        self.storage.dependencies[source] = set()

        with enter_phase(agent_session.agent_session, registry=self.registry):
            outcome = self.coordinator.blame_target(source, unrelated, "Missing API function.")
            self.assertFalse(outcome.accepted)
            self.assertIn("not an upstream dependency", outcome.message)

    def test_blame_requires_feedback_configuration(self) -> None:
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
            outcome = self.coordinator.blame_target(source, upstream, "Contract error.")
            self.assertFalse(outcome.accepted)
            self.assertIn("not configured to deliver feedback", outcome.message)

    def test_blame_requires_single_paragraph(self) -> None:
        source = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("foo"),
            role_address=dag_storage.RoleAddress("spec_qa"),
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
            role_address=dag_storage.RoleAddress("spec_qa"),
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
            feedback = self.storage.feedback_messages[upstream]
            self.assertEqual(1, len(feedback))
            self.assertEqual(
                "Type signature missing return annotation.", feedback[0].content
            )
            self.assertEqual(upstream, feedback[0].target)

    def test_fail_target(self) -> None:
        target = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("foo"),
            role_address=dag_storage.RoleAddress("lib"),
        )
        with enter_phase(agent_session.agent_session, registry=self.registry):
            outcome = self.coordinator.fail_target(target, "Cannot satisfy constraints.")
            self.assertTrue(outcome.accepted)
            self.assertIn(target, outcome.affected_nodes)
            feedback = self.storage.feedback_messages[target]
            self.assertEqual(1, len(feedback))
            self.assertIsInstance(feedback[0], dag_storage.FeedbackMessage)
            self.assertEqual("Cannot satisfy constraints.", feedback[0].content)
            self.assertEqual(
                "Cannot satisfy constraints.", self.storage.dirty_reasons[target]
            )
            self.assertTrue(self.storage.is_dirty(target))

    def test_blame_multiple_upstream_targets(self) -> None:
        source = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("foo"),
            role_address=dag_storage.RoleAddress("qa"),
        )
        upstream_lib = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("foo"),
            role_address=dag_storage.RoleAddress("lib"),
        )
        upstream_test = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("foo"),
            role_address=dag_storage.RoleAddress("test"),
        )
        self.storage.dependencies[source] = {
            dag_storage.DagDependency(node=upstream_lib, is_silent=False),
            dag_storage.DagDependency(node=upstream_test, is_silent=False),
        }
        self.storage.mark_node_clean(upstream_lib)
        self.storage.mark_node_clean(upstream_test)

        with enter_phase(agent_session.agent_session, registry=self.registry):
            outcome1 = self.coordinator.blame_target(
                source, upstream_lib, "Lib implementation violates return contract."
            )
            self.assertTrue(outcome1.accepted)
            self.assertTrue(self.storage.is_dirty(upstream_lib))
            self.assertEqual(1, len(self.storage.feedback_messages[upstream_lib]))

            outcome2 = self.coordinator.blame_target(
                source, upstream_test, "Test suite asserts uncontracted property."
            )
            self.assertTrue(outcome2.accepted)
            self.assertTrue(self.storage.is_dirty(upstream_test))
            self.assertEqual(1, len(self.storage.feedback_messages[upstream_test]))

    def test_blame_culprit_file_max_feedback_chars(self) -> None:
        import json
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_ws:
            meta_path = os.path.join(tmp_ws, ".cleanroom_role.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"role_name": "qa", "max_feedback_chars": 50}, f)

            outcome = self.coordinator.blame_culprit_file(
                culprit_file="foo.py",
                critique="A" * 60,
                workspace_root=tmp_ws,
            )
            self.assertFalse(outcome.accepted)
            self.assertIn(
                "Error: Critique exceeds maximum length of 50 characters (60 provided)",
                outcome.message,
            )
            self.assertIn(
                "you might prioritize contract discrepancies to report so the authoring role can make progress.",
                outcome.message,
            )


if __name__ == "__main__":
    unittest.main()
