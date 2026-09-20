# Requirements specified in loop_node_cleaner.pyi
from typing import Protocol, Sequence
from update_with_ai.parts.dag.lib import dag_storage


class NodeCleaner(Protocol):
    def clean(self, nodes: Sequence[dag_storage.Node]) -> bool: ...

