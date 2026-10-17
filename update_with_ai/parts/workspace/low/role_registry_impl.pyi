# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:45:00Z
# CHANGE: Delegate role configuration resolution to roles
# CODE_HASH: 47b98b0105c9
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for role_registry_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from session import AgentSessionTier
import cleanroom_files_ext
import file_paths
import role_registry
import roles


@singleton_type("agent_session")
class WorkspaceRegistry(
    role_registry.WorkspaceRegistry,
    InTier[AgentSessionTier],
):
    """Realizes role configuration resolution and active workspace tracking.

    GROUNDING:
    - Realizes role_registry.WorkspaceRegistry by delegating role definition resolution
      to roles.RoleResolver and producing role_registry.WorkspaceDescriptor
      records from active session memory or provisioned role workspaces.
    - Implements the search_ancestor_markers, inspect_role_metadata_descriptor,
      match_sibling_workspace_conventions, fallback_to_ambient_working_directory,
      sanitize_directory_folder_name, record_in_memory_descriptor, and discover_active_workspace_descriptors mechanics.
    - Backs active workspace tracking with an in-memory workspace descriptor collection
      keyed by workspace directory, hydrated through in-memory registration and provisioned
      role workspace discovery.
    - Constructs absolute and relative path representations with
      file_paths.FilePathManager.create_absolute_path,
      file_paths.FilePathManager.create_workspace_path, and
      file_paths.FilePathManager.resolve_path, delegating host filesystem text reads,
      writes, and directory marker checks to the external filesystem_ext mechanics and
      deterministic JSON encoding and decoding to the external json_ext mechanics.
    """

    @operation
    @override
    def discover_repository_root(
        self, start_dir: Optional[str] = None
    ) -> str:
        """Discovers the canonical repository root by searching ancestor directories.

        POSTCONDITIONS:
        - WHEN discovering repository roots from within an isolated role workspace, MUST match sibling workspace conventions to resolve the canonical repository root without reading host paths from role descriptors.

        GROUNDING:
        - Searches upward from the caller-supplied start_dir, or from the ambient current
          working directory when start_dir is absent, testing each ancestor directory for
          Cleanroom configuration files from cleanroom_files_ext (such as cleanroom_files_ext.CLEANROOM_CONFIG_FILE,
          cleanroom_files_ext.CLEANROOM_ROLES_FILE), pyproject.toml, or git repository markers to distinguish
          a canonical repository from a projected role workspace, and falls back to the
          ambient working directory when the ancestor walk reaches the filesystem root without a marker.
        - Matches sibling workspace conventions by resolving the parent projects root from
          the enclosing role workspace directory beneath the role_workspaces container,
          identifying the sibling project root matching the workspace prefix conventions,
          and returns the resulting path string without reading host paths from the role descriptor.
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
    ) -> roles.RoleDefinition:
        """Resolves a role configuration matching declared roles or addressed packages.

        GROUNDING:
        - Delegates resolution to roles.RoleResolver.resolve_role_definition.
        """
        ...

    @operation
    @override
    def list_roles(
        self,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Sequence[roles.RoleDefinition]:
        """Loads and resolves all role definitions declared in the repository.

        GROUNDING:
        - Delegates role listing to roles.RoleResolver.list_roles.
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
        descriptor: role_registry.WorkspaceDescriptor,
        repo_root: Optional[str] = None,
    ) -> None:
        """Records an active workspace descriptor into active session memory.

        GROUNDING:
        - Stores or updates the supplied role_registry.WorkspaceDescriptor in the
          in-memory descriptor collection keyed by workspace directory.
        """
        ...

    @operation
    @override
    def unregister_workspace(
        self, workspace_dir: str, repo_root: Optional[str] = None
    ) -> bool:
        """Removes a workspace descriptor from active session memory.

        GROUNDING:
        - Removes the collection entry whose workspace directory matches the supplied
          workspace_dir from the in-memory descriptor collection, and reports whether
          a matching entry was removed.
        """
        ...

    @operation
    @override
    def load_active_workspaces(
        self, repo_root: Optional[str] = None
    ) -> Sequence[role_registry.WorkspaceDescriptor]:
        """Loads active workspace descriptors from active session memory and provisioned role workspaces.

        GROUNDING:
        - Combines in-memory workspace descriptors with descriptors discovered by scanning
          the role_workspaces directory for provisioned role workspace directories carrying
          role metadata descriptors, decoding host text through the external filesystem_ext
          mechanics and JSON payloads through the external json_ext mechanics, constructing
          a role_registry.WorkspaceDescriptor for each discovered workspace matching
          the canonical repository root.
        """
        ...
