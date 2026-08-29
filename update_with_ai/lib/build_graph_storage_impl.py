# lib/build_graph_storage_impl.py
"""
Implementation of the LLS BuildGraphStorage interface.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Tuple
import os
from pathlib import Path

from .build_graph_storage import (
    BuildGraphStorage,
    GraphConfig,
    NodeDefinition,
    NodeId,
    PackageDirectory,
    GraphSource,
)
from .dag_storage import (
    NodeMessage,
    MessageKind,
    PendingMessages,
    NodeDependencies,
    KnownReverseDependencies,
)
from .build_message_store import BuildMessageStore
from .manifest_node_loader import ManifestNodeLoader


class BaseBuildGraphStorageImpl(BuildGraphStorage):
    """
    Base class providing DAG storage operations over a message store and graph definitions.
    """

    def __init__(
        self,
        config: GraphConfig,
        message_store: BuildMessageStore,
        manifest_loader: ManifestNodeLoader,
    ) -> None:
        self._config = config
        self.message_store: BuildMessageStore = message_store
        self.manifest_loader: ManifestNodeLoader = manifest_loader
        self._graph_source: GraphSource = self._resolve_graph_source()
        self._adjacency: Dict[NodeId, List[NodeId]] = self._build_adjacency()
        self._propagating_deps: Dict[NodeId, List[NodeId]] = self._build_propagating_deps()
        self._definitions: Dict[NodeId, NodeDefinition] = self._build_definitions()
        self._package_dirs: Dict[NodeId, PackageDirectory] = self._build_package_dirs()

    def _resolve_graph_source(self) -> GraphSource:
        if self._config.graph_source is not None:
            return self._config.graph_source
        if self._config.workspace_root is not None:
            return self._config.workspace_root
        raise ValueError(
            "GraphConfig must provide at least one of graph_source or workspace_root"
        )

    def _build_adjacency(self) -> Dict[NodeId, List[NodeId]]:
        raise NotImplementedError("Subclasses must implement _build_adjacency")

    def _build_propagating_deps(self) -> Dict[NodeId, List[NodeId]]:
        raise NotImplementedError("Subclasses must implement _build_propagating_deps")

    def _build_definitions(self) -> Dict[NodeId, NodeDefinition]:
        raise NotImplementedError("Subclasses must implement _build_definitions")

    def _build_package_dirs(self) -> Dict[NodeId, PackageDirectory]:
        raise NotImplementedError("Subclasses must implement _build_package_dirs")

    def resolve_node_definition(self, node_id: NodeId) -> NodeDefinition:
        definition = self._definitions.get(node_id)
        if definition is None:
            raise ValueError(f"Unknown node: {node_id}")
        return definition

    def resolve_package_directory(self, node_id: NodeId) -> PackageDirectory:
        package_dir = self._package_dirs.get(node_id)
        if package_dir is None:
            raise ValueError(f"Unknown node: {node_id}")
        return package_dir

    def get_pending_messages(self, node_id: NodeId) -> PendingMessages:
        pkg_dir = self.resolve_package_directory(node_id)
        return self.message_store.get_pending_messages(pkg_dir, node_id)

    def add_messages(self, node_id: NodeId, messages: List[NodeMessage]) -> None:
        pkg_dir = self.resolve_package_directory(node_id)
        for msg in messages:
            self.message_store.add_pending_message(pkg_dir, node_id, msg)

    def clear_pending_messages(self, node_id: NodeId) -> None:
        pkg_dir = self.resolve_package_directory(node_id)
        self.message_store.clear_pending_messages(pkg_dir, node_id)

    def delete_node_data(self, node_id: NodeId) -> None:
        pkg_dir = self.resolve_package_directory(node_id)
        self.message_store.delete_node_messages(pkg_dir, node_id)

    def get_node_dependencies(self, node_id: NodeId) -> NodeDependencies:
        deps = self._adjacency.get(node_id)
        if deps is None:
            raise ValueError(f"Unknown node: {node_id}")
        for dep in self._propagating_deps.get(node_id, deps):
            dep_pkg = self.resolve_package_directory(dep)
            self.message_store.add_known_reverse_dependency(dep_pkg, dep, node_id)
        return list(deps)

    def get_known_reverse_dependencies(self, node_id: NodeId) -> KnownReverseDependencies:
        pkg_dir = self.resolve_package_directory(node_id)
        return self.message_store.get_known_reverse_dependencies(pkg_dir, node_id)

    def get_subgraph(self, root_node: NodeId) -> List[NodeId]:
        if root_node not in self._adjacency:
            raise ValueError(f"Unknown node: {root_node}")
        visited: Set[NodeId] = set()
        order: List[NodeId] = []

        def dfs(curr: NodeId) -> None:
            visited.add(curr)
            for dep in self._adjacency.get(curr, []):
                if dep not in visited:
                    dfs(dep)
            order.append(curr)

        dfs(root_node)
        return order

    def get_propagating_dependencies(self, node_id: NodeId) -> NodeDependencies:
        if node_id not in self._adjacency:
            raise ValueError(f"Unknown node: {node_id}")
        return list(self._propagating_deps.get(node_id, self._adjacency.get(node_id, [])))

    def clear_known_reverse_dependencies(self, node_id: NodeId) -> None:
        pkg_dir = self.resolve_package_directory(node_id)
        self.message_store.clear_known_reverse_dependencies(pkg_dir, node_id)


class BuildGraphStorageFileImpl(BaseBuildGraphStorageImpl):
    """
    File-based implementation that reads node manifests from the workspace.
    """

    def __init__(
        self,
        config: GraphConfig,
        message_store: Optional[BuildMessageStore] = None,
        manifest_loader: Optional[ManifestNodeLoader] = None,
    ) -> None:
        if config.workspace_root is None:
            raise ValueError("BuildGraphStorageFileImpl requires workspace_root in config")

        loaded = manifest_loader.resolve_graph(config)

        self._definitions = loaded.node_definitions
        self._adjacency = loaded.node_dependencies
        self._package_dirs = loaded.package_directories
        self._propagating_deps = loaded.propagating_dependencies

        super().__init__(config, message_store=message_store, manifest_loader=manifest_loader)

    def _build_adjacency(self) -> Dict[NodeId, List[NodeId]]:
        return self._adjacency

    def _build_propagating_deps(self) -> Dict[NodeId, List[NodeId]]:
        return self._propagating_deps

    def _build_definitions(self) -> Dict[NodeId, NodeDefinition]:
        return self._definitions

    def _build_package_dirs(self) -> Dict[NodeId, PackageDirectory]:
        return self._package_dirs
