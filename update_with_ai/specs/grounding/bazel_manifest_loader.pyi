from typing import Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
import bazel_graph_storage
import bazel_node_id_utils
import dag_storage
import file_alias
import node_config

@data_type
class Manifest(str):
    """
PURPOSE:
Build artifact written by the build system carrying target metadata and file paths
"""
    ...

@singleton_type('system')
class BazelManifestLoader(Protocol):
    """
PURPOSE:
Defined as a system service that resolves manifests into graph structures and node configurations
"""

    @operation
    def get_manifest(self, node: dag_storage.Node) -> Optional[Manifest]:
        """
PURPOSE:
Retrieves the manifest for a node in dag storage

FRESH_REQUIREMENTS:
- The bazel manifest loader retrieves the manifest for a node in dag storage.
"""
        ...

    @operation
    def load_manifest(self, content: Manifest, storage: bazel_graph_storage.BazelGraphStorage) -> Sequence[bazel_graph_storage.NodeDefinition]:
        """
PURPOSE:
Resolves a manifest into target nodes, dependencies, node definitions, task prompts, and node configurations, populating the bazel graph storage

FRESH_REQUIREMENTS:
- A manifest loader resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations using a node identifier utility, populating the bazel graph storage.
- A manifest loader resolves declared source files and templates into read-write files and templates in node configurations.
- A manifest loader resolves declared silent source files into read-write files while excluding them from dependent read-only files.
- A manifest loader resolves declared direct dependencies into read-only files, and star dependencies into transitive read-only file closures.
- A manifest loader resolves declared silent dependencies as non-propagating dependencies while excluding their source files from read-only files.
- A manifest loader resolves declared guide targets into task guides in node configurations.
- A manifest loader resolves declared feedback dependencies into blame targets mapped to their owning dependency nodes in node configurations.
- A manifest loader generates node configurations with minimally disambiguated file aliases.
- A manifest loader synthesizes definitions for declared dependencies lacking explicit manifests.
"""
        ...
