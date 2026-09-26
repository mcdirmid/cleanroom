from typing import Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
import agent_storage
import bazel_target
import dag_storage
import agent_file_alias
import agent_node_config


@data_type
class TargetManifest(str):
    """Build artifact written by the build system carrying target metadata and file paths."""
    ...


@singleton_type('system')
class BazelManifestLoader(Protocol):
    """System service that resolves manifests into graph structures and node configurations."""

    @operation
    def get_manifest(self, node: dag_storage.DagNode) -> Optional[TargetManifest]:
        """Retrieves the manifest for a node in dag storage.

        REQUIREMENTS:
        - The bazel manifest loader retrieves the manifest for a node in dag storage.

        GROUNDING_PROVISIONS:
        - action("get_manifest", Optional[TargetManifest]): Retrieves manifest for node.
        """
        ...

    @operation
    def load_manifest(self, content: TargetManifest, storage: agent_storage.AgentStorage) -> Sequence[agent_storage.NodeDefinition]:
        """Resolves a manifest into target nodes, dependencies, node definitions, task prompts, and node configurations.

        REQUIREMENTS:
        - A manifest loader resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations, populating the agent storage.
        - A manifest loader resolves declared source files and templates into read-write files and templates in node configurations.
        - A manifest loader resolves declared silent source files into read-write files while excluding them from dependent read-only files.
        - A manifest loader resolves declared direct dependencies into read-only files, and star dependencies into transitive read-only file closures.
        - A manifest loader resolves declared silent dependencies as non-propagating dependencies while excluding their source files from read-only files.
        - A manifest loader resolves declared guide targets into task guides in node configurations.
        - A manifest loader resolves declared feedback dependencies into blame targets mapped to their owning dependency nodes in node configurations.
        - A manifest loader generates node configurations with minimally disambiguated file aliases.
        - A manifest loader synthesizes definitions for declared dependencies lacking explicit manifests.
        - A manifest loader synthesizes promptless pass-through node definitions that act as graph dependencies without propagating changes when a unit's component type is not active for a role.

        GROUNDING_PROVISIONS:
        - action("load_manifest", Sequence[agent_storage.NodeDefinition]): Resolves manifest into storage.
        """
        ...
