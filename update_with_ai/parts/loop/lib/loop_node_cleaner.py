from typing import Protocol, Sequence
from update_with_ai.parts.dag.lib import dag_storage


class NodeCleaner(Protocol):
    def clean(self, nodes: Sequence[dag_storage.Node]) -> bool: ...


class CleanedNodes(Protocol):
    @property
    def nodes(self) -> Sequence[dag_storage.Node]: ...

