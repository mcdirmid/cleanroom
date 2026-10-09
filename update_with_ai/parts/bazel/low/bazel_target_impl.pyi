# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 19a566d1bac6
# --- END CLEANROOM METADATA ---

"""Bazel target implementation low-level specification."""

from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import bazel_target
import dag_storage
import file_paths


@singleton_type("system")
class BazelTarget(bazel_target.BazelTarget, InTier[SystemTier]):
    """Realizes Bazel label canonicalization and package directory resolution.

    GROUNDING:
    - Realizes bazel_target interface contracts by delegating label normalization and package directory resolution to bazel_target_labels_ext.
    """

    @operation
    @override
    def normalize_target(self, target_identifier: bazel_target.TargetIdentifier) -> dag_storage.DagNode:
        """Normalizes raw target labels into canonical nodes.

        Args:
            target_identifier: The raw target label string.

        Returns:
            The normalized dag node.

        POSTCONDITIONS:
        - MUST strip repository qualifiers and expand omitted target names into canonical nodes.

        GROUNDING:
        - Invokes bazel_target_labels_ext.normalize_label to strip repository prefixes and expand omitted target names into canonical DagNode coordinates.
        """
        ...

    @operation
    @override
    def extract_node_dir(self, node: dag_storage.DagNode) -> bazel_target.NodeDirectory:
        """Derives package directory paths relative to the workspace root.

        Args:
            node: The node whose package directory is resolved.

        Returns:
            The resolved package node directory.

        POSTCONDITIONS:
        - MUST derive node directories by extracting package directory paths relative to a workspace root.

        GROUNDING:
        - Invokes bazel_target_labels_ext.resolve_package_dir to convert the DagNode package coordinate into a relative workspace path anchored via file_paths.
        """
        ...
