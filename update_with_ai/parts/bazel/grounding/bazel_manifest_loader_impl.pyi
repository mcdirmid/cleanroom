from typing import Optional, Sequence, Self
from framework import operation, override, singleton_type
import agent_storage
import bazel_manifest_loader
import bazel_target
import dag_storage
import agent_file_alias
import json_manifest_ext
import agent_node_config


@singleton_type('system')
class BazelManifestLoader(bazel_manifest_loader.BazelManifestLoader):
    """Implements manifest loader translating JSON target manifests into graph nodes and node configurations.

    GROUNDING_ARGUMENT:
    - As a system singleton, BazelManifestLoader translates target manifests into graph nodes and configurations and interacts with imported agent_storage, bazel_target, and dag_storage in the same system lifecycle tier.
    """

    @operation
    @override
    def get_manifest(self, node: dag_storage.DagNode) -> Optional[bazel_manifest_loader.TargetManifest]:
        """Retrieves target manifest for a node from workspace or runfiles tree.

        REQUIREMENTS:
        - The bazel manifest loader retrieves target manifests from workspace directories or runfiles trees for nodes in dag storage.

        GROUNDING_IMPLEMENTS:
        - action("get_manifest", Optional[bazel_manifest_loader.TargetManifest]): Retrieves manifest.
        """
        ...

    @operation
    @override
    def load_manifest(self, content: bazel_manifest_loader.TargetManifest, storage: agent_storage.AgentStorage) -> Sequence[agent_storage.NodeDefinition]:
        """Resolves target manifests and populates node definitions, graph relationships, and node configurations into agent storage.

        REQUIREMENTS:
        - A manifest loader parses JSON manifests using the filesystem into json manifest records.
        - A manifest loader normalizes node references into canonical nodes.
        - A manifest loader resolves package-relative file paths against target package directories.
        - A manifest loader maps declared source files, templates, and silent source files into read-write files and template entries.
        - A manifest loader expands direct dependencies and star dependencies into read-only files.
        - A manifest loader registers silent dependencies as non-propagating dependencies excluding their source files.
        - A manifest loader resolves guide targets into task guides and feedback dependencies into blame targets.
        - A manifest loader derives file aliases for all accessible workspace files.
        - A manifest loader synthesizes node definitions for referenced dependency targets lacking manifests.
        - A manifest loader resolves target manifests by loading unit manifests and role manifests to synthesize node definitions and dependencies across unit and role dimensions.
        - A manifest loader synthesizes target node manifests with templates, template parameters, declared dependencies, feedback dependencies, silent dependencies, and star dependencies across unit and role dimensions.
        - A manifest loader evaluates role source patterns and task prompt templates parameterized with unit metadata to configure synthesized nodes.
        - A manifest loader synthesizes promptless pass-through node definitions that act as graph dependencies without propagating changes when a unit's component type is not active for a role.

        GROUNDING_PROVISIONS:
        - action("load_manifest", Sequence[agent_storage.NodeDefinition]): Resolves target manifests into storage.

        GROUNDING_ARGUMENT:
        - action("load_manifest", Self) :- action("normalize", bazel_target.BazelTarget), action("extract_directory", bazel_target.BazelTarget), action("add_message", agent_storage.AgentStorage), action("register_dependent", agent_storage.AgentStorage).
        """
        ...
