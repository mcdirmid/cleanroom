# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: 6a6efd33ddca
# --- END CLEANROOM METADATA ---

from dataclasses import dataclass
from typing import NewType, Protocol
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib import dag_storage

TargetIdentifier = NewType("TargetIdentifier", str)


@dataclass(frozen=True)
class NodeDirectory(file_paths.WorkspacePath):
    pass


class UvTarget(Protocol):
    def normalize_target(
        self, target_identifier: TargetIdentifier
    ) -> dag_storage.DagNode: ...

    def extract_node_dir(self, node: dag_storage.DagNode) -> NodeDirectory: ...
