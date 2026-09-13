from typing import Protocol
from dataclasses import dataclass
from . import dag_storage
from . import file_paths

@dataclass(frozen=True, init=False)
class NodeDirectory(file_paths.WorkspacePath):
    pass

class BazelTarget(Protocol):
    def normalize(self, raw_label: str) -> dag_storage.Node:
        ...

    def extract_directory(self, node: dag_storage.Node) -> NodeDirectory:
        ...
