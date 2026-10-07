# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 3eb0f82da16f
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_registry."""

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier


@data_type
@dataclass(frozen=True)
class RoleDefinition:
    """Configuration definition for an autonomous development role.

    Args:
        role_name: Canonical role name.
        guide_path: Path to companion role guide.
        writable_file_patterns: Sequence of glob patterns for writable targets.
        readonly_file_patterns: Sequence of glob patterns for immutable contracts.
        feedback_role_deps: Sequence of role names receiving feedback.
        role_address: Optional full role target address.
        audit_tag: Optional metadata audit tag.
        task_prompt: Optional prompt template string.
    """

    role_name: str
    guide_path: str
    writable_file_patterns: Sequence[str]
    readonly_file_patterns: Sequence[str]
    feedback_role_deps: Sequence[str]
    role_address: Optional[str] = None
    audit_tag: Optional[str] = None
    task_prompt: Optional[str] = None


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
    role_definition: RoleDefinition
    last_sync_timestamp: Optional[str] = None


@singleton_type("agent_session")
class WorkspaceRegistry(InTier[AgentSessionTier], Protocol):
    """Registry resolving role definitions and tracking active workspaces."""

    @operation
    def discover_repository_root(
        self, start_dir: Optional[str] = None
    ) -> str:
        """Discovers the canonical repository root by ascending directory trees.

        POSTCONDITIONS:
        - MUST locate ancestor containing MODULE.bazel or .git marker.
        - MUST return absolute path to canonical repository root.
        """
        ...

    @operation
    def resolve_role_definition(
        self, role_name_or_address: str, repo_root: Optional[str] = None
    ) -> RoleDefinition:
        """Resolves role definition from role name or target address.

        POSTCONDITIONS:
        - MUST match standard Cleanroom roles or parse rule definition.
        - MUST return RoleDefinition with configured file patterns and guide.
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
        """Computes deterministic sanitized path for a role workspace directory.

        POSTCONDITIONS:
        - When custom_dest is provided, MUST return custom_dest directly.
        - MUST sanitize directory delimiters to underscores in workspace folder name.
        - MUST return absolute path to role workspace directory.
        """
        ...

    @operation
    def record_workspace(
        self, descriptor: WorkspaceDescriptor, repo_root: Optional[str] = None
    ) -> None:
        """Records active workspace descriptor into persistent registry file.

        POSTCONDITIONS:
        - MUST append or update workspace descriptor in .cleanroom_workspaces.json.
        """
        ...

    @operation
    def unregister_workspace(
        self, workspace_dir: str, repo_root: Optional[str] = None
    ) -> bool:
        """Removes workspace descriptor from persistent registry file.

        POSTCONDITIONS:
        - MUST remove matching workspace directory from .cleanroom_workspaces.json.
        - MUST return true when an existing workspace was removed.
        """
        ...

    @operation
    def load_active_workspaces(
        self, repo_root: Optional[str] = None
    ) -> Sequence[WorkspaceDescriptor]:
        """Loads all active workspace descriptors from persistent registry file.

        POSTCONDITIONS:
        - MUST deserialize descriptors from .cleanroom_workspaces.json.
        - When registry file is missing, MUST return an empty sequence.
        """
        ...
