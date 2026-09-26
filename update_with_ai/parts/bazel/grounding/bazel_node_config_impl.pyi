from typing import Any, List, Mapping, Optional, Sequence, Set, Tuple, Type, Self
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
    """Implements node config from node manifest metadata.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, NodeConfig accesses active target nodes and version from agent_node_config.RoleConfig, caching per node info for active nodes and unloading per node info when nodes leave, and dynamically aggregates session file sets, templates, and guidance configurations.
    """

    @property
    @override
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """Declared direct dependencies and transitive star dependencies.

        REQUIREMENTS:
        - The session read-only files aggregating read-only files across the active nodes, excluding files present in the session read-write files.

        GROUNDING_PROVISIONS:
        - knows("read_only_files", Set[agent_file_alias.ReadOnlyFile]): Exposes session read-only files.

        GROUNDING_ARGUMENT:
        - knows("read_only_files", Self) :- knows("per_node_info_by_node", Self), knows("read_write_files", Self).
        """
        ...

    @property
    @override
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """Declared source files and templates across active nodes.

        REQUIREMENTS:
        - The session read-write files and templates aggregating read-write files and templates across the active nodes, mapping read-write files to initial file content.

        GROUNDING_PROVISIONS:
        - knows("read_write_files", Set[agent_file_alias.ReadWriteFile]): Exposes session read-write files.

        GROUNDING_ARGUMENT:
        - knows("read_write_files", Self) :- knows("per_node_info_by_node", Self).
        """
        ...

    @property
    @override
    def allows_step_mode(self) -> bool:
        """Whether the node allows step mode from target node manifest.

        REQUIREMENTS:
        - Whether the node allows step mode resolved when the session contains exactly one node.

        GROUNDING_PROVISIONS:
        - knows("allows_step_mode", bool): Exposes whether node allows step mode.

        GROUNDING_ARGUMENT:
        - knows("allows_step_mode", Self) :- knows("nodes", agent_node_config.RoleConfig), knows("per_node_info_by_node", Self).
        """
        ...

    @property
    @override
    def is_step_mode(self) -> bool:
        """Whether step mode is active for the session.

        REQUIREMENTS:
        - Whether step mode is active, enabled when the agent config enables step mode, the session contains exactly one node, the target node allows step mode, and session feedback is absent.

        GROUNDING_PROVISIONS:
        - knows("is_step_mode", bool): Exposes whether session step mode is active.

        GROUNDING_ARGUMENT:
        - knows("is_step_mode", Self) :- knows("is_step_mode", agent_config.AgentConfig), knows("nodes", agent_node_config.RoleConfig), knows("allows_step_mode", Self), knows("feedback", Self).
        """
        ...

    @property
    @override
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        """Guide file configured when step mode is active.

        REQUIREMENTS:
        - The session guide file and task guide from the single active node when guide step mode is active.

        GROUNDING_PROVISIONS:
        - knows("guide_file", Optional[agent_file_alias.UnboundFile]): Exposes session guide file.

        GROUNDING_ARGUMENT:
        - knows("guide_file", Self) :- knows("is_step_mode", Self), knows("per_node_info_by_node", Self).
        """
        ...

    @property
    @override
    def templates(self) -> Set[Tuple[agent_file_alias.BoundFile, agent_file_alias.FileContent]]:
        """Startup template mappings for declared source files.

        REQUIREMENTS:
        - The session read-write files and templates aggregating read-write files and templates across the active nodes, mapping read-write files to initial file content.

        GROUNDING_PROVISIONS:
        - knows("templates", Set[Tuple[agent_file_alias.BoundFile, agent_file_alias.FileContent]]): Exposes template mappings.

        GROUNDING_ARGUMENT:
        - knows("templates", Self) :- knows("per_node_info_by_node", Self).
        """
        ...

    @property
    @override
    def template_parameters(self) -> Mapping[str, Any]:
        """Declared template parameters from the manifest.

        REQUIREMENTS:
        - The session template parameters combining template parameters across the active nodes.

        GROUNDING_PROVISIONS:
        - knows("template_parameters", Mapping[str, Any]): Exposes template parameter bindings.

        GROUNDING_ARGUMENT:
        - knows("template_parameters", Self) :- knows("per_node_info_by_node", Self).
        """
        ...

    @property
    @override
    def guide(self) -> Optional[agent_node_config.NodeGuide]:
        """Task guide configured when step mode is active.

        REQUIREMENTS:
        - The session guide file and task guide from the single active node when guide step mode is active.

        GROUNDING_PROVISIONS:
        - knows("guide", Optional[agent_node_config.NodeGuide]): Exposes task guide text.

        GROUNDING_ARGUMENT:
        - knows("guide", Self) :- knows("is_step_mode", Self), knows("per_node_info_by_node", Self).
        """
        ...

    @property
    @override
    def blame_targets_by_node(self) -> Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]]:
        """Session blame targets mapped by session node.

        REQUIREMENTS:
        - The session blame targets by node mapping each active node to its declared blame targets.

        GROUNDING_PROVISIONS:
        - knows("blame_targets_by_node", Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]]): Exposes blame targets by node.

        GROUNDING_ARGUMENT:
        - knows("blame_targets_by_node", Self) :- knows("per_node_info_by_node", Self).
        """
        ...

    @property
    @override
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        """Session verification checks derived from manifest verification commands.

        REQUIREMENTS:
        - The session verification checks aggregating verification checks across the active nodes, and verification checks by node mapping each active node to its verification checks.

        GROUNDING_PROVISIONS:
        - knows("verification_checks", Sequence[agent_node_config.VerificationCheck]): Exposes session verification checks.

        GROUNDING_ARGUMENT:
        - knows("verification_checks", Self) :- knows("per_node_info_by_node", Self).
        """
        ...

    @property
    @override
    def verification_checks_by_node(self) -> Mapping[dag_storage.DagNode, Sequence[agent_node_config.VerificationCheck]]:
        """Session verification checks mapped by session node.

        REQUIREMENTS:
        - The session verification checks aggregating verification checks across the active nodes, and verification checks by node mapping each active node to its verification checks.

        GROUNDING_PROVISIONS:
        - knows("verification_checks_by_node", Mapping[dag_storage.DagNode, Sequence[agent_node_config.VerificationCheck]]): Exposes verification checks by node.

        GROUNDING_ARGUMENT:
        - knows("verification_checks_by_node", Self) :- knows("per_node_info_by_node", Self).
        """
        ...

    @property
    @override
    def src_file_alias_by_node(self) -> Mapping[dag_storage.DagNode, str]:
        """Source file alias relative path mapped by session node.

        REQUIREMENTS:
        - The session src file alias by node mapping each active node to the relative path of its declared source file alias.

        GROUNDING_PROVISIONS:
        - knows("src_file_alias_by_node", Mapping[dag_storage.DagNode, str]): Exposes source file aliases by node.

        GROUNDING_ARGUMENT:
        - knows("src_file_alias_by_node", Self) :- knows("per_node_info_by_node", Self).
        """
        ...

    @property
    @override
    def verification_success_message(self) -> Optional[str]:
        """Session verification success message resolved from manifest metadata.

        REQUIREMENTS:
        - The session verification success message from the active node when the session contains exactly one node.

        GROUNDING_PROVISIONS:
        - knows("verification_success_message", Optional[str]): Exposes verification success message.

        GROUNDING_ARGUMENT:
        - knows("verification_success_message", Self) :- knows("nodes", agent_node_config.RoleConfig), knows("per_node_info_by_node", Self).
        """
        ...

    @property
    @override
    def feedback(self) -> Sequence[str]:
        """Session feedback retrieved from graph storage for session nodes.

        REQUIREMENTS:
        - The session feedback combining feedback messages retrieved from graph storage across the active nodes.

        GROUNDING_PROVISIONS:
        - knows("feedback", Sequence[str]): Exposes combined feedback messages.

        GROUNDING_ARGUMENT:
        - knows("feedback", Self) :- knows("per_node_info_by_node", Self).
        """
        ...

    @property
    @override
    def per_node_info_by_node(self) -> Mapping[dag_storage.DagNode, agent_node_config.PerNodeInfo]:
        """Session per node info mapped by session node.

        REQUIREMENTS:
        - The session per node info by node mapping each active node to its per node info.

        GROUNDING_PROVISIONS:
        - knows("per_node_info_by_node", Mapping[dag_storage.DagNode, agent_node_config.PerNodeInfo]): Exposes per-node info mapping.

        GROUNDING_ARGUMENT:
        - knows("per_node_info_by_node", Self) :- knows("nodes", agent_node_config.RoleConfig), knows("version", agent_node_config.RoleConfig), action("get_manifest", bazel_manifest_loader.BazelManifestLoader).
        """
        ...


