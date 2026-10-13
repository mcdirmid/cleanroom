# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:36Z
# LAST_CHANGED: 2026-10-11T04:14:50Z
# CHANGE: Contract role metadata descriptor and sibling workspace root discovery
# CODE_HASH: 4fdbb00b5cc5
# SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for workspace_registry_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import cleanroom_files_ext
import file_paths
import workspace_registry


@singleton_type("agent_session")
class WorkspaceRegistry(
    workspace_registry.WorkspaceRegistry,
    InTier[AgentSessionTier],
):
    """Realizes role configuration resolution and persistent workspace registration.

    GROUNDING:
    - Realizes workspace_registry.WorkspaceRegistry by producing
      workspace_registry.RoleDefinition records from parsed role declarations and
      workspace_registry.WorkspaceDescriptor records from persistent registry entries.
    - Implements the search_ancestor_markers, inspect_role_metadata_descriptor,
      match_sibling_workspace_conventions, fallback_to_ambient_working_directory,
      parse_role_definitions, normalize_role_identifier, sanitize_directory_folder_name,
      write_json_registry_atomically, and read_json_registry_descriptors mechanics over
      the cleanroom_files_ext.WORKSPACES_REGISTRY_FILE registry file held beneath the canonical repository
      root.
    - Backs active workspace tracking with an in-memory workspace descriptor collection
      keyed by workspace directory, hydrated through read_json_registry_descriptors and
      replaced through write_json_registry_atomically on every record or unregister.
    - Constructs absolute and relative path representations with
      file_paths.FilePathManager.create_absolute_path,
      file_paths.FilePathManager.create_workspace_path, and
      file_paths.FilePathManager.resolve_path, delegating host filesystem text reads,
      writes, and directory marker checks to the external filesystem_ext mechanics and
      deterministic JSON encoding and decoding to the external json_ext mechanics.
    - Parses role configuration declarations from declarative role files through the
      external cleanroom_files_ext role_manifest_parsing provision.
    """

    @operation
    @override
    def discover_repository_root(
        self, start_dir: Optional[str] = None
    ) -> str:
        """Discovers the canonical repository root by searching ancestor directories.

        POSTCONDITIONS:
        - WHEN discovering repository roots from within an isolated role workspace, MUST inspect role metadata descriptors to resolve the canonical repository root.
        - WHEN discovering repository roots from within an isolated role workspace, MUST match sibling workspace conventions to resolve the canonical repository root.

        GROUNDING:
        - Searches upward from the caller-supplied start_dir, or from the ambient current
          working directory when start_dir is absent, testing each ancestor directory for
          Cleanroom configuration files from cleanroom_files_ext (such as cleanroom_files_ext.CLEANROOM_CONFIG_FILE,
          cleanroom_files_ext.CLEANROOM_ROLES_FILE), pyproject.toml, or git repository markers to distinguish
          a canonical repository from a projected role workspace, and falls back to the
          ambient working directory when the ancestor walk reaches the filesystem root without a marker.
        - Inspects the role metadata descriptors carried by the enclosing isolated role
          workspace, reading the role metadata JSON recorded at cleanroom_files_ext.ROLE_DESCRIPTOR_FILE in the
          role workspace root together with the
          workspace_registry.WorkspaceDescriptor.directory_scope,
          workspace_registry.WorkspaceDescriptor.main_repository_root, and the
          workspace_registry.RoleDefinition role identity and pattern fields role_name,
          role_address, src_pattern, writable_file_patterns, and readonly_file_patterns,
          and resolves the canonical repository root from the recorded main repository
          root.
        - Matches sibling workspace conventions by enumerating the sibling role workspace
          directories beside the enclosing role workspace beneath the role_workspaces
          container directory of the parent projects root, and adopts the main repository
          root that those sibling role workspaces carry in their own role metadata
          descriptors as the canonical repository root.
        - Promotes the discovered directory through
          file_paths.FilePathManager.create_absolute_path and returns the resulting path
          string.
        """
        ...

    @operation
    @override
    def resolve_role_definition(
        self,
        role_name_or_address: str,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> workspace_registry.RoleDefinition:
        """Resolves a role configuration matching declared roles or addressed packages.

        GROUNDING:
        - Normalizes the supplied role name or package-qualified address into a canonical
          role name through normalize_role_identifier before any lookup.
        - Loads the addressed package role declarations when the address is
          package-qualified, discovers and loads the methodology configuration bound to
          the supplied dir_scope or its package hierarchy when the address is unqualified
          and dir_scope is supplied, and otherwise parses declarative role declarations
          from the repository root, evaluating declarations through the
          external cleanroom_files_ext role_manifest_parsing provision.
        - Extracts every declared role attribute from the parsed declaration into a
          workspace_registry.RoleDefinition record, deriving the configured guide path,
          source pattern, file patterns, dependency sequences, and audit tag.
        - Raises KeyError when the normalized role name is undeclared, and raises
          ValueError when a declaration redundantly lists feedback or star role
          dependencies in role_deps, lists a dependency as both role_deps and
          silent_role_deps, or declares an auditor role in role_deps, star_role_deps, or
          feedback_role_deps.
        """
        ...

    @operation
    @override
    def list_roles(
        self,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Sequence[workspace_registry.RoleDefinition]:
        """Loads and resolves all role definitions declared in the repository.

        GROUNDING:
        - Enumerates every role configuration declaration from the repository build files
          or from the methodology configuration bound to the supplied dir_scope and its
          package hierarchy, normalizing each declared role identifier through
          normalize_role_identifier.
        - Constructs a workspace_registry.RoleDefinition for every parsed declaration and
          applies the same redundant dependency, conflicting silent dependency, and
          auditor dependency rejection as resolve_role_definition.
        """
        ...

    @operation
    @override
    def compute_workspace_dir(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> str:
        """Computes sanitized path for a role workspace working tree.

        GROUNDING:
        - Returns the supplied custom_dest unchanged when provided.
        - Otherwise sanitizes the role name and dir_scope through
          sanitize_directory_folder_name, replacing directory separator characters with
          underscores to compose a single workspace folder name, builds that folder name
          as a file_paths.WorkspacePath through
          file_paths.FilePathManager.create_workspace_path, and combines it beneath the
          role_workspaces container directory in the parent projects root that contains
          the canonical repository root through file_paths.FilePathManager.resolve_path
          over a file_paths.AbsolutePath parent root.
        """
        ...

    @operation
    @override
    def record_workspace(
        self,
        descriptor: workspace_registry.WorkspaceDescriptor,
        repo_root: Optional[str] = None,
    ) -> None:
        """Records an active workspace descriptor into the persistent registry file.

        GROUNDING:
        - Reads the existing descriptor array from cleanroom_files_ext.WORKSPACES_REGISTRY_FILE through
          read_json_registry_descriptors, upserts the supplied
          workspace_registry.WorkspaceDescriptor in the in-memory descriptor collection
          keyed by workspace directory, and commits the collection through
          write_json_registry_atomically by encoding deterministic JSON via the external
          json_ext mechanics into a temporary sibling file and atomically replacing the
          registry file.
        """
        ...

    @operation
    @override
    def unregister_workspace(
        self, workspace_dir: str, repo_root: Optional[str] = None
    ) -> bool:
        """Removes a workspace descriptor from the persistent registry file.

        GROUNDING:
        - Reads the existing descriptor array from cleanroom_files_ext.WORKSPACES_REGISTRY_FILE through
          read_json_registry_descriptors, removes the collection entry whose workspace
          directory matches the supplied workspace_dir, commits the remaining collection
          through write_json_registry_atomically, and reports whether a matching entry was
          removed.
        """
        ...

    @operation
    @override
    def load_active_workspaces(
        self, repo_root: Optional[str] = None
    ) -> Sequence[workspace_registry.WorkspaceDescriptor]:
        """Loads active workspace descriptors from the persistent registry file.

        GROUNDING:
        - Reads cleanroom_files_ext.WORKSPACES_REGISTRY_FILE from the canonical repository root through
          read_json_registry_descriptors, decoding host text through the external
          filesystem_ext mechanics and JSON payloads through the external json_ext
          mechanics, and constructs a workspace_registry.WorkspaceDescriptor for each
          entry, treating an absent registry file as an empty descriptor collection.
        """
        ...
