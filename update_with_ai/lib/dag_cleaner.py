"""DAG cleaner interface for topological graph cleaning."""

from typing import Protocol
from .dag_storage import DagStorage, NodeId
from .dag_node_cleaner import NodeCleaner


class DagCleaner(Protocol):
    def clean_subgraph(
        self,
        root: NodeId,
        storage: DagStorage,
        cleaner: NodeCleaner,
    ) -> None:
        ...
