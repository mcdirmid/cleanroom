from typing import Any, List, Mapping, Optional, Sequence, Set, Tuple, Type
from framework import operation, override, singleton_type
import bazel_manifest_loader
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
- As an agent_session singleton, NodeConfig accesses active target nodes and version from agent_node_config.RoleConfig, caching per node info for active nodes and unloading per node info when nodes leave, and dynamically aggregates session file sets, templates, and guidance configurations.
"""

    @property
    @override
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """
PURPOSE:
Declared direct dependencies and transitive star dependencies

FRESH_REQUIREMENTS:
- The session read-only files aggregating read-only files across the active nodes, excluding files present in the session read-write files.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session read-only files restricted to inspection.

GROUNDING_ARGUMENT:
- Derived dynamically by aggregating read-only files across active nodes' cached PerNodeInfo from self.per_node_info_by_node, excluding files present in self.read_write_files.
"""
        ...

    @property
    @override
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """
PURPOSE:
Declared source files and templates across active nodes

FRESH_REQUIREMENTS:
- The session read-write files and templates aggregating read-write files and templates across the active nodes, mapping read-write files to initial file content.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session read-write files permitted for inspection and modification.

GROUNDING_ARGUMENT:
- Derived dynamically by aggregating read-write files across active nodes' cached PerNodeInfo from self.per_node_info_by_node.
"""
        ...

    @property
    @override
    def allows_step_mode(self) -> bool:
        """
PURPOSE:
Whether the node allows step mode from target node manifest

FRESH_REQUIREMENTS:
- Whether the node allows step mode resolved when the session contains exactly one node.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config indicates whether the node allows step mode.

GROUNDING_ARGUMENT:
- Derived dynamically from the single active node's cached PerNodeInfo in self.per_node_info_by_node when get_singleton(agent_node_config.RoleConfig).nodes contains exactly one node.
"""
        ...

    @property
    @override
    def is_step_mode(self) -> bool:
        """
PURPOSE:
Whether step mode is active for the session

FRESH_REQUIREMENTS:
- Whether step mode is active, enabled when the agent config enables step mode, the session contains exactly one node, the target node allows step mode, and session feedback is absent.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config indicates whether session step mode is active.

GROUNDING_ARGUMENT:
- Derived dynamically by querying agent_config.AgentConfig.is_step_mode in the system lifecycle tier, verifying that get_singleton(agent_node_config.RoleConfig).nodes contains exactly one node, checking self.allows_step_mode, and verifying that self.feedback is empty.
"""
        ...

    @property
    @override
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        """
PURPOSE:
Guide file configured when step mode is active

FRESH_REQUIREMENTS:
- The session guide file and task guide from the single active node when guide step mode is active.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session guide file when step mode is active.

GROUNDING_ARGUMENT:
- Derived dynamically from the single active node's cached PerNodeInfo in self.per_node_info_by_node when self.is_step_mode is true.
"""
        ...

    @property
    @override
    def templates(self) -> Set[Tuple[agent_file_alias.BoundFile, agent_file_alias.FileContent]]:
        """
PURPOSE:
Startup template mappings for declared source files

FRESH_REQUIREMENTS:
- The session read-write files and templates aggregating read-write files and templates across the active nodes, mapping read-write files to initial file content.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides templates mapping read-write files to initial file content.

GROUNDING_ARGUMENT:
- Derived dynamically by aggregating templates across active nodes' cached PerNodeInfo from self.per_node_info_by_node.
"""
        ...

    @property
    @override
    def template_parameters(self) -> Mapping[str, Any]:
        """
PURPOSE:
Declared template parameters from the manifest

FRESH_REQUIREMENTS:
- The session template parameters combining template parameters across the active nodes.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session template parameters, providing parameter bindings for template evaluation.

GROUNDING_ARGUMENT:
- Derived dynamically by combining template parameters across active nodes' cached PerNodeInfo from self.per_node_info_by_node.
"""
        ...

    @property
    @override
    def guide(self) -> Optional[agent_node_config.Guide]:
        """
PURPOSE:
Task guide configured when step mode is active

FRESH_REQUIREMENTS:
- The session guide file and task guide from the single active node when guide step mode is active.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session guide, providing structured instructional text when step mode is active.

GROUNDING_ARGUMENT:
- Derived dynamically from the single active node's cached PerNodeInfo in self.per_node_info_by_node when self.is_step_mode is true.
"""
        ...

    @property
    @override
    def blame_targets(self) -> Set[agent_file_alias.BoundFile]:
        """
PURPOSE:
Blame targets mapped to owning dependency nodes

FRESH_REQUIREMENTS:
- The session blame targets aggregating blame targets across the active nodes, and blame targets by node mapping each active node to its declared blame targets.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides blame targets eligible for defect attribution.

