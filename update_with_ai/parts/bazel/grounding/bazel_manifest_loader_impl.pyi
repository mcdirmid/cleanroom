from typing import Optional, Sequence
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
    """
PURPOSE:
Implements manifest loader translating JSON target manifests into graph nodes and node configurations

GROUNDING_ARGUMENT:
- As a system singleton, BazelManifestLoader translates target manifests into graph nodes and configurations and interacts with imported agent_storage, bazel_target, and dag_storage in the same system lifecycle tier.
"""

    @operation
    @override
    def get_manifest(self, node: dag_storage.Node) -> Optional[bazel_manifest_loader.Manifest]:
        """
PURPOSE:
Retrieves target manifest for a node from workspace or runfiles tree

FRESH_REQUIREMENTS:
- The bazel manifest loader retrieves target manifests from workspace directories or runfiles trees for nodes in dag storage.

INHERITED_REQUIREMENTS:
- [BazelManifestLoader] The bazel manifest loader retrieves the manifest for a node in dag storage.

GROUNDING_ARGUMENT:
- Receives node as a parameter and reads manifest JSON from the filesystem in the workspace directory or runfiles tree.
"""
        ...

    @operation
    @override
    def load_manifest(self, content: bazel_manifest_loader.Manifest, storage: agent_storage.AgentStorage) -> Sequence[agent_storage.NodeDefinition]:
        """
PURPOSE:
Resolves target manifests and populates node definitions, graph relationships, and node configurations into agent storage

FRESH_REQUIREMENTS:
- A manifest loader parses JSON manifests using the filesystem into json manifest records.
- A manifest loader normalizes node references into canonical nodes using node identifier utilities.
- A manifest loader resolves package-relative file paths against target package directories.
- A manifest loader maps declared source files, templates, and silent source files into read-write files and template entries.
- A manifest loader expands direct dependencies and star dependencies into read-only files.
- A manifest loader registers silent dependencies as non-propagating dependencies excluding their source files.
- A manifest loader resolves guide targets into task guides and feedback dependencies into blame targets.
- A manifest loader derives file aliases for all accessible workspace files.
- A manifest loader synthesizes node definitions for referenced dependency targets lacking manifests.

INHERITED_REQUIREMENTS:
- [BazelManifestLoader] A manifest loader resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations using a node identifier utility, populating the agent storage.
- [BazelManifestLoader] A manifest loader resolves declared source files and templates into read-write files and templates in node configurations.
- [BazelManifestLoader] A manifest loader resolves declared silent source files into read-write files while excluding them from dependent read-only files.
- [BazelManifestLoader] A manifest loader resolves declared direct dependencies into read-only files, and star dependencies into transitive read-only file closures.
- [BazelManifestLoader] A manifest loader resolves declared silent dependencies as non-propagating dependencies while excluding their source files from read-only files.
- [BazelManifestLoader] A manifest loader resolves declared guide targets into task guides in node configurations.
- [BazelManifestLoader] A manifest loader resolves declared feedback dependencies into blame targets mapped to their owning dependency nodes in node configurations.
- [BazelManifestLoader] A manifest loader generates node configurations with minimally disambiguated file aliases.
- [BazelManifestLoader] A manifest loader synthesizes definitions for declared dependencies lacking explicit manifests.

GROUNDING_ARGUMENT:
- Receives content and storage as arguments, uses imported bazel_target (in the same system lifecycle tier) to normalize target labels and derive directories, and populates node definitions, dependencies, and configurations into the provided AgentStorage.
"""
        ...
