# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: aaf46d04b0b3
# --- END CLEANROOM METADATA ---

"""Bazel target low-level interface specification."""

from typing import NewType, Protocol
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import dag_storage
import file_paths

TargetIdentifier = NewType("TargetIdentifier", str)


@data_type
class NodeDirectory(file_paths.WorkspacePath):
    """Workspace package directory containing a node."""
    ...


@singleton_type("system")
class BazelTarget(InTier[SystemTier], Protocol):
    """Normalizes Bazel target labels and extracts package directories."""

    @operation
    def normalize_target(self, target_identifier: TargetIdentifier) -> dag_storage.DagNode:
        """Normalizes an arbitrary target identifier string into a canonical node.

        Args:
            target_identifier: The raw target label or shorthand string.

        Returns:
            The canonical dag node.

        POSTCONDITIONS:
        - MUST normalize an arbitrary Bazel target identifier string into a canonical node.
        """
        ...

    @operation
    def extract_node_dir(self, node: dag_storage.DagNode) -> NodeDirectory:
        """Extracts the workspace package directory of a node.

        Args:
            node: The node whose package directory is extracted.

        Returns:
            The workspace package directory path.

        POSTCONDITIONS:
        - MUST extract a node directory from a node.
        """
        ...
