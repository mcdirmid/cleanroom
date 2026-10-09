# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T22:40:00Z
# CHANGE: Test unmodified submit with implement message succeeds without summary and feedback requires modification
# CODE_HASH: 3277d25a1988
# COVERAGE_AUDIT: 2026-10-09T21:19:01Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Unit tests for control_submit_impl."""

import unittest
from typing import Optional
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


class MockRoleDef:
    def __init__(self, is_auditor=False, audit_tag=None, src_pattern=""):
        self.is_auditor = is_auditor
        self.audit_tag = audit_tag
        self.src_pattern = src_pattern


class MockNodeConfig:
    tier = agent_session.agent_session

    def __init__(self):
        self.role_definitions = {
            "lib": MockRoleDef(is_auditor=False, src_pattern="{unit_dir}/lib/{unit_name}.py"),
            "qa": MockRoleDef(is_auditor=True, audit_tag="QA_AUDIT", src_pattern=""),
        }
        self.feedback: Optional[list[str]] = None


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
            self.assertNotIn(target, self.storage.messages)

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

    def test_submit_unmodified_with_implement_message_succeeds_without_summary(self) -> None:
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
            self.storage.add_message(
                dag_storage.ChangeMessage(
                    content=dag_storage.MessageContent("Implement task for unit 'sample' in role 'lib'.")
                ),
                to=target,
            )

            # Unmodified implementation node without feedback MUST succeed when submitted without summary
            outcome = self.coordinator.submit_target(target, change_summary=None, has_modifications=False)
            self.assertTrue(outcome.accepted)
            self.assertFalse(self.storage.is_dirty(target))

    def test_submit_unmodified_with_feedback_fails(self) -> None:
        verif = MockVerificationEvaluator(is_passing=True)
        self.registry.register_instance(
            verif,
            keys=[control_verification.VerificationEvaluator],
            tier=agent_session.agent_session,
        )
        self.cfg.feedback = ["Fix syntax error"]

        with enter_phase(agent_session.agent_session, registry=self.registry):
            target = dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress("sample"),
                role_address=dag_storage.RoleAddress("lib"),
            )
            self.storage.mark_node_dirty(target)
            outcome = self.coordinator.submit_target(target, change_summary=None, has_modifications=False)
            self.assertFalse(outcome.accepted)
            self.assertIn("Session feedback is present but no workspace files were modified", outcome.message)


if __name__ == "__main__":
    unittest.main()
