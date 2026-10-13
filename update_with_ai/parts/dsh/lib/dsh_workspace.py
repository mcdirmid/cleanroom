# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T20:00:00Z
# CHANGE: author dsh_workspace interface library
# CODE_HASH: 849255e9caca
# --- END CLEANROOM METADATA ---

"""Interface specification for dsh_workspace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence


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


class DshWorkspaceConfigurer(Protocol):
    """Establishes DeepSeek Harness boundary hints and Cordis overlay patches in role workspaces."""

    def configure_role_workspace(
        self,
        workspace_dir: str,
        role_name: str,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> DshWorkspaceConfinementReport:
        """Configures role agent documentation and Cordis overlay patch for DeepSeek Harness."""
        ...
