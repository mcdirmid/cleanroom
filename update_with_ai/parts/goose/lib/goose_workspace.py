# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T09:50:00Z
# CHANGE: author goose_workspace interface library
# CODE_HASH: 87332f991098
# --- END CLEANROOM METADATA ---

"""Interface specification for goose_workspace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class GooseWorkspaceConfinementReport:
    """Confinement report for a configured Goose role workspace.

    Args:
        workspace_dir: Absolute path to the role workspace directory.
        role_name: Assigned Cleanroom role identifier.
        configured_files: Sequence of created boundary and recipe file paths.
        status: Confinement status indicator string.
    """

    workspace_dir: str
    role_name: str
    configured_files: Sequence[str] = ()
    status: str = "configured"


class GooseWorkspaceConfigurer(Protocol):
    """Establishes Goose boundary hints and role recipe files in role workspaces."""

    def configure_role_workspace(
        self,
        workspace_dir: str,
        role_name: str,
    ) -> GooseWorkspaceConfinementReport:
        """Configures boundary hints and materializes recipes in a role workspace."""
        ...
