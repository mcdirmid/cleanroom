# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 8944f51dbfbc
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
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
        - For roles with stub_role_deps, MUST synthesize read-only test stubs with NotImplementedError from companion specifications without copying real implementation files.
        - MUST package runner zipapps in bin/ with 0o755 permissions.
        - MUST write .cleanroom_role.json configuration and AGENTS.md instructions.
        - MUST record workspace descriptor in the workspace registry.
        - MUST return the created WorkspaceDescriptor.
        """
        ...
