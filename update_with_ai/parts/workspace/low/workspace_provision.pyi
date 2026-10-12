# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:03Z
# LAST_CHANGED: 2026-10-11T03:37:01Z
# CHANGE: Align role workspace commissioning, permissions, and runner deployment contracts
# CODE_HASH: 5dd2a7538fb6
# SPEC_QA_AUDIT: 2026-10-12T18:21:03Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_provision."""

from typing import Optional, Protocol
from framework import operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import cleanroom_files_ext
import workspace_registry


@singleton_type("agent_session")
class WorkspaceProvisioner(InTier[AgentSessionTier], Protocol):
    """Service creating and configuring isolated, directory-scoped role workspaces."""

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
        - MUST resolve the role definition for the requested role and directory scope.
        - MUST create the workspace directory tree including a bin directory.
        - MUST copy writable target files with 0o644 permissions.
        - MUST copy upstream contract dependencies with 0o444 permissions.
        - WHEN the role definition declares stub role dependencies, MUST synthesize read-only test stubs raising NotImplementedError from companion specifications without copying real implementation files.
        - MUST package executable runner tools into the bin directory with 0o755 permissions.
        - MUST write cleanroom_files_ext.ROLE_DESCRIPTOR_FILE role configuration in the workspace root.
        - MUST synthesize role-tailored AGENTS.md instructions in the workspace root.
        - MUST record the created workspace descriptor in the persistent registry.
        - MUST return a workspace descriptor for the newly created workspace directory.
        """
        ...
