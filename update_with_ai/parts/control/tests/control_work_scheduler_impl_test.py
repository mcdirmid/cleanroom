# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: e33484eb1cf1
# COVERAGE_AUDIT: 2026-10-09T21:19:01Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Unit tests for control_work_scheduler_impl."""

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib import agent_node_config, agent_session
from update_with_ai.parts.dag.lib import dag_storage, dag_subgraph
from update_with_ai.parts.control.lib import control_work_scheduler
from update_with_ai.parts.control.lib.control_work_scheduler_impl import WorkScheduler


class MockDagStorage:
    tier = system

    def __init__(self):
        self.all_nodes = set()
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

    def get_messages(self, node):
        return self.messages.get(node, set())


class MockRoleDef:
    def __init__(self, role_deps=()):
        self.role_deps = role_deps


class MockNodeConfig:
    tier = agent_session.agent_session

    def __init__(self):
        self.role_definitions = {
            "high": MockRoleDef([]),
            "planning": MockRoleDef(["high"]),
            "low": MockRoleDef(["planning"]),
            "lib": MockRoleDef(["low"]),
            "test": MockRoleDef(["lib"]),
        }


class ControlWorkSchedulerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.scheduler = WorkScheduler()
        self.registry.register_instance(
            self.scheduler,
            keys=[control_work_scheduler.WorkScheduler, WorkScheduler],
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

    def test_compute_role_precedence(self) -> None:
        role_deps = {
            "high": [],
            "planning": ["high"],
            "low": ["planning"],
            "lib": ["low"],
            "test": ["lib"],
        }
        ranks = self.scheduler.compute_role_precedence(role_deps)
        self.assertEqual(ranks["high"], 0)
        self.assertEqual(ranks["planning"], 1)
        self.assertEqual(ranks["low"], 2)
        self.assertEqual(ranks["lib"], 3)
        self.assertEqual(ranks["test"], 4)

    def test_schedule_work_directory_scope(self) -> None:
        node_high = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("parts/foo/bar"),
            role_address=dag_storage.RoleAddress("high"),
        )
        node_low = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("parts/foo/bar"),
            role_address=dag_storage.RoleAddress("low"),
        )
        self.storage.all_nodes.add(node_high)
        self.storage.all_nodes.add(node_low)
        self.storage.mark_node_dirty(node_high)
        self.storage.mark_node_dirty(node_low)
        # node_low depends on node_high (which is dirty), so node_low is NOT ready!
        self.storage.dependencies[node_low] = {
            dag_storage.DagDependency(node=node_high, is_silent=False)
        }

        with enter_phase(agent_session.agent_session, registry=self.registry):
            schedule = self.scheduler.schedule_work(dir_scope="parts/foo")
            self.assertEqual(len(schedule.tasks), 1)
            self.assertEqual(schedule.tasks[0].node, node_high)

            # Once node_high is clean, node_low becomes ready!
            self.storage.mark_node_clean(node_high)
            schedule2 = self.scheduler.schedule_work(dir_scope="parts/foo")
            self.assertEqual(len(schedule2.tasks), 1)
            self.assertEqual(schedule2.tasks[0].node, node_low)


if __name__ == "__main__":
    unittest.main()
