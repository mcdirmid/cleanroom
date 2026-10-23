"""Low-level interface specification for role_registry."""

from __future__ import annotations
from update_with_ai.parts.agent.lib.session import AgentSessionTier
from support.lib.lifecycle import Singleton

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from . import roles

RoleDefinition = roles.RoleDefinition


# Contract: WorkspaceDescriptor data structure identifies an active role workspace and its metadata.
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
    role_definition: roles.RoleDefinition
    last_sync_timestamp: Optional[str] = None


# Contract: WorkspaceRegistry protocol resolves role specifications and tracks commissioned workspaces.
class WorkspaceRegistry(Singleton[AgentSessionTier], Protocol):
    """Registry resolving role specifications and tracking commissioned workspaces."""

    # Contract: Discovers canonical repository root from filesystem environment or current working directory.
    def discover_repository_root(self, start_dir: Optional[str] = None) -> str:
        """Discovers the canonical repository root from the filesystem environment or the current working directory."""
        ...

    # Contract: Resolves role definition through roles.RoleResolver.
    def resolve_role_definition(
        self,
        role_name_or_address: str,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> roles.RoleDefinition:
        """Resolves a role definition from a role name or qualified role address."""
        ...

    # Contract: Loads and resolves all role definitions declared in the repository through RoleResolver.
    def list_roles(
        self,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Sequence[roles.RoleDefinition]:
        """Loads and resolves all role definitions declared in the repository or bound methodology configuration."""
        ...

    # Contract: Computes sanitized role workspace directory path from role name and directory scope.
    def compute_workspace_dir(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> str:
        """Computes a sanitized role workspace directory path from a role name and directory scope."""
        ...

    # Contract: Records active workspace descriptor into active session memory.
    def record_workspace(
        self, descriptor: WorkspaceDescriptor, repo_root: Optional[str] = None
    ) -> None:
        """Records an active workspace descriptor into active session memory."""
        ...

    # Contract: Removes workspace descriptor from active session memory and reports removal status.
    def unregister_workspace(
        self, workspace_dir: str, repo_root: Optional[str] = None
    ) -> bool:
        """Removes a workspace descriptor from active session memory."""
        ...

    # Contract: Loads active workspace descriptors from active session memory and provisioned role workspaces.
    def load_active_workspaces(
        self, repo_root: Optional[str] = None
    ) -> Sequence[WorkspaceDescriptor]:
        """Loads all active workspace descriptors from active session memory and provisioned role workspaces."""
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:45:00Z
# CHANGE: Delegate role configuration to roles
# --- END CLEANROOM METADATA ---
