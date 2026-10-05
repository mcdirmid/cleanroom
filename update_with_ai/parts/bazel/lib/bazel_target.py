# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 09dc733c624d
# --- END CLEANROOM METADATA ---

# Requirements specified in bazel_target.pyi
from dataclasses import dataclass
from typing import NewType, Protocol
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib import dag_storage

TargetIdentifier = NewType("TargetIdentifier", str)


@dataclass(frozen=True)
class NodeDirectory(file_paths.WorkspacePath):
    pass


class BazelTarget(Protocol):
    def normalize_target(
        self, target_identifier: TargetIdentifier
    ) -> dag_storage.DagNode: ...

    def extract_node_dir(self, node: dag_storage.DagNode) -> NodeDirectory: ...
