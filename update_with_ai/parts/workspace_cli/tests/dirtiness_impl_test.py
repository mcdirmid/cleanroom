"""Unit tests for dirtiness_impl aligned with low-level specifications."""

import os
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.metadata.lib import src_metadata
from update_with_ai.parts.workspace.lib import role_registry
from update_with_ai.parts.workspace_cli.lib import (
    dirtiness,
    dirtiness_impl,
)


class FakeWorkspaceRegistry:
    def resolve_role_definition(self, role_name: str, repo_root: str | None = None) -> role_registry.RoleDefinition:
        clean = role_name.split(":")[-1].strip().lower()
        if clean == "lib":
            return role_registry.RoleDefinition(
                role_name="lib",
                guide_path="guides/lib.md",
                writable_file_patterns=["*/lib/*.py"],
                readonly_file_patterns=[],
                feedback_role_deps=[],
                src_pattern="{unit_dir}/lib/{unit_name}.py",
                role_deps=["low"],
                star_role_deps=["low"],
                active_component_types=["interface", "implementation"],
            )
        if clean == "low":
            return role_registry.RoleDefinition(
                role_name="low",
                guide_path="guides/low.md",
                writable_file_patterns=["*/low/*.pyi"],
                readonly_file_patterns=[],
                feedback_role_deps=[],
                src_pattern="{unit_dir}/low/{unit_name}.pyi",
                role_deps=["planning"],
                star_role_deps=[],
                active_component_types=["interface", "implementation"],
            )
        if clean == "qa":
            return role_registry.RoleDefinition(
                role_name="qa",
                guide_path="guides/qa.md",
                writable_file_patterns=[],
                readonly_file_patterns=[],
                feedback_role_deps=["lib"],
                src_pattern="",
                role_deps=[],
                audit_tag="QA_AUDIT",
                active_component_types=["interface", "implementation"],
            )
        raise LookupError(f"Role not found: {role_name}")

    def list_roles(self, repo_root: str | None = None) -> list[role_registry.RoleDefinition]:
        return [
            self.resolve_role_definition("lib"),
            self.resolve_role_definition("low"),
            self.resolve_role_definition("qa"),
        ]


class WorkspaceDirtinessImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.registry.register_instance(
            FakeWorkspaceRegistry(),
            keys=[role_registry.WorkspaceRegistry],
            tier=agent_session.agent_session,
        )
        self.evaluator = dirtiness_impl.WorkspaceDirtinessEvaluator()
        self.registry.register_instance(
            self.evaluator,
            keys=[
                dirtiness.WorkspaceDirtinessEvaluator,
                dirtiness_impl.WorkspaceDirtinessEvaluator,
            ],
            tier=agent_session.agent_session,
        )
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.phase_cm.__enter__()
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_evaluate_unit_dirty_missing_target(self) -> None:
        res = self.evaluator.evaluate_unit_dirty(
            ws_root=self.test_dir,
            part_dir="parts/foo",
            unit_name="bar",
            eval_role="lib",
            repo_root=self.test_dir,
        )
        self.assertTrue(res.is_dirty)
        self.assertTrue(any("does not exist" in r for r in res.dirtiness_reasons))

    def test_evaluate_unit_dirty_uninitialized_target(self) -> None:
        part_dir = os.path.join(self.test_dir, "parts", "foo")
        lib_dir = os.path.join(part_dir, "lib")
        os.makedirs(lib_dir, exist_ok=True)
        target_file = os.path.join(lib_dir, "bar.py")
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# Cleanroom library template without metadata header\n")
        res = self.evaluator.evaluate_unit_dirty(
            ws_root=self.test_dir,
            part_dir="parts/foo",
            unit_name="bar",
            eval_role="lib",
            repo_root=self.test_dir,
        )
        self.assertTrue(res.is_dirty)
        self.assertTrue(any("is uninitialized (initial implementation required)" in r for r in res.dirtiness_reasons))
        self.assertFalse(any("in-band metadata header" in r for r in res.dirtiness_reasons))

    def test_evaluate_unit_dirty_metadata_clean(self) -> None:
        part_dir = os.path.join(self.test_dir, "parts", "foo")
        lib_dir = os.path.join(part_dir, "lib")
        low_dir = os.path.join(part_dir, "low")
        os.makedirs(lib_dir, exist_ok=True)
        os.makedirs(low_dir, exist_ok=True)

        target_file = os.path.join(lib_dir, "bar.py")
        upstream_spec = os.path.join(low_dir, "bar.pyi")

        src_metadata.update_metadata(
            upstream_spec,
            last_cleaned="2026-10-10T10:00:00Z",
            last_changed="2026-10-10T10:00:00Z",
            clear_dirty=True,
        )
        src_metadata.update_metadata(
            target_file,
            last_cleaned="2026-10-10T12:00:00Z",
            last_changed="2026-10-10T12:00:00Z",
            clear_dirty=True,
        )

        res = self.evaluator.evaluate_unit_dirty(
            ws_root=self.test_dir,
            part_dir="parts/foo",
            unit_name="bar",
            eval_role="lib",
            repo_root=self.test_dir,
        )
        self.assertFalse(res.is_dirty)
        self.assertEqual(res.dirtiness_reasons, ())

    def test_evaluate_unit_dirty_upstream_modified(self) -> None:
        part_dir = os.path.join(self.test_dir, "parts", "foo")
        lib_dir = os.path.join(part_dir, "lib")
        low_dir = os.path.join(part_dir, "low")
        os.makedirs(lib_dir, exist_ok=True)
        os.makedirs(low_dir, exist_ok=True)

        target_file = os.path.join(lib_dir, "bar.py")
        upstream_spec = os.path.join(low_dir, "bar.pyi")

        # Upstream spec modified after target last_cleaned
        src_metadata.update_metadata(
            upstream_spec,
            last_cleaned="2026-10-10T14:00:00Z",
            last_changed="2026-10-10T14:00:00Z",
            clear_dirty=True,
        )
        src_metadata.update_metadata(
            target_file,
            last_cleaned="2026-10-10T12:00:00Z",
            last_changed="2026-10-10T12:00:00Z",
            clear_dirty=True,
        )

        res = self.evaluator.evaluate_unit_dirty(
            ws_root=self.test_dir,
            part_dir="parts/foo",
            unit_name="bar",
            eval_role="lib",
            repo_root=self.test_dir,
        )
        self.assertTrue(res.is_dirty)
        self.assertTrue(any("modified" in r for r in res.dirtiness_reasons))

    def test_evaluate_auditor_dirty_uncertified(self) -> None:
        part_dir = os.path.join(self.test_dir, "parts", "foo")
        lib_dir = os.path.join(part_dir, "lib")
        os.makedirs(lib_dir, exist_ok=True)
        target_file = os.path.join(lib_dir, "bar.py")

        src_metadata.update_metadata(
            target_file,
            last_cleaned="2026-10-10T12:00:00Z",
            last_changed="2026-10-10T12:00:00Z",
            clear_dirty=True,
        )

        res = self.evaluator.evaluate_unit_dirty(
            ws_root=self.test_dir,
            part_dir="parts/foo",
            unit_name="bar",
            eval_role="qa",
            repo_root=self.test_dir,
        )
        self.assertTrue(res.is_dirty)
        self.assertTrue(any("QA_AUDIT" in r for r in res.dirtiness_reasons))

    def test_extract_cross_unit_dependencies(self) -> None:
        high_dir = os.path.join(self.test_dir, "parts", "foo", "high")
        os.makedirs(high_dir, exist_ok=True)
        spec_file = os.path.join(high_dir, "bar.md")
        with open(spec_file, "w", encoding="utf-8") as f:
            f.write("# bar spec\n\nimports: //parts/baz:qux\n\n## Purpose\n")

        deps = self.evaluator.extract_cross_unit_dependencies(
            repo_root=self.test_dir,
            part_dir="parts/foo",
            unit_name="bar",
        )
        self.assertEqual(list(deps), [("parts/baz", "qux")])

    def test_evaluate_unit_dirty_projected_role_workspace_metadata(self) -> None:
        """Verifies that projected workspace files without LAST_CLEANED resolve canonical main metadata."""
        canonical_repo = os.path.join(self.test_dir, "canonical_repo")
        role_ws = os.path.join(self.test_dir, "role_ws")
        part_rel = os.path.join("parts", "foo")

        main_lib_dir = os.path.join(canonical_repo, part_rel, "lib")
        main_low_dir = os.path.join(canonical_repo, part_rel, "low")
        os.makedirs(main_lib_dir, exist_ok=True)
        os.makedirs(main_low_dir, exist_ok=True)

        ws_lib_dir = os.path.join(role_ws, part_rel, "lib")
        ws_low_dir = os.path.join(role_ws, part_rel, "low")
        os.makedirs(ws_lib_dir, exist_ok=True)
        os.makedirs(ws_low_dir, exist_ok=True)

        main_target = os.path.join(main_lib_dir, "bar.py")
        main_spec = os.path.join(main_low_dir, "bar.pyi")

        ws_target = os.path.join(ws_lib_dir, "bar.py")
        ws_spec = os.path.join(ws_low_dir, "bar.pyi")

        # Upstream spec clean in main
        src_metadata.update_metadata(
            main_spec,
            last_cleaned="2026-10-10T10:00:00Z",
            last_changed="2026-10-10T10:00:00Z",
            clear_dirty=True,
        )
        # Target file clean in main
        src_metadata.update_metadata(
            main_target,
            last_cleaned="2026-10-10T12:00:00Z",
            last_changed="2026-10-10T12:00:00Z",
            clear_dirty=True,
        )
        # Projected target file in role workspace (has CODE_HASH, but NO last_cleaned, NO last_changed)
        with open(ws_target, "w", encoding="utf-8") as f:
            f.write("# --- CLEANROOM METADATA ---\n# CODE_HASH: 123456\n# --- END CLEANROOM METADATA ---\n")
        # Projected spec in role workspace
        with open(ws_spec, "w", encoding="utf-8") as f:
            f.write("# --- CLEANROOM METADATA ---\n# CODE_HASH: abcdef\n# --- END CLEANROOM METADATA ---\n")

        res = self.evaluator.evaluate_unit_dirty(
            ws_root=role_ws,
            part_dir="parts/foo",
            unit_name="bar",
            eval_role="lib",
            repo_root=canonical_repo,
        )
        self.assertFalse(res.is_dirty)
        self.assertEqual(res.dirtiness_reasons, ())

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:15:00Z
# CHANGE: Unit tests for dirtiness_impl
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
