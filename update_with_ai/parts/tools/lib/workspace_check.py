# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:25:00Z
# CHANGE: Define workspace_check interface
# CODE_HASH: 35bc5adcad63
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional, Protocol


class WorkspaceChecker(Protocol):
    """Executes work discovery and file verification for role workspaces."""

    def run_get_work(
        self,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        force: bool = False,
        batch_size: Optional[int] = None,
    ) -> int: ...

    def run_check_files(
        self,
        target: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int: ...
