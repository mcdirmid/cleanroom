# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 00a36e4aa3bc
# GROUNDING_QA_AUDIT: 2026-10-05T04:28:01Z
# --- END CLEANROOM METADATA ---

"""Bazel target grounding specification module."""

from __future__ import annotations
from dataclasses import dataclass
from typing import NewType, Protocol
from support.lib.grounding_support import InTier, SystemTier
from parts.core.grounding import file_paths
from parts.dag.grounding import dag_storage

TargetIdentifier = NewType("TargetIdentifier", str)


@dataclass(frozen=True)
class NodeDirectory(file_paths.WorkspacePath):
    """Workspace package directory containing a node."""

    pass


class BazelTarget(InTier[SystemTier], Protocol):
    """Normalizes Bazel target labels and extracts package directories."""

    def normalize_target(
        self, target_identifier: TargetIdentifier
    ) -> dag_storage.DagNode:
        """
        COVERED:
        - MUST normalize an arbitrary Bazel target identifier string into a canonical node.
          - Consequent knowledge: return DagNode record.

        DEFERRED:
        - Label parsing and repository qualifier stripping deferred to bazel_target_impl.py.
        """
        _node = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress(str(target_identifier)),
            role_address=dag_storage.RoleAddress(""),
        )
        raise NotImplementedError

    def extract_node_dir(self, node: dag_storage.DagNode) -> NodeDirectory:
        """
        COVERED:
        - MUST extract a node directory from a node.
          - Consequent knowledge: construct NodeDirectory record.

        DEFERRED:
        - Package path extraction deferred to bazel_target_impl.py.
        """
        _dir = NodeDirectory(path=file_paths.PathString("pkg"))
        raise NotImplementedError
