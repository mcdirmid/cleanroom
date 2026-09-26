# Requirements specified in bazel_target.pyi
from typing import Protocol
from dataclasses import dataclass
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.core.lib import file_paths


@dataclass(frozen=True, init=False)
class NodeDirectory(file_paths.WorkspacePath):
    pass


class BazelTarget(Protocol):
    def normalize(self, raw_label: str) -> dag_storage.DagNode: ...

    def extract_directory(self, node: dag_storage.DagNode) -> NodeDirectory: ...
