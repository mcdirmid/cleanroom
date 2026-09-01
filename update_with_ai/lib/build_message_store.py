"""Build message store interface for package-directory DAG storage."""

from typing import Protocol
from .dag_storage import DagStorage, NodeId
from .node_id_utils import NodeDirectory


class BuildMessageStore(DagStorage, Protocol):
    def get_package_directory(self, node: NodeId) -> NodeDirectory:
        ...
