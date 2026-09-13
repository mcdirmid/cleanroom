from typing import Any, List, Mapping, Optional, Sequence, Set, Tuple, Type
from framework import operation, override, singleton_type
import bazel_manifest_loader
import dag_node_cleaner
import dag_storage
import file_alias
import file_paths
import model_config
import node_config
import tool_provider

@singleton_type('agent_session')
class NodeConfig(node_config.NodeConfig):
    """
PURPOSE:
Implements node config from node manifest metadata

GROUNDING_ARGUMENT:
- As an agent_session singleton, NodeConfig accesses the target node from dag_node_cleaner.CleanedNode.node and loads its manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(node) during session initialization, deriving session file sets, templates, and guidance configurations.
"""

    @property
    @override
    def read_only_files(self) -> Set[file_alias.BoundFile]:
        """
PURPOSE:
Declared direct dependencies and transitive star dependencies

FRESH_REQUIREMENTS:
- The node config exposes declared direct dependencies and transitive star dependencies resolved across dependency manifests using the bazel manifest loader as the session's read-only files, excluding silent dependencies.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session read-only files restricted to inspection.

GROUNDING_ARGUMENT:
- Derived by loading the target node's manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(get_singleton(dag_node_cleaner.CleanedNode).node), extracting direct dependencies and resolving the transitive closure of star dependencies across manifests via the manifest loader, and constructing ReadOnlyFile instances.
"""
        ...

    @property
    @override
    def read_write_files(self) -> Set[file_alias.BoundFile]:
        """
PURPOSE:
Declared source files and silent source files

FRESH_REQUIREMENTS:
- The node config exposes declared source files and silent source files as read-write files.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session read-write files permitted for inspection and modification.

GROUNDING_ARGUMENT:
- Derived by loading the target node's manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(get_singleton(dag_node_cleaner.CleanedNode).node), extracting declared source files and silent source files, and constructing ReadWriteFile instances.
"""
        ...

    @property
    @override
    def allows_step_mode(self) -> bool:
        """
PURPOSE:
Whether the node allows step mode from the manifest

FRESH_REQUIREMENTS:
- The node config exposes whether the node allows step mode from the target node manifest.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config indicates whether the node allows step mode.

GROUNDING_ARGUMENT:
- Derived by loading the target node manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(get_singleton(dag_node_cleaner.CleanedNode).node) and extracting allows_step_mode.
"""
        ...

    @property
    @override
    def is_step_mode(self) -> bool:
        """
PURPOSE:
Whether step mode is active for the session

FRESH_REQUIREMENTS:
- The node config exposes whether step mode is active, enabled when the model config enables step mode, the node allows step mode, and session feedback is absent.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config indicates whether session step mode is active.

GROUNDING_ARGUMENT:
- Derived by querying model_config.ModelConfig.is_step_mode in the system lifecycle tier, self.allows_step_mode, and verifying that self.feedback is empty, enabling step mode only when all conditions are satisfied.
"""
        ...

    @property
    @override
    def guide_file(self) -> Optional[file_alias.UnboundFile]:
        """
PURPOSE:
Guide file configured when step mode is active

FRESH_REQUIREMENTS:
- The node config exposes the declared guide target as the guide file when step mode is active.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session guide file when step mode is active.

GROUNDING_ARGUMENT:
- Derived by loading the target node's manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(get_singleton(dag_node_cleaner.CleanedNode).node), constructing an UnboundFile for the declared guide target when step mode is active.
"""
        ...

    @property
    @override
    def templates(self) -> Set[Tuple[file_alias.BoundFile, file_alias.FileContent]]:
        """
PURPOSE:
Startup template mappings for declared source files

FRESH_REQUIREMENTS:
- The node config exposes templates mapping read-write files to initial file content.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides templates mapping read-write files to initial file content.

GROUNDING_ARGUMENT:
- Derived by loading the target node's manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(get_singleton(dag_node_cleaner.CleanedNode).node), pairing read-write files with template contents.
"""
        ...

    @property
    @override
    def template_parameters(self) -> Mapping[str, Any]:
        """
PURPOSE:
Declared template parameters from the manifest

FRESH_REQUIREMENTS:
- The node config exposes declared template parameters from the manifest.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session template parameters, providing parameter bindings for template evaluation.

GROUNDING_ARGUMENT:
- Extracted from the target node manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(get_singleton(dag_node_cleaner.CleanedNode).node).
"""
        ...

    @property
    @override
    def guide(self) -> Optional[node_config.Guide]:
        """
PURPOSE:
Task guide configured when step mode is active

FRESH_REQUIREMENTS:
- The node config exposes the declared guide target as the task guide when step mode is active.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session guide, providing structured instructional text when step mode is active.

GROUNDING_ARGUMENT:
- Derived by loading the target node's manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(get_singleton(dag_node_cleaner.CleanedNode).node), reading and parsing the guide markdown when step mode is active.
"""
        ...

    @property
    @override
    def blame_targets(self) -> Set[file_alias.BoundFile]:
        """
PURPOSE:
Blame targets mapped to owning dependency nodes

FRESH_REQUIREMENTS:
- The node config exposes declared feedback dependencies as blame targets mapped to owning dependency nodes.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides blame targets eligible for defect attribution.

GROUNDING_ARGUMENT:
- Derived by loading the target node's manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(get_singleton(dag_node_cleaner.CleanedNode).node), mapping declared feedback dependencies to ReadOnlyFile blame targets.
"""
        ...

    @property
    @override
    def verification_checks(self) -> List[node_config.VerificationCheck]:
        """
PURPOSE:
Session verification checks derived from the manifest verification command

FRESH_REQUIREMENTS:
- The node config exposes declared verification checks from the manifest verification command.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session verification checks evaluated during session advancement.

GROUNDING_ARGUMENT:
- Derived by loading the target node's manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(get_singleton(dag_node_cleaner.CleanedNode).node), constructing a CommandVerificationCheck from the declared verify command string when present.
"""
        ...

    @property
    @override
    def verification_success_message(self) -> Optional[str]:
        """
PURPOSE:
Session verification success message resolved from manifest metadata

FRESH_REQUIREMENTS:
- Declared verification success message from the manifest as the session verification success message.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session verification success message when configured.

GROUNDING_ARGUMENT:
- Derived by loading the target node's manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(get_singleton(dag_node_cleaner.CleanedNode).node), extracting the declared verification_success_message string when present.
"""
        ...

    @property
    @override
    def feedback(self) -> Sequence[str]:
        """
PURPOSE:
Session feedback retrieved from graph storage for the target node

FRESH_REQUIREMENTS:
- Declared feedback messages retrieved from graph storage for the target node as the session feedback.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session feedback, exposing incoming feedback delivered to the node when present.

GROUNDING_ARGUMENT:
- Derived by querying dag_storage.DagStorage for incoming feedback messages for get_singleton(dag_node_cleaner.CleanedNode).node.
"""
        ...

