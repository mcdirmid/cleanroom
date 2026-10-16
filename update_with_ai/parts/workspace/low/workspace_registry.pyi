# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:45:00Z
# CHANGE: Delegate role configuration resolution to workspace_roles
# CODE_HASH: 5f184681fbaf
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_registry."""

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import workspace_roles

RoleDefinition = workspace_roles.RoleDefinition


@data_type
@dataclass(frozen=True)
class WorkspaceDescriptor:
    """Descriptor identifying an active role workspace.

    Args:
        workspace_dir: Absolute path to the role workspace directory.
        main_repository_root: Absolute path to canonical repository root.
        directory_scope: Package or directory scope for the role workspace.
        role_definition: Associated role definition configuration.
        last_sync_timestamp: Optional UTC ISO 8601 timestamp of last sync.
    """

    workspace_dir: str
    main_repository_root: str
    directory_scope: str
    role_definition: workspace_roles.RoleDefinition
    last_sync_timestamp: Optional[str] = None


@singleton_type("agent_session")
class WorkspaceRegistry(InTier[AgentSessionTier], Protocol):
    """Registry resolving role specifications and tracking commissioned workspaces."""

    @operation
    def discover_repository_root(
        self, start_dir: Optional[str] = None
    ) -> str:
        """Discovers the canonical repository root from the filesystem environment or the current working directory.

        POSTCONDITIONS:
        - MUST resolve the canonical repository root from the filesystem environment.
        - WHEN no repository root is discoverable in the filesystem environment, MUST resolve the canonical repository root from the current working directory.
        - MUST return an absolute path to the canonical repository root.
        """
        ...

    @operation
    def resolve_role_definition(
        self,
        role_name_or_address: str,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> workspace_roles.RoleDefinition:
        """Resolves a role definition through role resolution services.

        POSTCONDITIONS:
        - MUST delegate role definition resolution to workspace_roles.RoleResolver.resolve_role_definition.
        """
        ...

    @operation
    def list_roles(
        self,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Sequence[workspace_roles.RoleDefinition]:
        """Loads and resolves all role definitions declared in the repository through role resolution services.

        POSTCONDITIONS:
        - MUST delegate role listing to workspace_roles.RoleResolver.list_roles.
        """
        ...

    @operation
    def compute_workspace_dir(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> str:
        """Computes a sanitized role workspace directory path from a role name and directory scope.

        POSTCONDITIONS:
        - WHEN custom_dest is provided, MUST return the supplied destination directory.
        - MUST sanitize directory delimiter characters into underscores within the workspace folder name.
        - MUST return an absolute path to the role workspace directory.
        """
        ...

    @operation
    def record_workspace(
        self, descriptor: WorkspaceDescriptor, repo_root: Optional[str] = None
    ) -> None:
        """Records an active workspace descriptor into active session memory.

        POSTCONDITIONS:
        - MUST record or update the workspace descriptor in active session memory.
        """
        ...

    @operation
    def unregister_workspace(
        self, workspace_dir: str, repo_root: Optional[str] = None
    ) -> bool:
        """Removes a workspace descriptor from active session memory.

        POSTCONDITIONS:
        - MUST remove the matching workspace directory entry from active session memory.
        - WHEN a matching workspace directory entry is removed, MUST return true.
        """
        ...

    @operation
    def load_active_workspaces(
        self, repo_root: Optional[str] = None
    ) -> Sequence[WorkspaceDescriptor]:
        """Loads all active workspace descriptors from active session memory and provisioned role workspaces.

        POSTCONDITIONS:
        - MUST return active workspace descriptors tracked in memory or discovered by inspecting provisioned role workspace directories carrying role metadata descriptors.
        - WHEN no workspaces have been recorded or provisioned, MUST return an empty sequence.
        """
        ...
