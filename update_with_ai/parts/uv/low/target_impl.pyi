# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: bca872dec6f9
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Cleanroom target implementation low-level specification."""

from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
from update_with_ai.parts.dag.lib import dag_storage
from . import target
import dag_storage
import file_paths


@singleton_type("system")
class UvTarget(target.UvTarget, InTier[SystemTier]):
    """Realizes Cleanroom label canonicalization and package directory resolution.

    GROUNDING:
    - Realizes target interface contracts by delegating label normalization and package directory resolution to target_labels_ext.
    """

    @operation
    @override
    def normalize_target(self, target_identifier: target.TargetIdentifier) -> dag_storage.DagNode:
        """Normalizes raw target labels into canonical nodes.

        Args:
            target_identifier: The raw target label string.

        Returns:
            The normalized dag node.

        POSTCONDITIONS:
        - MUST strip repository qualifiers and expand omitted target names into canonical nodes.

        GROUNDING:
        - Invokes target_labels_ext.normalize_label to strip repository prefixes and expand omitted target names into canonical DagNode coordinates.
        """
        ...

    @operation
    @override
    def extract_node_dir(self, node: dag_storage.DagNode) -> target.NodeDirectory:
        """Derives package directory paths relative to the workspace root.

        Args:
            node: The node whose package directory is resolved.

        Returns:
            The resolved package node directory.

        POSTCONDITIONS:
        - MUST derive node directories by extracting package directory paths relative to a workspace root.

        GROUNDING:
        - Invokes target_labels_ext.resolve_package_dir to convert the DagNode package coordinate into a relative workspace path anchored via file_paths.
        """
        ...
