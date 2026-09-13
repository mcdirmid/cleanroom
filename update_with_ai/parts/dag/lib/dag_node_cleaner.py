from typing import Protocol
from . import dag_storage

class NodeCleaner(Protocol):
    def clean(self, node: dag_storage.Node) -> bool:
        ...

class CleanedNode(Protocol):
    @property
    def node(self) -> dag_storage.Node:
        ...

