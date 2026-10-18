# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:58:06Z
# CHANGE: Replace the undeclared private registry and source metadata constructors with test doubles implementing the declared WorkspaceRegistry and SourceMetadataCoordinator interfaces
# CODE_HASH: be7f91954e3b
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Unit tests for work_impl."""

import hashlib
import json
import os
import tempfile
import unittest
from typing import Dict, List, Optional
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.control.lib import work_scheduler
from update_with_ai.parts.metadata.lib import src_metadata
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.workspace.lib import role_registry
from update_with_ai.parts.workspace_cli.lib import (
    work,
    work_impl,
)


def _parse_metadata_text(content: str) -> Optional[src_metadata.FileMetadata]:
    """Parses an in-band cleanroom metadata header from text."""
    in_header = False
    found = False
    values: Dict[str, str] = {}
    for raw in content.splitlines():
        stripped = raw.strip()
        if stripped.startswith("# --- CLEANROOM METADATA ---") or stripped.startswith(
            "<!-- CLEANROOM METADATA"
        ):
            in_header = True
            found = True
            continue
        if stripped.startswith("# --- END CLEANROOM METADATA ---") or stripped == "-->":
            break
        if not in_header:
            continue
        cleaned = stripped.lstrip("#").strip()
        if ":" in cleaned:
            key, _, value = cleaned.partition(":")
            values[key.strip().upper()] = value.strip()
    if not found:
        return None
    audits: Dict[str, str] = {}
    for key, value in values.items():
        if key.endswith("_AUDIT"):
            audits[key] = value
            audits[key[: -len("_AUDIT")].lower()] = value
    return src_metadata.FileMetadata(
        last_cleaned=values.get("LAST_CLEANED"),
        last_changed=values.get("LAST_CHANGED"),
        change_summary=values.get("CHANGE", ""),
        feedback=[values["FEEDBACK"]] if "FEEDBACK" in values else [],
        audits=audits,
        dirty=values.get("DIRTY"),
        code_hash=values.get("CODE_HASH"),
    )


class FakeSourceMetadataCoordinator:
    """Test double implementing the declared SourceMetadataCoordinator interface."""

    tier = "system"

    def __init__(self) -> None:
        self.metadata: Dict[str, src_metadata.FileMetadata] = {}

    def extract_metadata(self, file_path) -> Optional[src_metadata.FileMetadata]:
        key = str(file_path)
        if key in self.metadata:
            return self.metadata[key]
        try:
            with open(key, "r", encoding="utf-8") as fh:
                return _parse_metadata_text(fh.read())
        except OSError:
            return None

    def extract_metadata_from_text(
        self, content: str, filename_or_ext: str
    ) -> Optional[src_metadata.FileMetadata]:
        return _parse_metadata_text(content)

    def extract_code_body(self, content: str, filename_or_ext: str) -> str:
        return content

    def compute_code_hash(self, content: str, filename_or_ext: str) -> str:
        return hashlib.md5(content.encode("utf-8")).hexdigest()[:12]

    def compute_file_code_hash(self, file_path) -> Optional[str]:
        try:
            with open(str(file_path), "r", encoding="utf-8") as fh:
                return self.compute_code_hash(fh.read(), str(file_path))
        except OSError:
            return None

    def is_code_modified(self, file_path) -> bool:
        return False

    def update_metadata(self, file_path, **kwargs) -> None:
        return None

    def delete_last_cleaned(self, file_path) -> None:
        return None

    def mark_dirty(self, file_path, reason: str = "manual dirty") -> None:
        return None

    def mark_clean(self, file_path, default_change: str = "new file") -> None:
        return None

    def record_change(
        self, file_path, change_description: str, code_hash: Optional[str] = None
    ) -> None:
        return None

    def append_feedback(
        self, file_path, explanation: str, sender: str = "user"
    ) -> None:
        return None

    def stamp_audit(self, file_path, role_name: str) -> None:
        return None

    def clear_audits(self, file_path) -> None:
        return None


class FakeWorkspaceRegistry:
    """Test double implementing the declared WorkspaceRegistry interface."""

    tier = agent_session.agent_session

    def __init__(self, roles) -> None:
        self.roles = list(roles)
        self.descriptors: List[role_registry.WorkspaceDescriptor] = []

    def discover_repository_root(self, start_dir=None) -> str:
        return start_dir or os.getcwd()

    def resolve_role_definition(
        self, role_name_or_address, repo_root=None, dir_scope=None
    ) -> role_registry.RoleDefinition:
        name = str(role_name_or_address).split(":")[-1].split("#")[0].strip().lower()
        for role in self.roles:
            if role.role_name == name:
                return role
        raise KeyError(f"Role not found: {role_name_or_address}")

    def list_roles(self, repo_root=None, dir_scope=None):
        return list(self.roles)

    def compute_workspace_dir(
        self, role_name, dir_scope, repo_root=None, custom_dest=None
    ) -> str:
        if custom_dest:
            return custom_dest
        folder = f"{role_name}_{str(dir_scope).replace('/', '_')}"
        return os.path.join(repo_root or os.getcwd(), folder)

    def record_workspace(self, descriptor, repo_root=None) -> None:
        self.descriptors.append(descriptor)

    def unregister_workspace(self, workspace_dir, repo_root=None) -> bool:
        before = len(self.descriptors)
        self.descriptors = [
            d for d in self.descriptors if d.workspace_dir != workspace_dir
        ]
        return len(self.descriptors) != before

    def load_active_workspaces(self, repo_root=None):
        return list(self.descriptors)


def _role(
    name: str,
    src_pattern: str,
    writable: List[str],
    readonly: Optional[List[str]] = None,
    role_deps: Optional[List[str]] = None,
    star_role_deps: Optional[List[str]] = None,
    feedback_role_deps: Optional[List[str]] = None,
    stub_role_deps: Optional[List[str]] = None,
    audit_tag: Optional[str] = None,
) -> role_registry.RoleDefinition:
    return role_registry.RoleDefinition(
        role_name=name,
        guide_path=f"guides/{name}.md",
        writable_file_patterns=writable,
        readonly_file_patterns=readonly or [],
        feedback_role_deps=feedback_role_deps or [],
        src_pattern=src_pattern,
        role_deps=role_deps or [],
        star_role_deps=star_role_deps or [],
        stub_role_deps=stub_role_deps or [],
        audit_tag=audit_tag,
    )


def _make_roles():
    return [
        _role(
            "high",
            "{unit_dir}/high/{unit_name}.md",
            ["high/*.md", "**/high/*.md"],
        ),
        _role(
            "planning",
            "{unit_dir}/planning/{unit_name}.md",
            ["planning/*.md", "**/planning/*.md"],
        ),
        _role(
            "low",
            "{unit_dir}/low/{unit_name}.pyi",
            ["low/*.pyi", "**/low/*.pyi"],
            readonly=["high/*.md", "**/high/*.md"],
        ),
        _role(
            "lib",
            "{unit_dir}/lib/{unit_name}.py",
            ["lib/*.py", "**/lib/*.py"],
            readonly=["low/*.pyi", "**/low/*.pyi"],
            role_deps=["low"],
            star_role_deps=["low"],
        ),
        _role(
            "test",
            "{unit_dir}/tests/{unit_name}_test.py",
            ["tests/*.py", "**/tests/*.py"],
            readonly=["low/*.pyi", "**/low/*.pyi"],
            role_deps=["low"],
            stub_role_deps=["lib"],
        ),
        _role(
            "qa",
            "{unit_dir}/lib/{unit_name}.py",
            ["lib/*.py", "**/lib/*.py"],
            readonly=["low/*.pyi", "**/low/*.pyi", "tests/*.py", "**/tests/*.py"],
            feedback_role_deps=["lib", "test"],
            star_role_deps=["low", "test"],
            audit_tag="QA_AUDIT",
        ),
        _role(
            "scenario",
            "{unit_dir}/scenarios/{unit_name}.md",
            ["scenarios/*.md", "**/scenarios/*.md"],
            star_role_deps=["scenario"],
        ),
    ]


class MockWorkScheduler:
    tier = agent_session.agent_session

    def __init__(self, tasks=None):
        self.tasks = tasks or []

    def schedule_work(self, subgraph=None, dir_scope=None, max_batch_size=None):
        return work_scheduler.WorkSchedule(tasks=self.tasks)


class MockDagStorage:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.materialized: list[dag_storage.DagNode] = []

    def materialize_template(self, node: dag_storage.DagNode) -> None:
        self.materialized.append(node)


class WorkspaceWorkImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        from update_with_ai.parts.workspace_cli.lib import workspace_cli_asm
        workspace_cli_asm.__initialize__(self.registry)
        self.mock_storage = MockDagStorage()
        self.registry.register_instance(
            self.mock_storage,
            keys=[dag_storage.DagStorage],
            tier=agent_session.agent_session,
        )
        self.ws_registry = FakeWorkspaceRegistry(_make_roles())
        self.registry.register_instance(
            self.ws_registry,
            keys=[
                role_registry.WorkspaceRegistry,
            ],
            tier=agent_session.agent_session,
        )
        self.src_meta = FakeSourceMetadataCoordinator()
        self.registry.register_instance(
            self.src_meta,
            keys=[
                src_metadata.SourceMetadataCoordinator,
            ],
            tier="system",
        )
        self.work_mgr = work_impl.WorkspaceWorkManager()
        self.registry.register_instance(
            self.work_mgr,
            keys=[
                work.WorkspaceWorkManager,
                work_impl.WorkspaceWorkManager,
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
        task = work_scheduler.ScheduledTask(
            node=node,
            task_prompt="Implement foo.py",
            dependency_paths=[],
            feedback_messages=[],
        )
        mock_sched = MockWorkScheduler(tasks=[task])
        self.registry.register_instance(
            mock_sched,
            keys=[work_scheduler.WorkScheduler],
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

            units_a = work_impl.get_part_units(repo_root, "parts/alpha")
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

            units_b = work_impl.get_part_units(repo_root, "parts/beta")
            self.assertEqual(units_b, {"beta": []})

    def test_compute_role_work_queue_materializes_template(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            part_dir = os.path.join(repo_root, "parts/sample")
            os.makedirs(os.path.join(part_dir, "high"), exist_ok=True)
            os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
            with open(os.path.join(part_dir, "low/sample_iface.pyi"), "w", encoding="utf-8") as f:
                f.write("# sample_iface\n")

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
            with open(os.path.join(part_b, "high/common_stem.md"), "w", encoding="utf-8") as f:
                f.write(clean_md + "# common_stem\n")
            with open(os.path.join(part_b, "planning/common_stem.md"), "w", encoding="utf-8") as f:
                f.write(clean_md + "# common_stem\n")
            with open(os.path.join(part_b, "low/common_stem.pyi"), "w", encoding="utf-8") as f:
                f.write(clean_py)
            with open(os.path.join(part_b, "lib/common_stem.py"), "w", encoding="utf-8") as f:
                f.write(clean_py)

            with open(os.path.join(part_b, "high/consumer.md"), "w", encoding="utf-8") as f:
                f.write(clean_md + "imports: common_stem\n\n# consumer\n")
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

    def test_remove_pending_target_strictly_removes_matching(self) -> None:
        with tempfile.TemporaryDirectory() as ws_dir:
            self.work_mgr.set_pending_work(ws_dir, ["staging/parts/sample/lib/foo.py"])
            # Remove a non-matching target
            self.work_mgr.remove_pending_target(ws_dir, "staging/parts/sample/lib/bar.py")
            # Foo must strictly remain in pending work
            self.assertEqual(list(self.work_mgr.get_pending_work(ws_dir)), ["staging/parts/sample/lib/foo.py"])

            # Remove matching target
            self.work_mgr.remove_pending_target(ws_dir, "staging/parts/sample/lib/foo.py")
            self.assertEqual(list(self.work_mgr.get_pending_work(ws_dir)), [])

    def test_eval_auditor_unit_dirtiness_across_all_feedback_targets(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            clean_md = (
                "<!-- CLEANROOM METADATA\n"
                "LAST_CLEANED: 2026-10-08T00:00:00Z\n"
                "LAST_CHANGED: 2026-10-08T00:00:00Z\n"
                "-->\n"
            )
            part_dir = os.path.join(repo_root, "staging/parts/sample")
            for d in ["high", "planning", "low", "lib", "tests"]:
                os.makedirs(os.path.join(part_dir, d), exist_ok=True)
            with open(os.path.join(part_dir, "high/sample_impl.md"), "w", encoding="utf-8") as f:
                f.write(clean_md + "# sample_impl\n")
            with open(os.path.join(part_dir, "planning/sample_impl.md"), "w", encoding="utf-8") as f:
                f.write(clean_md + "# sample_impl\n")
            with open(os.path.join(part_dir, "low/sample_impl.pyi"), "w", encoding="utf-8") as f:
                f.write(
                    "# --- CLEANROOM METADATA ---\n"
                    "# LAST_CLEANED: 2026-10-08T00:00:00Z\n"
                    "# LAST_CHANGED: 2026-10-08T00:00:00Z\n"
                    "# --- END CLEANROOM METADATA ---\n"
                )
            # lib has QA_AUDIT at 01:00:00Z
            lib_content = (
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-08T00:00:00Z\n"
                "# LAST_CHANGED: 2026-10-08T00:00:00Z\n"
                "# QA_AUDIT: 2026-10-08T01:00:00Z\n"
                "# --- END CLEANROOM METADATA ---\n"
            )
            with open(os.path.join(part_dir, "lib/sample_impl.py"), "w", encoding="utf-8") as f:
                f.write(lib_content)
            # test was modified at 02:00:00Z without QA_AUDIT
            test_content = (
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-08T02:00:00Z\n"
                "# LAST_CHANGED: 2026-10-08T02:00:00Z\n"
                "# --- END CLEANROOM METADATA ---\n"
            )
            with open(os.path.join(part_dir, "tests/sample_impl_test.py"), "w", encoding="utf-8") as f:
                f.write(test_content)

            # Role qa must be dirty and ready because tests were modified without QA_AUDIT
            ready, blocked = self.work_mgr.compute_role_work_queue(
                role_name="qa",
                dir_scope="staging",
                repo_root=repo_root,
            )
            ready_files = [item.target_file for item in ready]
            self.assertIn("staging/parts/sample/lib/sample_impl.py", ready_files)
            self.assertEqual(len(blocked), 0)

            # Check is_pending_target_dirty for qa
            self.assertTrue(
                self.work_mgr.is_pending_target_dirty(
                    "staging/parts/sample/lib/sample_impl.py",
                    repo_root,
                    role_name="qa",
                )
            )

            # Now certify tests with QA_AUDIT
            audited_test_content = (
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-08T02:00:00Z\n"
                "# LAST_CHANGED: 2026-10-08T02:00:00Z\n"
                "# QA_AUDIT: 2026-10-08T02:30:00Z\n"
                "# --- END CLEANROOM METADATA ---\n"
            )
            with open(os.path.join(part_dir, "tests/sample_impl_test.py"), "w", encoding="utf-8") as f:
                f.write(audited_test_content)

            # Now qa should evaluate clean
            self.assertFalse(
                self.work_mgr.is_pending_target_dirty(
                    "staging/parts/sample/lib/sample_impl.py",
                    repo_root,
                    role_name="qa",
                )
            )

            # If feedback target is marked DIRTY: but unmodified (QA_AUDIT > LAST_CHANGED), qa remains clean
            dirty_tagged_lib = (
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-08T00:00:00Z\n"
                "# LAST_CHANGED: 2026-10-08T00:00:00Z\n"
                "# DIRTY: Check carefully\n"
                "# QA_AUDIT: 2026-10-08T01:00:00Z\n"
                "# --- END CLEANROOM METADATA ---\n"
            )
            with open(os.path.join(part_dir, "lib/sample_impl.py"), "w", encoding="utf-8") as f:
                f.write(dirty_tagged_lib)
            self.assertFalse(
                self.work_mgr.is_pending_target_dirty(
                    "staging/parts/sample/lib/sample_impl.py",
                    repo_root,
                    role_name="qa",
                )
            )

    def test_eval_auditor_unit_dirtiness_when_contract_dependency_modified(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            clean_md = (
                "<!-- CLEANROOM METADATA\n"
                "LAST_CLEANED: 2026-10-08T00:00:00Z\n"
                "LAST_CHANGED: 2026-10-08T00:00:00Z\n"
                "-->\n"
            )
            part_dir = os.path.join(repo_root, "staging/parts/sample")
            for d in ["high", "planning", "low", "lib", "tests"]:
                os.makedirs(os.path.join(part_dir, d), exist_ok=True)
            with open(os.path.join(part_dir, "high/sample_impl.md"), "w", encoding="utf-8") as f:
                f.write(clean_md + "# sample_impl\n")
            with open(os.path.join(part_dir, "planning/sample_impl.md"), "w", encoding="utf-8") as f:
                f.write(clean_md + "# sample_impl\n")
            # low contract modified at 03:00:00Z
            with open(os.path.join(part_dir, "low/sample_impl.pyi"), "w", encoding="utf-8") as f:
                f.write(
                    "# --- CLEANROOM METADATA ---\n"
                    "# LAST_CLEANED: 2026-10-08T03:00:00Z\n"
                    "# LAST_CHANGED: 2026-10-08T03:00:00Z\n"
                    "# --- END CLEANROOM METADATA ---\n"
                )
            # lib has QA_AUDIT at 01:00:00Z
            with open(os.path.join(part_dir, "lib/sample_impl.py"), "w", encoding="utf-8") as f:
                f.write(
                    "# --- CLEANROOM METADATA ---\n"
                    "# LAST_CLEANED: 2026-10-08T00:00:00Z\n"
                    "# LAST_CHANGED: 2026-10-08T00:00:00Z\n"
                    "# QA_AUDIT: 2026-10-08T01:00:00Z\n"
                    "# --- END CLEANROOM METADATA ---\n"
                )
            # test has QA_AUDIT at 01:00:00Z
            with open(os.path.join(part_dir, "tests/sample_impl_test.py"), "w", encoding="utf-8") as f:
                f.write(
                    "# --- CLEANROOM METADATA ---\n"
                    "# LAST_CLEANED: 2026-10-08T00:00:00Z\n"
                    "# LAST_CHANGED: 2026-10-08T00:00:00Z\n"
                    "# QA_AUDIT: 2026-10-08T01:00:00Z\n"
                    "# --- END CLEANROOM METADATA ---\n"
                )

            # Even though lib and test are audited, low contract was modified after audit, so qa is dirty
            self.assertTrue(
                self.work_mgr.is_pending_target_dirty(
                    "staging/parts/sample/lib/sample_impl.py",
                    repo_root,
                    role_name="qa",
                )
            )

    def test_producer_dirty_when_star_role_dependency_modified_on_interface(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            part_dir = os.path.join(repo_root, "staging/parts/sample")
            os.makedirs(os.path.join(part_dir, "scenarios"), exist_ok=True)
            # Interface scenario modified at 02:00:00Z
            with open(os.path.join(part_dir, "scenarios/sample.md"), "w", encoding="utf-8") as f:
                f.write(
                    "<!-- CLEANROOM METADATA\n"
                    "LAST_CLEANED: 2026-10-08T02:00:00Z\n"
                    "LAST_CHANGED: 2026-10-08T02:00:00Z\n"
                    "-->\n"
                    "# sample scenario\n"
                )
            # Implementation scenario cleaned at 01:00:00Z (before interface change)
            with open(os.path.join(part_dir, "scenarios/sample_impl.md"), "w", encoding="utf-8") as f:
                f.write(
                    "<!-- CLEANROOM METADATA\n"
                    "LAST_CLEANED: 2026-10-08T01:00:00Z\n"
                    "LAST_CHANGED: 2026-10-08T01:00:00Z\n"
                    "-->\n"
                    "# sample_impl scenario\n"
                )

            # Implementation must evaluate dirty because star dependency (interface scenario) changed
            self.assertTrue(
                self.work_mgr.is_pending_target_dirty(
                    "staging/parts/sample/scenarios/sample_impl.md",
                    repo_root,
                    role_name="scenario",
                )
            )

    def test_resolve_contract_files_includes_interface_stem_for_star_roles(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            part_dir = os.path.join(repo_root, "staging/parts/sample")
            os.makedirs(os.path.join(part_dir, "scenarios"), exist_ok=True)
            with open(os.path.join(part_dir, "scenarios/sample.md"), "w", encoding="utf-8") as f:
                f.write("# sample scenario\n")
            with open(os.path.join(part_dir, "scenarios/sample_impl.md"), "w", encoding="utf-8") as f:
                f.write("# sample_impl scenario\n")

            contracts = self.work_mgr.resolve_contract_files(
                target_path="staging/parts/sample/scenarios/sample_impl.md",
                workspace_dir=repo_root,
                role_name="scenario",
            )
            self.assertIn("staging/parts/sample/scenarios/sample.md", contracts)

    def test_evaluate_work_bounds_ready_items_by_batch_size(self) -> None:
        tasks = [
            work_scheduler.ScheduledTask(
                node=dag_storage.DagNode(
                    unit_address=dag_storage.UnitAddress(f"staging/parts/sample/lib/unit_{i}.py"),
                    role_address=dag_storage.RoleAddress("//update_python_with_ai:lib"),
                ),
                task_prompt=f"Implement unit_{i}.py",
                dependency_paths=[],
                feedback_messages=[],
            )
            for i in range(3)
        ]
        mock_sched = MockWorkScheduler(tasks=tasks)
        self.registry.register_instance(
            mock_sched,
            keys=[work_scheduler.WorkScheduler],
            tier=agent_session.agent_session,
        )
        with tempfile.TemporaryDirectory() as ws_dir:
            summary = self.work_mgr.evaluate_work(
                dir_scope="staging",
                role_name="lib",
                workspace_dir=ws_dir,
                force=True,
                batch_size=1,
            )
            self.assertEqual(len(summary.ready_items), 1)
            self.assertEqual(summary.remaining_ready_count, 2)
            self.assertFalse(summary.is_clean)

            pending = self.work_mgr.get_pending_work(ws_dir)
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0], summary.ready_items[0].target_file)

    def test_compute_role_work_queue_bounds_to_target_unit(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            clean_py = (
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-08T00:00:00Z\n"
                "# LAST_CHANGED: 2026-10-08T00:00:00Z\n"
                "# --- END CLEANROOM METADATA ---\n"
            )
            part_a = os.path.join(repo_root, "staging/parts/alpha")
            part_b = os.path.join(repo_root, "staging/parts/beta")
            os.makedirs(os.path.join(part_a, "lib"), exist_ok=True)
            os.makedirs(os.path.join(part_a, "low"), exist_ok=True)
            os.makedirs(os.path.join(part_b, "lib"), exist_ok=True)
            os.makedirs(os.path.join(part_b, "low"), exist_ok=True)

            with open(os.path.join(part_a, "low/alpha.pyi"), "w", encoding="utf-8") as f:
                f.write(clean_py)
            with open(os.path.join(part_a, "lib/alpha.py"), "w", encoding="utf-8") as f:
                f.write("# alpha\n")

            with open(os.path.join(part_b, "low/beta.pyi"), "w", encoding="utf-8") as f:
                f.write(clean_py)
            with open(os.path.join(part_b, "lib/beta.py"), "w", encoding="utf-8") as f:
                f.write("# beta\n")

            ready_all, _ = self.work_mgr.compute_role_work_queue(
                role_name="lib",
                dir_scope="staging",
                repo_root=repo_root,
            )
            self.assertEqual(len(ready_all), 2)

            ready_bounded, _ = self.work_mgr.compute_role_work_queue(
                role_name="lib",
                dir_scope="staging",
                repo_root=repo_root,
                target_unit="//staging/parts/alpha:alpha#lib",
            )
            self.assertEqual(len(ready_bounded), 1)
            self.assertEqual(ready_bounded[0].target_file, "staging/parts/alpha/lib/alpha.py")


if __name__ == "__main__":
    unittest.main()
