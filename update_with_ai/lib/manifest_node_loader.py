# lib/manifest_node_loader.py
"""
Interface definitions for the LLS ManifestNodeLoader.
"""

from typing import Dict, List, Optional, Protocol, Tuple, TypeAlias
from dataclasses import dataclass

from .build_graph_storage import NodeDefinition, PackageDirectory, GraphConfig
from .dag_storage import NodeId, NodeDependencies


@dataclass
class LoadedGraphManifests:
    node_definitions: Dict[NodeId, NodeDefinition]
    node_dependencies: Dict[NodeId, NodeDependencies]
    package_directories: Dict[NodeId, PackageDirectory]
    propagating_dependencies: Dict[NodeId, NodeDependencies]
    silent_dependencies: Dict[NodeId, NodeDependencies]


class ManifestNodeLoader(Protocol):
    def resolve_graph(self, config: GraphConfig) -> LoadedGraphManifests:
        ...
