"""Interface specification for dsh_workspace."""

from __future__ import annotations
from update_with_ai.parts.agent.lib.session import AgentSessionTier
from support.lib.lifecycle import Singleton

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence


# Contract: DshWorkspaceConfinementReport data type holding workspace path, role name, configured file paths, and status.
@dataclass(frozen=True)
class DshWorkspaceConfinementReport:
    """Confinement report for a configured DeepSeek Harness role workspace.

    Args:
        workspace_dir: Absolute path to the role workspace directory.
        role_name: Assigned Cleanroom role identifier.
        configured_files: Sequence of created boundary and patch file paths.
        status: Confinement status indicator string.
    """

    workspace_dir: str
    role_name: str
    configured_files: Sequence[str] = ()
    status: str = "configured"


# Contract: DshWorkspaceConfigurer protocol defining configure_role_workspace.
class DshWorkspaceConfigurer(Singleton[AgentSessionTier], Protocol):
    """Establishes DeepSeek Harness boundary hints and Cordis overlay patches in role workspaces."""

    # Contract: MUST configure role agent documentation and Cordis overlay patch, and return report.
    def configure_role_workspace(
        self,
        workspace_dir: str,
        role_name: str,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> DshWorkspaceConfinementReport:
        """Configures role agent documentation and Cordis overlay patch for DeepSeek Harness."""
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-13T20:00:00Z
# CHANGE: author dsh_workspace interface library
# --- END CLEANROOM METADATA ---
