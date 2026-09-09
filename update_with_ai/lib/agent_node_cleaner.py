from typing import Protocol, Set
from . import dag_node_cleaner
from . import dag_storage

class AgentNodeCleaner(dag_node_cleaner.NodeCleaner, Protocol):
    def clean_node(self, node: dag_storage.Node) -> Set[dag_storage.Message]:
        ...