@singleton_type('agent_session')
class AliasManager(file_alias.AliasManager):
    """
PURPOSE:
Implements alias manager with minimal unambiguous short names

INHERITANCE:
- tool_provider.ParameterConverter: Implements parameter converter for file alias actual type

GROUNDING_ARGUMENT:
- As an agent_session singleton, AliasManager resolves accessible workspace files for get_singleton(dag_node_cleaner.CleanedNode).node into minimal unambiguous short names and maintains host path mappings.
"""

    @property
    @override
    def actual_type(self) -> Type:
        """
PURPOSE:
FileAlias actual type

GROUNDING_ARGUMENT:
- Constant type descriptor identifying FileAlias.
"""
        ...

    @property
    @override
    def wire_type(self) -> tool_provider.WireType:
        """
PURPOSE:
String wire type

GROUNDING_ARGUMENT:
- Constant wire type descriptor identifying WireType.STRING.
"""
        ...

    @operation
    @override
    def convert(self, wire_value: str) -> file_alias.FileAlias:
        """
PURPOSE:
Converts short names to matching file aliases

FRESH_REQUIREMENTS:
- The alias manager converts short names to matching file aliases, producing unbound files when unmapped.

INHERITED_REQUIREMENTS:
- [AliasManager] Converting a wire type string produces the matching file alias if its short name is found, and produces an unbound file if the short name is not found.

GROUNDING_ARGUMENT:
- Receives wire_value string directly as a parameter and looks up the corresponding file alias in session mappings on self, returning an unbound file if not found.
"""
        ...

    @operation
    @override
    def sanitize_text(self, text: str) -> str:
        """
PURPOSE:
Masks occurrences of relative workspace paths and preceding path prefixes with minimal short names

FRESH_REQUIREMENTS:
- The alias manager sanitizes output text by masking occurrences of each file's relative workspace path and any preceding path prefix with its minimal short name, using performant regular expression patterns that disallow directory separators within prefix segments to prevent catastrophic backtracking.

INHERITED_REQUIREMENTS:
- [AliasManager] Sanitizing text masks occurrences of relative workspace paths and preceding path prefixes with the corresponding file alias short names.

GROUNDING_ARGUMENT:
- Receives text directly as a parameter and replaces relative workspace paths and preceding path prefixes with corresponding minimal short names stored on self.
"""
        ...

    @property
    @override
    def workspace_root(self) -> file_paths.WorkspaceRoot:
        """
PURPOSE:
Established that the alias manager is configured with a workspace root

GROUNDING_ARGUMENT:
- Resolved from physical workspace directory configured at session startup via file_paths.WorkspaceRoot.
"""
        ...
