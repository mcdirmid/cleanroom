# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T18:24:00Z
# CHANGE: test template materialization in evaluate_work and compute_role_work_queue
# CODE_HASH: 481bc1d5e06a
# COVERAGE_AUDIT: 2026-10-07T23:58:18Z
# QA_AUDIT: 2026-10-07T23:58:18Z
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
)
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.workspace.lib import (
    workspace_registry,
    workspace_work,
    workspace_work_impl,
)


class MockWorkScheduler:
    tier = agent_session.agent_session

    def __init__(self, tasks=None):
        self.tasks = tasks or []

    def schedule_work(self, subgraph=None, dir_scope=None, max_batch_size=None):
        return control_work_scheduler.WorkSchedule(tasks=self.tasks)


class MockDagStorage:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.materialized: list[dag_storage.DagNode] = []

    def materialize_template(self, node: dag_storage.DagNode) -> None:
        self.materialized.append(node)


class WorkspaceWorkImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = get_default_registry()
        self.mock_storage = MockDagStorage()
        self.registry.register_instance(
            self.mock_storage,
            keys=[dag_storage.DagStorage],
            tier=agent_session.agent_session,
        )
        self.ws_registry = workspace_registry._DefaultWorkspaceRegistry()
        self.registry.register_instance(
            self.ws_registry,
            keys=[
                workspace_registry.WorkspaceRegistry,
            ],
            tier=agent_session.agent_session,
        )
        self.src_meta = src_metadata._DefaultSourceMetadataCoordinator()
        self.registry.register_instance(
            self.src_meta,
            keys=[
                src_metadata.SourceMetadataCoordinator,
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
            self.assertIn(node, self.mock_storage.materialized)

    def test_resolve_contract_files(self) -> None:
        with tempfile.TemporaryDirectory() as ws_dir:
            part_dir = os.path.join(ws_dir, "staging/parts/testpkg")
            os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
            os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)

            low_spec = os.path.join(part_dir, "low/widget_impl.pyi")
            low_iface = os.path.join(part_dir, "low/widget.pyi")
            lib_iface = os.path.join(part_dir, "lib/widget.py")
            lib_impl = os.path.join(part_dir, "lib/widget_impl.py")

            for fpath in (low_spec, low_iface, lib_iface, lib_impl):
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("# test\n")

            contracts = self.work_mgr.resolve_contract_files(
                "staging/parts/testpkg/lib/widget_impl.py",
                ws_dir,
                role_name="lib",
            )
            self.assertIn("staging/parts/testpkg/low/widget_impl.pyi", contracts)
            self.assertIn("staging/parts/testpkg/low/widget.pyi", contracts)
            self.assertNotIn("staging/parts/testpkg/lib/widget.py", contracts)
            self.assertNotIn("staging/parts/testpkg/lib/widget_impl.py", contracts)

    def test_get_part_units_from_high_and_filesystem(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            # 1. HLS-based discovery without BUILD.bazel
            part_a = os.path.join(repo_root, "parts/alpha")
            high_a = os.path.join(part_a, "high")
            os.makedirs(high_a, exist_ok=True)
            with open(os.path.join(high_a, "alpha_iface.md"), "w", encoding="utf-8") as f:
                f.write("# alpha_iface interface component\n\n## Purpose\n...")
            with open(os.path.join(high_a, "alpha_impl.md"), "w", encoding="utf-8") as f:
                f.write(
                    "# alpha_impl implementation component\n\n"
                    "imports: alpha_iface, other_dep\n"
                    "implements: alpha_iface\n\n"
                    "## Purpose\n..."
                )

            units_a = workspace_work_impl._get_part_units(repo_root, "parts/alpha")
            self.assertIn("alpha_iface", units_a)
            self.assertEqual(units_a["alpha_iface"], [])
            self.assertIn("alpha_impl", units_a)
            self.assertEqual(units_a["alpha_impl"], ["alpha_iface", "other_dep"])

            # 2. Filesystem stems fallback without BUILD.bazel or high/
            part_b = os.path.join(repo_root, "parts/beta")
            lib_b = os.path.join(part_b, "lib")
            os.makedirs(lib_b, exist_ok=True)
            with open(os.path.join(lib_b, "beta.py"), "w", encoding="utf-8") as f:
                f.write("# beta\n")

            units_b = workspace_work_impl._get_part_units(repo_root, "parts/beta")
            self.assertEqual(units_b, {"beta": []})

    def test_compute_role_work_queue_materializes_template(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            part_dir = os.path.join(repo_root, "parts/sample")
            os.makedirs(os.path.join(part_dir, "high"), exist_ok=True)
            with open(os.path.join(part_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
                f.write('update_python_with_ai(name="sample_iface")\n')

            ready, blocked = self.work_mgr.compute_role_work_queue(
                role_name="high",
                dir_scope="parts/sample",
                repo_root=repo_root,
            )
            self.assertEqual(len(ready), 1)
            self.assertEqual(ready[0].target_file, "parts/sample/high/sample_iface.md")
            self.assertEqual(len(self.mock_storage.materialized), 1)
            self.assertEqual(
                self.mock_storage.materialized[0].unit_address,
                "parts/sample/high/sample_iface.md",
            )
            self.assertEqual(
                self.mock_storage.materialized[0].role_address,
                "high",
            )

    def test_compute_role_work_queue_disambiguates_unit_name_across_packages(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            clean_md = (
                "<!-- CLEANROOM METADATA\n"
                "LAST_CLEANED: 2026-10-08T00:00:00Z\n"
                "LAST_CHANGED: 2026-10-08T00:00:00Z\n"
                "-->\n"
            )
            clean_py = (
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-08T00:00:00Z\n"
                "# LAST_CHANGED: 2026-10-08T00:00:00Z\n"
                "# --- END CLEANROOM METADATA ---\n"
            )
            newer_py = (
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-08T12:00:00Z\n"
                "# LAST_CHANGED: 2026-10-08T12:00:00Z\n"
                "# --- END CLEANROOM METADATA ---\n"
            )
            older_py = (
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-07T00:00:00Z\n"
                "# LAST_CHANGED: 2026-10-07T00:00:00Z\n"
                "# --- END CLEANROOM METADATA ---\n"
            )

            # Package A has common_stem dirty in planning (no LAST_CLEANED)
            part_a = os.path.join(repo_root, "staging/parts/pkg_a")
            for d in ["high", "planning", "low", "lib"]:
                os.makedirs(os.path.join(part_a, d), exist_ok=True)
            with open(os.path.join(part_a, "BUILD.bazel"), "w", encoding="utf-8") as f:
                f.write('update_python_with_ai(name="common_stem")\n')
            with open(os.path.join(part_a, "high/common_stem.md"), "w", encoding="utf-8") as f:
                f.write(clean_md + "# common_stem\n")
            with open(os.path.join(part_a, "planning/common_stem.md"), "w", encoding="utf-8") as f:
                f.write("# common_stem\nUncleaned file\n")
            with open(os.path.join(part_a, "low/common_stem.pyi"), "w", encoding="utf-8") as f:
                f.write(clean_py)
            with open(os.path.join(part_a, "lib/common_stem.py"), "w", encoding="utf-8") as f:
                f.write(clean_py)

            # Package B has common_stem clean, and consumer depending on common_stem
            part_b = os.path.join(repo_root, "staging/parts/pkg_b")
            for d in ["high", "planning", "low", "lib"]:
                os.makedirs(os.path.join(part_b, d), exist_ok=True)
            with open(os.path.join(part_b, "BUILD.bazel"), "w", encoding="utf-8") as f:
                f.write(
                    'update_python_with_ai(name="common_stem")\n'
                    'update_python_with_ai(name="consumer", module_deps=[":common_stem"])\n'
                )
            with open(os.path.join(part_b, "high/common_stem.md"), "w", encoding="utf-8") as f:
                f.write(clean_md + "# common_stem\n")
            with open(os.path.join(part_b, "planning/common_stem.md"), "w", encoding="utf-8") as f:
                f.write(clean_md + "# common_stem\n")
            with open(os.path.join(part_b, "low/common_stem.pyi"), "w", encoding="utf-8") as f:
                f.write(clean_py)
            with open(os.path.join(part_b, "lib/common_stem.py"), "w", encoding="utf-8") as f:
                f.write(clean_py)

            with open(os.path.join(part_b, "high/consumer.md"), "w", encoding="utf-8") as f:
                f.write(clean_md + "# consumer\n")
            with open(os.path.join(part_b, "planning/consumer.md"), "w", encoding="utf-8") as f:
                f.write(clean_md + "# consumer\n")
            with open(os.path.join(part_b, "low/consumer.pyi"), "w", encoding="utf-8") as f:
                f.write(newer_py)
            with open(os.path.join(part_b, "lib/consumer.py"), "w", encoding="utf-8") as f:
                f.write(older_py)

            # In role 'lib', consumer in pkg_b should be ready and NOT blocked by pkg_a's common_stem
            ready, blocked = self.work_mgr.compute_role_work_queue(
                role_name="lib",
                dir_scope="staging",
                repo_root=repo_root,
            )
            ready_files = [item.target_file for item in ready]
            blocked_files = [item.target_file for item in blocked]

            self.assertIn("staging/parts/pkg_b/lib/consumer.py", ready_files)
            self.assertNotIn("staging/parts/pkg_b/lib/consumer.py", blocked_files)

    def test_is_pending_target_dirty_regenerates_on_delete_for_regenerable_roles(self) -> None:
        with tempfile.TemporaryDirectory() as ws_dir:
            part_dir = os.path.join(ws_dir, "staging/parts/sample")
            os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)
            target_lib = "staging/parts/sample/lib/sample_impl.py"
            self.mock_storage.materialized.clear()
            is_dirty = self.work_mgr.is_pending_target_dirty(
                target_lib, ws_dir, main_root=ws_dir, role_name="lib"
            )
            self.assertTrue(is_dirty)
            self.assertEqual(len(self.mock_storage.materialized), 1)
            self.assertEqual(self.mock_storage.materialized[0].unit_address, target_lib)

    def test_is_pending_target_dirty_does_not_regenerate_on_delete_for_high(self) -> None:
        with tempfile.TemporaryDirectory() as ws_dir:
            part_dir = os.path.join(ws_dir, "staging/parts/sample")
            os.makedirs(os.path.join(part_dir, "high"), exist_ok=True)
            target_high = "staging/parts/sample/high/sample.md"
            self.mock_storage.materialized.clear()
            is_dirty = self.work_mgr.is_pending_target_dirty(
                target_high, ws_dir, main_root=ws_dir, role_name="high"
            )
            self.assertTrue(is_dirty)
            self.assertEqual(len(self.mock_storage.materialized), 0)


if __name__ == "__main__":
    unittest.main()
