# lib/build_message_store.py
"""
Interface definitions for the LLS BuildMessageStore.
"""

from typing import Dict, List, Optional, Protocol, Tuple, TypeAlias
from .dag_storage import NodeId, NodeMessage, PendingMessages, KnownReverseDependencies
from .build_graph_storage import PackageDirectory

PackageMessageData: TypeAlias = Dict[NodeId, Tuple[PendingMessages, KnownReverseDependencies]]


class BuildMessageStore(Protocol):
    def read_package_messages(self, package_dir: PackageDirectory) -> PackageMessageData:
        ...

    def write_package_messages(self, package_dir: PackageDirectory, data: PackageMessageData) -> None:
        ...

    def get_pending_messages(self, package_dir: PackageDirectory, node: NodeId) -> PendingMessages:
        ...

    def add_pending_message(self, package_dir: PackageDirectory, node: NodeId, message: NodeMessage) -> None:
        ...

    def set_pending_messages(self, package_dir: PackageDirectory, node: NodeId, messages: PendingMessages) -> None:
        ...

    def clear_pending_messages(self, package_dir: PackageDirectory, node: NodeId) -> None:
        ...

    def delete_node_messages(self, package_dir: PackageDirectory, node: NodeId) -> None:
        ...

    def get_known_reverse_dependencies(self, package_dir: PackageDirectory, node: NodeId) -> KnownReverseDependencies:
        ...

    def add_known_reverse_dependency(self, package_dir: PackageDirectory, node: NodeId, reverse_dep: NodeId) -> None:
        ...

    def clear_known_reverse_dependencies(self, package_dir: PackageDirectory, node: NodeId) -> None:
        ...
