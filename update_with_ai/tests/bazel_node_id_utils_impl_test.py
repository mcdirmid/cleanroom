"""Unit tests for bazel_node_id_utils_impl aligned with grounding specifications."""

import unittest
from lib.bazel_node_id_utils import BazelNodeIdentifierUtility, NodeDirectory
from lib.bazel_node_id_utils_impl import (
    BazelNodeIdentifierUtility as BazelNodeIdentifierUtilityImpl,
    __initialize__,
)
from lib.dag_storage import Node
from lib.lifecycle import LifecycleRegistry, enter_phase


class TestBazelNodeIdUtilsImpl(unittest.TestCase):
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
            utils = scope.get_singleton(BazelNodeIdentifierUtility)
            # Requirement: The bazel node identifier utility normalizes raw target labels by stripping repository qualifiers and expanding omitted target names.
            # Requirement: [BazelNodeIdentifierUtility] The bazel node identifier utility normalizes an arbitrary target identifier string into a canonical node.
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
        with enter_phase("system", registry=self.registry) as scope:
            utils = scope.get_singleton(BazelNodeIdentifierUtility)
            # Requirement: The bazel node identifier utility derives node directories from normalized nodes relative to a workspace root.
            # Requirement: [BazelNodeIdentifierUtility] The bazel node identifier utility extracts a node directory from a node.
            self.assertEqual(
                utils.extract_directory(Node(address="//pkg/sub:target")),
                NodeDirectory(path="pkg/sub"),
            )
            self.assertEqual(
                utils.extract_directory(Node(address="//:root_target")),
                NodeDirectory(path=""),
            )


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None


