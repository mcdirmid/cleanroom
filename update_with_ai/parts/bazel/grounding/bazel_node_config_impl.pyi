from typing import Any, List, Mapping, Optional, Sequence, Set, Tuple, Type
from framework import operation, override, singleton_type
import bazel_manifest_loader
import loop_node_cleaner
import dag_storage
import agent_file_alias
import file_paths
import agent_config
import agent_node_config
import tool_provider

@singleton_type('agent_session')
class NodeConfig(agent_node_config.NodeConfig):
    """
PURPOSE:
Implements node config from node manifest metadata

GROUNDING_ARGUMENT:
- As an agent_session singleton, NodeConfig accesses target nodes from loop_node_cleaner.CleanedNodes.nodes and loads their manifests via bazel_manifest_loader.BazelManifestLoader.get_manifest during session initialization, deriving session file sets, templates, and guidance configurations.
"""

    @property
    @override
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """
PURPOSE:
Declared direct dependencies and transitive star dependencies

FRESH_REQUIREMENTS:
- The node config exposes declared direct dependencies and transitive star dependencies resolved across dependency manifests using the bazel manifest loader as the session's read-only files, excluding silent dependencies and files present in read-write files.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session read-only files restricted to inspection.

GROUNDING_ARGUMENT:
- Derived by loading target node manifests via bazel_manifest_loader.BazelManifestLoader.get_manifest across nodes in get_singleton(loop_node_cleaner.CleanedNodes).nodes, extracting direct dependencies and resolving the transitive closure of star dependencies across manifests, and constructing ReadOnlyFile instances excluding files present in read_write_files.
"""
        ...

    @property
    @override
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """
PURPOSE:
Declared source files and silent source files across session nodes

FRESH_REQUIREMENTS:
- The node config exposes declared source files and silent source files across session nodes as read-write files.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session read-write files permitted for inspection and modification.

GROUNDING_ARGUMENT:
- Derived by loading target node manifests via bazel_manifest_loader.BazelManifestLoader.get_manifest across nodes in get_singleton(loop_node_cleaner.CleanedNodes).nodes, extracting declared source files and silent source files, and constructing ReadWriteFile instances.
"""
        ...

    @property
    @override
    def allows_step_mode(self) -> bool:
        """
PURPOSE:
Whether the node allows step mode from the primary node manifest

FRESH_REQUIREMENTS:
- The node config exposes whether the node allows step mode from the primary target node manifest.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config indicates whether the node allows step mode.

GROUNDING_ARGUMENT:
- Derived by loading the primary target node manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(get_singleton(loop_node_cleaner.CleanedNodes).primary_node) and extracting allows_step_mode.
"""
        ...

    @property
    @override
    def is_step_mode(self) -> bool:
        """
PURPOSE:
Whether step mode is active for the session

FRESH_REQUIREMENTS:
- The node config exposes whether step mode is active, enabled when the agent config enables step mode, the session contains exactly one node, the primary node allows step mode, and session feedback is absent.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config indicates whether session step mode is active.

GROUNDING_ARGUMENT:
- Derived by querying agent_config.AgentConfig.is_step_mode in the system lifecycle tier, verifying that get_singleton(loop_node_cleaner.CleanedNodes).nodes contains exactly one node, checking self.allows_step_mode, and verifying that self.feedback is empty.
"""
        ...

    @property
    @override
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        """
PURPOSE:
Guide file configured when step mode is active

FRESH_REQUIREMENTS:
- The node config exposes the declared guide target as the guide file when step mode is active.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session guide file when step mode is active.

GROUNDING_ARGUMENT:
- Derived by loading the primary target node manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(get_singleton(loop_node_cleaner.CleanedNodes).primary_node), constructing an UnboundFile for the declared guide target when step mode is active.
"""
        ...

    @property
    @override
    def templates(self) -> Set[Tuple[agent_file_alias.BoundFile, agent_file_alias.FileContent]]:
        """
PURPOSE:
Startup template mappings for declared source files

FRESH_REQUIREMENTS:
- The node config exposes templates mapping read-write files to initial file content.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides templates mapping read-write files to initial file content.

GROUNDING_ARGUMENT:
- Derived by loading target node manifests via bazel_manifest_loader.BazelManifestLoader.get_manifest across nodes in get_singleton(loop_node_cleaner.CleanedNodes).nodes, pairing read-write files with template contents.
"""
        ...

    @property
    @override
    def template_parameters(self) -> Mapping[str, Any]:
        """
PURPOSE:
Declared template parameters from the manifest

FRESH_REQUIREMENTS:
- The node config exposes declared template parameters from the primary target node manifest.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session template parameters, providing parameter bindings for template evaluation.

GROUNDING_ARGUMENT:
- Extracted from the primary target node manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(get_singleton(loop_node_cleaner.CleanedNodes).primary_node).
"""
        ...

    @property
    @override
    def guide(self) -> Optional[agent_node_config.Guide]:
        """
PURPOSE:
Task guide configured when step mode is active

FRESH_REQUIREMENTS:
- The node config exposes the declared guide target as the task guide when step mode is active.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session guide, providing structured instructional text when step mode is active.

GROUNDING_ARGUMENT:
- Derived by loading the primary target node manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(get_singleton(loop_node_cleaner.CleanedNodes).primary_node), reading and parsing the guide markdown when step mode is active.
"""
        ...

    @property
    @override
    def blame_targets(self) -> Set[agent_file_alias.BoundFile]:
        """
PURPOSE:
Blame targets mapped to owning dependency nodes

FRESH_REQUIREMENTS:
- The node config exposes declared feedback dependencies as blame targets mapped to owning dependency nodes.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides blame targets eligible for defect attribution.

GROUNDING_ARGUMENT:
- Derived by unioning the values of self.blame_targets_by_node.
"""
        ...

    @property
    @override
    def blame_targets_by_node(self) -> Mapping[dag_storage.Node, Set[agent_file_alias.BoundFile]]:
        """
PURPOSE:
Session blame targets mapped by session node

FRESH_REQUIREMENTS:
- The node config exposes blame targets by node mapping each session node to its declared blame targets.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session blame targets mapped by session node.

GROUNDING_ARGUMENT:
- Derived by loading target node manifests via bazel_manifest_loader.BazelManifestLoader.get_manifest for each node in get_singleton(loop_node_cleaner.CleanedNodes).nodes, mapping declared feedback dependencies to BoundFile instances.
"""
        ...

    @property
    @override
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        """
PURPOSE:
Session verification checks derived from manifest verification commands

FRESH_REQUIREMENTS:
- The node config exposes declared verification checks from the manifest verification commands.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session verification checks evaluated during session advancement.

GROUNDING_ARGUMENT:
- Derived by concatenating verification checks from self.verification_checks_by_node across all session nodes.
"""
        ...

    @property
    @override
    def verification_checks_by_node(self) -> Mapping[dag_storage.Node, Sequence[agent_node_config.VerificationCheck]]:
        """
PURPOSE:
Session verification checks mapped by session node

FRESH_REQUIREMENTS:
- The node config exposes verification checks by node mapping each session node to its verification checks.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session verification checks mapped by session node.

GROUNDING_ARGUMENT:
- Derived by loading target node manifests via bazel_manifest_loader.BazelManifestLoader.get_manifest for each node in get_singleton(loop_node_cleaner.CleanedNodes).nodes, constructing CommandVerificationCheck instances from declared verify command strings.
"""
        ...

    @property
    @override
    def src_file_alias_by_node(self) -> Mapping[dag_storage.Node, str]:
        """
PURPOSE:
Source file alias relative path mapped by session node

FRESH_REQUIREMENTS:
- The node config exposes declared src file alias by node mapping each session node to the relative path of its declared source file alias.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the source file alias relative path mapped by session node.

GROUNDING_ARGUMENT:
- Derived by loading target node manifests via bazel_manifest_loader.BazelManifestLoader.get_manifest for each node in get_singleton(loop_node_cleaner.CleanedNodes).nodes and extracting the relative path of its declared src file.
"""
        ...

    @property
    @override
    def verification_success_message(self) -> Optional[str]:
        """
PURPOSE:
Session verification success message resolved from manifest metadata

FRESH_REQUIREMENTS:
- Declared verification success message from the primary target node manifest as the session verification success message.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session verification success message when configured.

GROUNDING_ARGUMENT:
- Derived by loading the primary target node manifest via bazel_manifest_loader.BazelManifestLoader.get_manifest(get_singleton(loop_node_cleaner.CleanedNodes).primary_node), extracting the declared verification_success_message string when present.
"""
        ...

    @property
    @override
    def feedback(self) -> Sequence[str]:
        """
PURPOSE:
Session feedback retrieved from graph storage for session nodes

FRESH_REQUIREMENTS:
- Declared feedback messages retrieved from graph storage for the session nodes as the session feedback.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session feedback, exposing incoming feedback delivered to the node when present.

GROUNDING_ARGUMENT:
- Derived by querying dag_storage.DagStorage for incoming feedback messages across all nodes in get_singleton(loop_node_cleaner.CleanedNodes).nodes.
"""
        ...

