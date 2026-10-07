# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 8cf36b92bdc5
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

"""Unit tests for workspace_work_impl."""

import json
import os
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.control.lib import (
    control_work_scheduler,
    src_metadata,
    src_metadata_impl,
)
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.workspace.lib import (
    workspace_registry,
    workspace_registry_impl,
    workspace_work,
    workspace_work_impl,
)


class MockWorkScheduler:
    tier = agent_session.agent_session

    def __init__(self, tasks=None):
        self.tasks = tasks or []

    def schedule_work(self, subgraph=None, dir_scope=None, max_batch_size=None):
        return control_work_scheduler.WorkSchedule(tasks=self.tasks)


class WorkspaceWorkImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = get_default_registry()
        self.ws_registry = workspace_registry_impl.WorkspaceRegistry()
        self.registry.register_instance(
            self.ws_registry,
            keys=[
                workspace_registry.WorkspaceRegistry,
                workspace_registry_impl.WorkspaceRegistry,
            ],
            tier=agent_session.agent_session,
        )
        self.src_meta = src_metadata_impl.SourceMetadataCoordinator()
        self.registry.register_instance(
            self.src_meta,
            keys=[
                src_metadata.SourceMetadataCoordinator,
                src_metadata_impl.SourceMetadataCoordinator,
            ],
            tier=agent_session.agent_session,
        )
        self.work_mgr = workspace_work_impl.WorkspaceWorkManager()
        self.registry.register_instance(
            self.work_mgr,
            keys=[
                workspace_work.WorkspaceWorkManager,
                workspace_work_impl.WorkspaceWorkManager,
            ],
            tier=agent_session.agent_session,
        )
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.phase_cm.__enter__()

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_pending_work_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as ws_dir:
            self.assertEqual(self.work_mgr.get_pending_work(ws_dir), ())

            p = os.path.join(ws_dir, ".cleanroom_pending_work.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"targets": ["foo.py", "bar.py"]}, f)

            pending = self.work_mgr.get_pending_work(ws_dir)
            self.assertEqual(list(pending), ["foo.py", "bar.py"])

            self.work_mgr.clear_pending_work(ws_dir)
            self.assertEqual(self.work_mgr.get_pending_work(ws_dir), ())

    def test_evaluate_work(self) -> None:
        node = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("scope/lib/foo.py"),
            role_address=dag_storage.RoleAddress("//update_python_with_ai:lib"),
        )
        task = control_work_scheduler.ScheduledTask(
            node=node,
            task_prompt="Implement foo.py",
            dependency_paths=[],
            feedback_messages=[],
        )
        mock_sched = MockWorkScheduler(tasks=[task])
        self.registry.register_instance(
            mock_sched,
            keys=[control_work_scheduler.WorkScheduler],
            tier=agent_session.agent_session,
        )

        with tempfile.TemporaryDirectory() as ws_dir:
            summary = self.work_mgr.evaluate_work(
                dir_scope="scope",
                role_name="lib",
                workspace_dir=ws_dir,
            )
            self.assertFalse(summary.is_clean)
            self.assertEqual(len(summary.ready_items), 1)
            self.assertEqual(summary.ready_items[0].target_file, "scope/lib/foo.py")

            # Pending work file was written
            pending = self.work_mgr.get_pending_work(ws_dir)
            self.assertEqual(list(pending), ["scope/lib/foo.py"])


if __name__ == "__main__":
    unittest.main()