@singleton_type('agent_session')
class AliasManager(agent_file_alias.AliasManager):
    """Implements alias manager with relative paths.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, AliasManager resolves accessible workspace files for get_singleton(agent_node_config.RoleConfig).nodes into relative paths and maintains host path mappings, checking the role config version to update file aliases and path masking.
    """

    @property
    @override
    def actual_type(self) -> Type[agent_file_alias.FileAlias]:
        """FileAlias actual type.

        GROUNDING_IMPLEMENTS:
        - knows("actual_type", Type): Constant type descriptor identifying FileAlias.
        """
        ...

    @property
    @override
    def wire_type(self) -> Type[tool_provider.WireString]:
        """String wire type.

        GROUNDING_IMPLEMENTS:
        - knows("wire_type", Type[tool_provider.WireString]): Constant wire type descriptor identifying tool_provider.WireString.
        """
        ...

    @operation
    @override
    def convert(self, wire_value: tool_provider.WireString) -> agent_file_alias.FileAlias:
        """Converts relative paths to matching file aliases.

        REQUIREMENTS:
        - The alias manager converts relative paths to matching file aliases, producing unbound files when unmapped or ambiguous.

        GROUNDING_PROVISIONS:
        - action("convert", agent_file_alias.FileAlias): Converts wire string to file alias.

        GROUNDING_ARGUMENT:
        - action("convert", Self) :- action("resolve_alias", Self), knows("workspace_root", Self).
        """
        ...

    @operation
    @override
    def sanitize_text(self, text: str) -> str:
        """Masks occurrences of relative workspace paths and preceding path prefixes with relative paths.

        REQUIREMENTS:
        - The alias manager sanitizes output text by masking occurrences of each file's relative workspace path and any preceding path prefix with its relative path, using performant regular expression patterns that disallow directory separators within prefix segments to prevent catastrophic backtracking, stripping workspace root path prefixes, and stripping execution root path prefixes.

        GROUNDING_PROVISIONS:
        - action("sanitize_text", str): Sanitizes and masks paths in text.

        GROUNDING_ARGUMENT:
        - action("sanitize_text", Self) :- action("mask_relative_paths", Self), knows("workspace_root", Self).
        """
        ...

    @property
    @override
    def workspace_root(self) -> file_paths.WorkspaceRoot:
        """Workspace root configured on alias manager.

        GROUNDING_PROVISIONS:
        - knows("workspace_root", file_paths.WorkspaceRoot): Exposes configured workspace root.

        GROUNDING_ARGUMENT:
        - knows("workspace_root", Self) :- knows("workspace_root", file_paths.WorkspaceRoot).
        """
        ...
