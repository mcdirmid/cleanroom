from typing import Protocol
from dataclasses import dataclass
from . import dag_storage
from . import file_alias

@dataclass(frozen=True)
class NodeDirectory(file_alias.DirectoryPath):
    pass

class BazelNodeIdentifierUtility(Protocol):
    def normalize(self, raw_label: str) -> dag_storage.Node:
        ...

    def extract_directory(self, node: dag_storage.Node) -> NodeDirectory:
        ...

