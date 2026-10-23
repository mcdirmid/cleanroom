"""Unit tests for work_scheduler_impl."""

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib import (
    file_alias,
    node_config,
    agent_session,
)
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib import dag_storage, subgraph
from update_with_ai.parts.control.lib import work_scheduler
from update_with_ai.parts.control.lib.work_scheduler_impl import WorkScheduler


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
    def __init__(self, role_deps=(), src_pattern=""):
        self.role_deps = role_deps
        self.src_pattern = src_pattern


class MockNodeConfig:
    tier = agent_session.agent_session

    def __init__(self):
        self.role_definitions = {
            "high": MockRoleDef([], src_pattern="{unit_dir}/high/{unit_name}.md"),
            "planning": MockRoleDef(["high"], src_pattern="{unit_dir}/planning/{unit_name}.md"),
            "low": MockRoleDef(["planning"], src_pattern="{unit_dir}/low/{unit_name}.pyi"),
            "lib": MockRoleDef(["low"], src_pattern="{unit_dir}/lib/{unit_name}.py"),
            "test": MockRoleDef(["lib"], src_pattern="{unit_dir}/tests/{unit_name}_test.py"),
            "qa": MockRoleDef(["lib", "test"], src_pattern=""),
        }
        self.src_file_alias_by_node = {}
        self.blame_targets_by_node = {}
        self.read_only_files = ()
        self.read_write_files = ()
        self.guide_file = None
        self.is_step_mode = False
        self.guide = None


class ControlWorkSchedulerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.scheduler = WorkScheduler()
        self.registry.register_instance(
            self.scheduler,
            keys=[work_scheduler.WorkScheduler, WorkScheduler],
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
            keys=[node_config.NodeConfig],
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
            # Verifies dependency paths are resolved to file aliases, not raw Bazel targets (parts/foo/bar:high)
            self.assertEqual(schedule2.tasks[0].dependency_paths, ["parts/foo/high/bar.md"])

    def test_format_task_prompt_auditor_avoids_bazel_targets_and_guides_blame(self) -> None:
        node_qa = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("parts/foo:my_widget"),
            role_address=dag_storage.RoleAddress("qa"),
        )
        node_lib = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("parts/foo:my_widget"),
            role_address=dag_storage.RoleAddress("lib"),
        )
        node_test = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("parts/foo:my_widget"),
            role_address=dag_storage.RoleAddress("test"),
        )

        bound_lib = file_alias.BoundFile(
            relative_path=file_alias.RelativePath("parts/foo/lib/my_widget.py"),
            workspace_path=file_paths.WorkspacePath(
                file_paths.PathString("parts/foo/lib/my_widget.py")
            ),
            owning_node=node_lib,
        )
        bound_test = file_alias.BoundFile(
            relative_path=file_alias.RelativePath("parts/foo/tests/my_widget_test.py"),
            workspace_path=file_paths.WorkspacePath(
                file_paths.PathString("parts/foo/tests/my_widget_test.py")
            ),
            owning_node=node_test,
        )
        self.cfg.blame_targets_by_node[node_qa] = {bound_lib, bound_test}

        with enter_phase(agent_session.agent_session, registry=self.registry):
            prompt = self.scheduler.format_task_prompt([node_qa])
            # Verifies blame targets are listed as files
            self.assertIn("parts/foo/lib/my_widget.py", prompt)
            self.assertIn("parts/foo/tests/my_widget_test.py", prompt)
            # Verifies no Bazel target leaks or unit_name hints
            self.assertNotIn("parts/foo:my_widget", prompt)
            self.assertNotIn("//", prompt)
            self.assertNotIn("<unit_name>", prompt)
            self.assertNotIn("<relative_path>/<unit_name>", prompt)
            # Verifies actionable directives for auditor
            self.assertIn("strictly read-only", prompt)
            self.assertIn("blame(target='<culprit_file>'", prompt)


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
