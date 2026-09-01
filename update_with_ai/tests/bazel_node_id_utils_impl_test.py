"""Unit tests for bazel_node_id_utils_impl derived from LLS."""

import os
import unittest
from lib.bazel_node_id_utils_impl import BazelNodeIdUtilsImpl


class TestBazelNodeIdUtilsImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.utils = BazelNodeIdUtilsImpl()

    def test_canonicalize_node_id(self) -> None:
        """Tests CUJ for canonicalizing various Bazel target label formats into canonical NodeId.

        Checks postconditions & invariants:
        - Labels starting with // are normalized to //pkg:target.
        - Repository qualifiers (@@//, @//) are stripped.
        - Omitted target labels (//pkg) are expanded to //pkg:pkg.
        - Relative labels (:target) in context are resolved to //pkg:target.
        """
        self.assertEqual(
            self.utils.canonicalize_node_id("//pkg/sub:target", current_context=""),
            "//pkg/sub:target",
        )
        self.assertEqual(
            self.utils.canonicalize_node_id("@@//pkg:target", current_context=""),
            "//pkg:target",
        )
        self.assertEqual(
            self.utils.canonicalize_node_id("@//pkg:target", current_context=""),
            "//pkg:target",
        )
        self.assertEqual(
            self.utils.canonicalize_node_id("//pkg", current_context=""),
            "//pkg:pkg",
        )
        self.assertEqual(
            self.utils.canonicalize_node_id(":target", current_context="pkg"),
            "//pkg:target",
        )

    def test_extract_node_directory(self) -> None:
        """Tests CUJ for extracting package directory from canonical NodeId.

        Checks postconditions & invariants:
        - Joins package part of canonical NodeId with workspace_root.
        - Root target //:root_target resolves directly to workspace_root.
        - Paths returned are normalized filesystem paths.
        """
        ws = "/workspace"
        self.assertEqual(
            self.utils.extract_node_directory("//pkg/sub:target", ws),
            os.path.normpath("/workspace/pkg/sub"),
        )
        self.assertEqual(
            self.utils.extract_node_directory("//:root_target", ws),
            os.path.normpath("/workspace"),
        )


if __name__ == "__main__":
    unittest.main()
