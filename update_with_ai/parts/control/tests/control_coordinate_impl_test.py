"""Unit tests for control_coordinate_impl."""

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib import agent_node_config, agent_session
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.control.lib import (
    control_attribution,
    control_coordinate,
    control_submit,
    control_verification,
    control_work_scheduler,
)
from update_with_ai.parts.control.lib.control_coordinate_impl import SessionCoordinator


class MockVerificationEvaluator:
    tier = agent_session.agent_session

    def evaluate_verification(self, target=None):
        return control_verification.VerificationResult(
            passed=True,
            diagnostic_output="Clean verification",
            is_cached=False,
        )


class MockWorkScheduler:
    tier = agent_session.agent_session

    def schedule_work(self, subgraph=None, dir_scope=None, max_batch_size=None):
        node = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("pkg/unit_a"),
            role_address=dag_storage.RoleAddress("lib"),
        )
        task = control_work_scheduler.ScheduledTask(
            node=node,
            task_prompt="Implement task A",
            dependency_paths=[],
            feedback_messages=[],
        )
        return control_work_scheduler.WorkSchedule(tasks=[task])


class MockSubmissionCoordinator:
    tier = agent_session.agent_session

    def submit_target(self, target_node, change_summary=None, has_modifications=False, in_batch_dependencies=None):
        return control_submit.SubmissionOutcome(accepted=True, message="Target submitted.")


class MockAttributionCoordinator:
    tier = agent_session.agent_session

    def blame_target(self, source_node, blame_target_node, explanation, in_batch_dependencies=None, in_batch_dependents=None):
        return control_attribution.AttributionOutcome(
            accepted=True, message="Blame recorded", affected_nodes=[source_node]
        )

    def fail_target(self, target_node, explanation, in_batch_dependents=None):
        return control_attribution.AttributionOutcome(
            accepted=True, message="Target failed", affected_nodes=[target_node]
        )


class MockDagStorage:
    tier = system

    def get_dependencies(self, node):
        return set()

    def is_dirty(self, node):
        return True


class MockNodeConfig:
    tier = agent_session.agent_session
    read_write_files = []


class ControlCoordinateImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.coordinator = SessionCoordinator()
        self.registry.register_instance(
            self.coordinator,
            keys=[control_coordinate.SessionCoordinator, SessionCoordinator],
            tier=agent_session.agent_session,
        )
        self.registry.register_instance(
            MockVerificationEvaluator(),
            keys=[control_verification.VerificationEvaluator],
            tier=agent_session.agent_session,
        )
        self.registry.register_instance(
            MockWorkScheduler(),
            keys=[control_work_scheduler.WorkScheduler],
            tier=agent_session.agent_session,
        )
        self.registry.register_instance(
            MockSubmissionCoordinator(),
            keys=[control_submit.SubmissionCoordinator],
            tier=agent_session.agent_session,
        )
        self.registry.register_instance(
            MockAttributionCoordinator(),
            keys=[control_attribution.AttributionCoordinator],
            tier=agent_session.agent_session,
        )
        self.registry.register_instance(
            MockDagStorage(),
            keys=[dag_storage.DagStorage],
            tier=system,
        )
        self.registry.register_instance(
            MockNodeConfig(),
            keys=[agent_node_config.NodeConfig],
            tier=agent_session.agent_session,
        )

    def test_node_registration_and_open_targets(self) -> None:
        node = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("parts/foo"),
            role_address=dag_storage.RoleAddress("lib"),
        )
        self.coordinator.register_node(node, alias="lib/foo.py")
        self.assertEqual(len(self.coordinator.open_targets), 1)
        self.assertEqual(self.coordinator.open_targets[0], node)
        self.assertEqual(self.coordinator.get_alias_for_node(node), "lib/foo.py")
        self.assertEqual(self.coordinator.get_node_for_alias("lib/foo.py"), node)
        self.assertEqual(self.coordinator.resolve_default_target(), node)

    def test_dispatch_get_work(self) -> None:
        with enter_phase(agent_session.agent_session, registry=self.registry):
            schedule = self.coordinator.dispatch_get_work(dir_scope="pkg")
            self.assertEqual(len(schedule.tasks), 1)
            self.assertEqual(len(self.coordinator.open_targets), 1)

    def test_dispatch_check_files_all_work(self) -> None:
        with enter_phase(agent_session.agent_session, registry=self.registry):
            self.coordinator.dispatch_get_work(dir_scope="pkg")
            res = self.coordinator.dispatch_check_files()
            self.assertTrue(res.passed)

    def test_dispatch_submit_and_state_transition(self) -> None:
        with enter_phase(agent_session.agent_session, registry=self.registry):
            self.coordinator.dispatch_get_work(dir_scope="pkg")
            outcome = self.coordinator.dispatch_submit(
                change_summary="Fixed", has_modifications=True
            )
            self.assertTrue(outcome.success)
            self.assertEqual(len(self.coordinator.open_targets), 0)


if __name__ == "__main__":
    unittest.main()