@singleton_type('agent_session')
class AliasManager(agent_file_alias.AliasManager):
    """
PURPOSE:
Implements alias manager with relative paths

INHERITANCE:
- tool_provider.ParameterConverter: Implements parameter converter for file alias actual type

GROUNDING_ARGUMENT:
- As an agent_session singleton, AliasManager resolves accessible workspace files for get_singleton(loop_node_cleaner.CleanedNodes).nodes into relative paths and maintains host path mappings.
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
    def convert(self, wire_value: str) -> agent_file_alias.FileAlias:
        """
PURPOSE:
Converts relative paths to matching file aliases

FRESH_REQUIREMENTS:
- The alias manager converts relative paths to matching file aliases, producing unbound files when unmapped.

INHERITED_REQUIREMENTS:
- [AliasManager] Converting a wire type string produces the matching file alias if its relative path is found, and produces an unbound file if the relative path is not found.

GROUNDING_ARGUMENT:
- Receives wire_value string directly as a parameter and looks up the corresponding file alias in session mappings on self, returning an unbound file if not found.
"""
        ...

    @operation
    @override
    def sanitize_text(self, text: str) -> str:
        """
PURPOSE:
Masks occurrences of relative workspace paths and preceding path prefixes with relative paths

FRESH_REQUIREMENTS:
- The alias manager sanitizes output text by masking occurrences of each file's relative workspace path and any preceding path prefix with its relative path, using performant regular expression patterns that disallow directory separators within prefix segments to prevent catastrophic backtracking.

INHERITED_REQUIREMENTS:
- [AliasManager] Sanitizing text masks occurrences of relative workspace paths and preceding path prefixes with the corresponding file alias relative paths.

GROUNDING_ARGUMENT:
- Receives text directly as a parameter and replaces relative workspace paths and preceding path prefixes with corresponding relative paths stored on self.
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
