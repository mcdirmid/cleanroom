# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:36Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_workspace_impl implementation low-level specification
# CODE_HASH: d5df385ee3ca
# SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for antigravity_workspace_impl."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
import agent_session
import antigravity_ext
import antigravity_workspace
import workspace_registry


@singleton_type("agent_session")
class AntigravityWorkspaceConfigurer(
    antigravity_workspace.AntigravityWorkspaceConfigurer,
    InTier[agent_session.AgentSessionTier],
):
    """Realizes Antigravity-specific isolation rules and workspace confinement.

    GROUNDING:
    - Realizes workspace boundary configuration by querying role definitions through
      workspace_registry.WorkspaceRegistry.resolve_role_definition, generating
      workspace-local isolation rules conforming to antigravity_ext rule specifications,
      writing role guidance documentation, and synthesizing
      antigravity_workspace.WorkspaceConfinementReport records.
    """

    @operation
    @override
    def configure_workspace(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
    ) -> antigravity_workspace.WorkspaceConfinementReport:
        """Establishes Antigravity isolation rules and returns a confinement report.

        GROUNDING:
        - Resolves role definitions via workspace_registry.WorkspaceRegistry.resolve_role_definition,
          writes boundary isolation rules into .agents/rules/isolation.md adhering to
          antigravity_ext, writes role guidance documents into the workspace, and returns
          antigravity_workspace.WorkspaceConfinementReport with the list of created file paths.
        """
        ...
