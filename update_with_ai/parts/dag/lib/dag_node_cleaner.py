from typing import Protocol, Sequence
from . import dag_storage


class NodeCleaner(Protocol):
    def clean(self, nodes: Sequence[dag_storage.Node]) -> bool: ...


class CleanedNodes(Protocol):
    @property
    def nodes(self) -> Sequence[dag_storage.Node]: ...

    @property
    def primary_node(self) -> dag_storage.Node: ...