GROUNDING_ARGUMENT:
- Derived dynamically by unioning blame targets across active nodes' cached PerNodeInfo from self.per_node_info_by_node.
"""
        ...

    @property
    @override
    def blame_targets_by_node(self) -> Mapping[dag_storage.Node, Set[agent_file_alias.BoundFile]]:
        """
PURPOSE:
Session blame targets mapped by session node

FRESH_REQUIREMENTS:
- The session blame targets aggregating blame targets across the active nodes, and blame targets by node mapping each active node to its declared blame targets.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session blame targets mapped by session node.

GROUNDING_ARGUMENT:
- Derived dynamically by mapping each active node to its blame targets from self.per_node_info_by_node.
"""
        ...

    @property
    @override
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        """
PURPOSE:
Session verification checks derived from manifest verification commands

FRESH_REQUIREMENTS:
- The session verification checks aggregating verification checks across the active nodes, and verification checks by node mapping each active node to its verification checks.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session verification checks evaluated during session advancement.

GROUNDING_ARGUMENT:
- Derived dynamically by concatenating verification checks across active nodes' cached PerNodeInfo from self.per_node_info_by_node.
"""
        ...

    @property
    @override
    def verification_checks_by_node(self) -> Mapping[dag_storage.Node, Sequence[agent_node_config.VerificationCheck]]:
        """
PURPOSE:
Session verification checks mapped by session node

FRESH_REQUIREMENTS:
- The session verification checks aggregating verification checks across the active nodes, and verification checks by node mapping each active node to its verification checks.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session verification checks mapped by session node.

GROUNDING_ARGUMENT:
- Derived dynamically by mapping each active node to its verification checks from self.per_node_info_by_node.
"""
        ...

    @property
    @override
    def src_file_alias_by_node(self) -> Mapping[dag_storage.Node, str]:
        """
PURPOSE:
Source file alias relative path mapped by session node

FRESH_REQUIREMENTS:
- The session src file alias by node mapping each active node to the relative path of its declared source file alias.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the source file alias relative path mapped by session node.

GROUNDING_ARGUMENT:
- Derived dynamically by mapping each active node to its declared src_file_alias from self.per_node_info_by_node.
"""
        ...

    @property
    @override
    def verification_success_message(self) -> Optional[str]:
        """
PURPOSE:
Session verification success message resolved from manifest metadata

FRESH_REQUIREMENTS:
- The session verification success message from the active node when the session contains exactly one node.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session verification success message when configured.

GROUNDING_ARGUMENT:
- Derived dynamically from the single active node's cached PerNodeInfo in self.per_node_info_by_node when get_singleton(agent_node_config.RoleConfig).nodes contains exactly one node.
"""
        ...

    @property
    @override
    def feedback(self) -> Sequence[str]:
        """
PURPOSE:
Session feedback retrieved from graph storage for session nodes

FRESH_REQUIREMENTS:
- The session feedback combining feedback messages retrieved from graph storage across the active nodes.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session feedback, exposing incoming feedback delivered to the node when present.

GROUNDING_ARGUMENT:
- Derived dynamically by combining feedback messages across active nodes' cached PerNodeInfo from self.per_node_info_by_node.
"""
        ...

    @property
    @override
    def per_node_info_by_node(self) -> Mapping[dag_storage.Node, agent_node_config.PerNodeInfo]:
        """
PURPOSE:
Session per node info mapped by session node

FRESH_REQUIREMENTS:
- The session per node info by node mapping each active node to its per node info.

INHERITED_REQUIREMENTS:
- [NodeConfig] The node config provides the session per node info by node, mapping each active node to its per node info.

GROUNDING_ARGUMENT:
- Maintains cached PerNodeInfo entries loaded via bazel_manifest_loader.BazelManifestLoader.get_manifest for each active node from get_singleton(agent_node_config.RoleConfig), checking version to unload cached entries when nodes are no longer being cleaned.
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
- As an agent_session singleton, AliasManager resolves accessible workspace files for get_singleton(agent_node_config.RoleConfig).nodes into relative paths and maintains host path mappings.
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
- The alias manager sanitizes output text by masking occurrences of each file's relative workspace path and any preceding path prefix with its relative path, using performant regular expression patterns that disallow directory separators within prefix segments to prevent catastrophic backtracking, stripping workspace root path prefixes, and stripping execution root path prefixes.

INHERITED_REQUIREMENTS:
- [AliasManager] Sanitizing text masks occurrences of relative workspace paths and preceding path prefixes with the corresponding file alias relative paths.

GROUNDING_ARGUMENT:
- Receives text directly as a parameter and replaces relative workspace paths and preceding path prefixes with corresponding relative paths stored on self, stripping workspace root and execution root path prefixes.
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
