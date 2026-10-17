# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_workspace interface library
# CODE_HASH: 4ba0c0a644a7
# --- END CLEANROOM METADATA ---

"""Interface specification for antigravity_workspace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from support.lib.lifecycle import InTier
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier


# Contract: WorkspaceConfinementReport captures the configured isolation state of a role workspace.
@dataclass(frozen=True)
class WorkspaceConfinementReport:
    """Captures the configured isolation state of a role workspace.

    Args:
        workspace_dir: Absolute path to the role workspace directory.
        rule_paths: Sequence of relative paths to created isolation rules.
        role_name: Name of the assigned role.
        is_confined: Confinement configuration status.
    """

    workspace_dir: str
    rule_paths: Sequence[str]
    role_name: str
    is_confined: bool


# Contract: AntigravityWorkspaceConfigurer configures Antigravity-specific isolation rules and workspace confinement.
class AntigravityWorkspaceConfigurer(InTier[AgentSessionTier], Protocol):
    """Configures Antigravity-specific isolation rules and workspace confinement."""

    # Contract: AntigravityWorkspaceConfigurer.configure_workspace - writes workspace-local isolation rules and returns a confinement report.
    def configure_workspace(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
    ) -> WorkspaceConfinementReport:
        """Establishes Antigravity isolation rules and returns a confinement report."""
        ...

