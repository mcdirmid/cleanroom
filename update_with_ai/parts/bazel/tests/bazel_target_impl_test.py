"""Unit tests for bazel_target_impl aligned with grounding specifications."""

import unittest
from update_with_ai.parts.bazel.lib.bazel_target import BazelTarget, NodeDirectory
from update_with_ai.parts.bazel.lib.bazel_target_impl import (
    BazelTarget as BazelTargetImpl,
    __initialize__,
)
from update_with_ai.parts.dag.lib.dag_storage import Node
from support.lib.lifecycle import LifecycleRegistry, enter_phase


class TestBazelTargetImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_normalize(self) -> None:
        """Tests CUJ for normalizing various Bazel target label formats into canonical Node.

        Checks postconditions & invariants:
        - Labels starting with // are preserved.
        - Repository qualifiers (@@//, @//) are stripped.
        - Omitted target labels (//pkg) are expanded to //pkg:pkg.
        """
        with enter_phase("system", registry=self.registry) as scope:
            utils = scope.get_singleton(BazelTarget)
            # Requirement: The bazel target normalizes raw target labels by stripping repository qualifiers and expanding omitted target names.
            # Requirement: [BazelTarget] The bazel target normalizes an arbitrary Bazel target identifier string into a canonical node.
            self.assertEqual(
                utils.normalize("//pkg/sub:target"),
                Node(address="//pkg/sub:target"),
            )
            self.assertEqual(
                utils.normalize("@@//pkg:target"),
                Node(address="//pkg:target"),
            )
            self.assertEqual(
                utils.normalize("@//pkg:target"),
                Node(address="//pkg:target"),
            )
            self.assertEqual(
                utils.normalize("//pkg"),
                Node(address="//pkg:pkg"),
            )
            self.assertEqual(
                utils.normalize("//foo/bar"),
                Node(address="//foo/bar:bar"),
            )
            self.assertEqual(
                utils.normalize("pkg:target"),
                Node(address="//pkg:target"),
            )

    def test_extract_directory(self) -> None:
        """Tests CUJ for extracting package directory from canonical Node.

        Checks postconditions & invariants:
        - Extracts package directory relative to workspace.
        - Root target //:root_target resolves to empty path.
        """

        def _make_node_dir(path: str) -> NodeDirectory:
            obj = object.__new__(NodeDirectory)
            object.__setattr__(obj, "path", path)
            return obj

        with enter_phase("system", registry=self.registry) as scope:
            utils = scope.get_singleton(BazelTarget)
            # Requirement: The bazel target derives node directories from normalized nodes relative to a workspace root.
            # Requirement: [BazelTarget] The bazel target extracts a node directory from a node.
            self.assertEqual(
                utils.extract_directory(Node(address="//pkg/sub:target")),
                _make_node_dir("pkg/sub"),
            )
            self.assertEqual(
                utils.extract_directory(Node(address="//:root_target")),
                _make_node_dir(""),
            )


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
