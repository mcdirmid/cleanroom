# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: 6a6efd33ddca
# --- END CLEANROOM METADATA ---

from dataclasses import dataclass
from typing import NewType, Protocol
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib import dag_storage

TargetIdentifier = NewType("TargetIdentifier", str)


# Contract: workspace package directory containing a node
@dataclass(frozen=True)
class NodeDirectory(file_paths.WorkspacePath):
    pass


class UvTarget(Protocol):
    # Contract: normalize arbitrary target identifier string into a canonical node
    def normalize_target(
        self, target_identifier: TargetIdentifier
    ) -> dag_storage.DagNode: ...

    # Contract: extract workspace package directory of a node
    def extract_node_dir(self, node: dag_storage.DagNode) -> NodeDirectory: ...
