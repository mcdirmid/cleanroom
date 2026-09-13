from typing import Protocol
from . import dag_node_cleaner
from . import dag_storage


class DagCleaner(Protocol):
    def clean(
        self, node: dag_storage.Node, cleaner: dag_node_cleaner.NodeCleaner
    ) -> None: ...
