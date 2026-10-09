# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:02Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: 96b957ff9704
# COVERAGE_AUDIT: 2026-10-09T21:19:02Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Unit tests for uv_target_impl aligned with low-level specifications."""

import unittest
from update_with_ai.parts.uv.lib.uv_target import (
    UvTarget,
    NodeDirectory,
    TargetIdentifier,
)
from update_with_ai.parts.uv.lib.uv_target_impl import (
    UvTarget as UvTargetImpl,
    __initialize__,
)
from update_with_ai.parts.core.lib.file_paths import PathString
from update_with_ai.parts.dag.lib.dag_storage import DagNode, RoleAddress, UnitAddress
from support.lib.lifecycle import LifecycleRegistry, enter_phase


def _make_dag_node(unit_address: str, role_address: str = "") -> DagNode:
    return DagNode(
        unit_address=UnitAddress(unit_address), role_address=RoleAddress(role_address)
    )


class TestUvTargetImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_normalize_target(self) -> None:
        """Verifies normalizing various target label formats into canonical DagNode."""
        with enter_phase("system", registry=self.registry) as scope:
            utils = scope.get_singleton(UvTarget)
            # MUST strip repository qualifiers and expand omitted target names into canonical nodes.
            self.assertEqual(
                utils.normalize_target(TargetIdentifier("//pkg/sub:target")),
                _make_dag_node("//pkg/sub:target"),
            )
            self.assertEqual(
                utils.normalize_target(TargetIdentifier("@@//pkg:target")),
                _make_dag_node("//pkg:target"),
            )
            self.assertEqual(
                utils.normalize_target(TargetIdentifier("@//pkg:target")),
                _make_dag_node("//pkg:target"),
            )
            self.assertEqual(
                utils.normalize_target(TargetIdentifier("//pkg")),
                _make_dag_node("//pkg:pkg"),
            )
            self.assertEqual(
                utils.normalize_target(TargetIdentifier("//foo/bar")),
                _make_dag_node("//foo/bar:bar"),
            )
            self.assertEqual(
                utils.normalize_target(TargetIdentifier("pkg:target")),
                _make_dag_node("//pkg:target"),
            )
            self.assertEqual(
                utils.normalize_target(
                    TargetIdentifier("//pkg/sub:target#//roles:lib")
                ),
                _make_dag_node("//pkg/sub:target", "//roles:lib"),
            )
            self.assertEqual(
                utils.normalize_target(
                    TargetIdentifier("//pkg/sub:target#lib")
                ),
                _make_dag_node("//pkg/sub:target", "lib"),
            )
            self.assertEqual(
                utils.normalize_target(TargetIdentifier("")),
                _make_dag_node(""),
            )

    def test_normalize_path_based_target(self) -> None:
        """Verifies normalizing file paths into canonical DagNode coordinates."""
        with enter_phase("system", registry=self.registry) as scope:
            utils = scope.get_singleton(UvTarget)
            # High spec path
            self.assertEqual(
                utils.normalize_target(TargetIdentifier("update_with_ai/parts/uv/high/uv_target.md")),
                _make_dag_node("//update_with_ai/parts/uv:uv_target", "high"),
            )
            # Planning spec path
            self.assertEqual(
                utils.normalize_target(TargetIdentifier("update_with_ai/parts/uv/planning/uv_target.md")),
                _make_dag_node("//update_with_ai/parts/uv:uv_target", "planning"),
            )
            # Low spec path
            self.assertEqual(
                utils.normalize_target(TargetIdentifier("update_with_ai/parts/uv/low/uv_target.pyi")),
                _make_dag_node("//update_with_ai/parts/uv:uv_target", "low"),
            )
            # Library source path
            self.assertEqual(
                utils.normalize_target(TargetIdentifier("update_with_ai/parts/uv/lib/uv_target.py")),
                _make_dag_node("//update_with_ai/parts/uv:uv_target", "lib"),
            )
            # Test source path
            self.assertEqual(
                utils.normalize_target(TargetIdentifier("update_with_ai/parts/uv/tests/uv_target_impl_test.py")),
                _make_dag_node("//update_with_ai/parts/uv:uv_target_impl", "test"),
            )

    def test_extract_node_dir(self) -> None:
        """Verifies extracting package directory from canonical DagNode."""
        with enter_phase("system", registry=self.registry) as scope:
            utils = scope.get_singleton(UvTarget)
            # MUST derive node directories by extracting package directory paths relative to a workspace root.
            self.assertEqual(
                utils.extract_node_dir(_make_dag_node("//pkg/sub:target")),
                NodeDirectory(path=PathString("pkg/sub")),
            )
            self.assertEqual(
                utils.extract_node_dir(_make_dag_node("//:root_target")),
                NodeDirectory(path=PathString("")),
            )


if __name__ == "__main__":
    unittest.main()
