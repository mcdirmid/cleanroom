# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 7567deb21f68
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

"""Unit tests for control_submit_impl."""

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib import agent_node_config, agent_session
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.control.lib import control_submit, control_verification
from update_with_ai.parts.control.lib.control_submit_impl import SubmissionCoordinator


class MockVerificationEvaluator:
    tier = agent_session.agent_session

    def __init__(self, is_passing=True, diagnostic=""):
        self.is_passing = is_passing
        self.diagnostic = diagnostic

    def evaluate_verification(self, target=None):
        return control_verification.VerificationResult(
            passed=self.is_passing,
            diagnostic_output=self.diagnostic,
            is_cached=False,
        )


class MockDagStorage:
    tier = system

    def __init__(self):
        self._dirty_nodes = set()
        self.messages = {}

    def is_dirty(self, node):
        return node in self._dirty_nodes

    def mark_node_clean(self, node, change_description=None):
        self._dirty_nodes.discard(node)

    def mark_node_dirty(self, node):
        self._dirty_nodes.add(node)

    def add_message(self, message, to):
        if to not in self.messages:
            self.messages[to] = []
        self.messages[to].append(message)


class MockNodeConfig:
    tier = agent_session.agent_session

    def __init__(self):
        self.role_definitions = {}


class ControlSubmitImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.coordinator = SubmissionCoordinator()
        self.registry.register_instance(
            self.coordinator,
            keys=[control_submit.SubmissionCoordinator, SubmissionCoordinator],
            tier=agent_session.agent_session,
        )
        self.storage = MockDagStorage()
        self.registry.register_instance(
            self.storage,
            keys=[dag_storage.DagStorage],
            tier=system,
        )
        self.cfg = MockNodeConfig()
        self.registry.register_instance(
            self.cfg,
            keys=[agent_node_config.NodeConfig],
            tier=agent_session.agent_session,
        )

    def test_submit_fails_when_verification_fails(self) -> None:
        verif = MockVerificationEvaluator(is_passing=False, diagnostic="build error")
        self.registry.register_instance(
            verif,
            keys=[control_verification.VerificationEvaluator],
            tier=agent_session.agent_session,
        )

        with enter_phase(agent_session.agent_session, registry=self.registry):
            target = dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress("sample"),
                role_address=dag_storage.RoleAddress("lib"),
            )
            outcome = self.coordinator.submit_target(target, change_summary="Fixed issue", has_modifications=True)
            self.assertFalse(outcome.accepted)
            self.assertIn("Verification is failing", outcome.message)

    def test_submit_change_summary_rules(self) -> None:
        verif = MockVerificationEvaluator(is_passing=True)
        self.registry.register_instance(
            verif,
            keys=[control_verification.VerificationEvaluator],
            tier=agent_session.agent_session,
        )

        with enter_phase(agent_session.agent_session, registry=self.registry):
            target = dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress("sample"),
                role_address=dag_storage.RoleAddress("lib"),
            )
            self.storage.mark_node_dirty(target)

            # Modified files require summary
            outcome1 = self.coordinator.submit_target(target, change_summary=None, has_modifications=True)
            self.assertFalse(outcome1.accepted)
            self.assertIn("change_summary was not provided", outcome1.message)

            # Unmodified files forbid summary
            outcome2 = self.coordinator.submit_target(target, change_summary="Some summary", has_modifications=False)
            self.assertFalse(outcome2.accepted)
            self.assertIn("not permitted when submitting without workspace file modifications", outcome2.message)

            # Valid modified submission
            outcome3 = self.coordinator.submit_target(target, change_summary="Updated config", has_modifications=True)
            self.assertTrue(outcome3.accepted)
            self.assertFalse(self.storage.is_dirty(target))

    def test_submit_auditor_forbids_summary(self) -> None:
        verif = MockVerificationEvaluator(is_passing=True)
        self.registry.register_instance(
            verif,
            keys=[control_verification.VerificationEvaluator],
            tier=agent_session.agent_session,
        )

        with enter_phase(agent_session.agent_session, registry=self.registry):
            target = dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress("sample"),
                role_address=dag_storage.RoleAddress("qa"),
            )
            outcome = self.coordinator.submit_target(target, change_summary="Audit done", has_modifications=False)
            self.assertFalse(outcome.accepted)
            self.assertIn("not permitted for audit nodes", outcome.message)

            outcome_valid = self.coordinator.submit_target(target, change_summary=None, has_modifications=False)
            self.assertTrue(outcome_valid.accepted)


if __name__ == "__main__":
    unittest.main()
