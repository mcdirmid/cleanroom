"""Unit tests for bazel_target_impl aligned with grounding specifications."""

import unittest
from update_with_ai.parts.bazel.lib.bazel_target import BazelTarget, NodeDirectory, TargetIdentifier
from update_with_ai.parts.bazel.lib.bazel_target_impl import (
    BazelTarget as BazelTargetImpl,
    __initialize__,
)
from update_with_ai.parts.core.lib.file_paths import PathString
from update_with_ai.parts.dag.lib.dag_storage import DagNode, RoleAddress, UnitAddress
from support.lib.lifecycle import LifecycleRegistry, enter_phase


def _make_dag_node(unit_address: str, role_address: str = "") -> DagNode:
    return DagNode(unit_address=UnitAddress(unit_address), role_address=RoleAddress(role_address))


class TestBazelTargetImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_normalize_target(self) -> None:
        """CUJ: Normalizing various Bazel target label formats into canonical DagNode."""
        with enter_phase("system", registry=self.registry) as scope:
            utils = scope.get_singleton(BazelTarget)
            # Requirement: MUST strip repository qualifiers and expand omitted target names into canonical nodes.
            # Requirement: MUST normalize an arbitrary Bazel target identifier string into a canonical node.
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
                utils.normalize_target(TargetIdentifier("//pkg/sub:target#//roles:lib")),
                _make_dag_node("//pkg/sub:target", "//roles:lib"),
            )
            self.assertEqual(
                utils.normalize_target(TargetIdentifier("")),
                _make_dag_node(""),
            )

    def test_extract_node_dir(self) -> None:
        """CUJ: Extracting package directory from canonical DagNode."""
        with enter_phase("system", registry=self.registry) as scope:
            utils = scope.get_singleton(BazelTarget)
            # Requirement: MUST derive node directories by extracting package directory paths relative to a workspace root.
            # Requirement: MUST extract a node directory from a node.
            self.assertEqual(
                utils.extract_node_dir(
                    _make_dag_node("//pkg/sub:target")
                ),
                NodeDirectory(path=PathString("pkg/sub")),
            )
            self.assertEqual(
                utils.extract_node_dir(
                    _make_dag_node("//:root_target")
                ),
                NodeDirectory(path=PathString("")),
            )


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
