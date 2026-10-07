# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: af3eb6d4918a
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_provision."""

from typing import Optional, Protocol
from framework import operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import workspace_registry


@singleton_type("agent_session")
class WorkspaceProvisioner(InTier[AgentSessionTier], Protocol):
    """Service commissioning and decommissioning isolated role workspaces."""

    @operation
    def commission(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> workspace_registry.WorkspaceDescriptor:
        """Commissions an isolated role workspace with permission boundaries.

        POSTCONDITIONS:
        - MUST create workspace directory tree with bin directory.
        - MUST copy writable targets with 0o644 permissions.
        - MUST copy upstream contract dependencies with 0o444 permissions.
        - MUST package runner zipapps in bin/ with 0o755 permissions.
        - MUST write .cleanroom_role.json configuration and AGENTS.md instructions.
        - MUST record workspace descriptor in the workspace registry.
        - MUST return the created WorkspaceDescriptor.
        """
        ...

    @operation
    def decommission(
        self,
        role_name_or_dir: str,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        force: bool = False,
    ) -> bool:
        """Decommissions and safely removes an active role workspace.

        POSTCONDITIONS:
        - When force is false and unharvested modifications exist, MUST raise RuntimeError.
        - MUST unregister workspace from the workspace registry.
        - MUST recursively delete the workspace directory tree.
        - MUST return true upon successful decommissioning.
        """
        ...
