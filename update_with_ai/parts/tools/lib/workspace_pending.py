# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:40:00Z
# CHANGE: Define workspace_pending interface
# CODE_HASH: 0ac03f0d71d0
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional, Protocol, Sequence


class WorkspacePendingManager(Protocol):
    """Tracks active pending tasks and buffer persistence within role workspaces."""

    def get_pending_work(self, workspace_dir: str) -> Sequence[str]: ...
    def clear_pending_work(self, workspace_dir: str) -> None: ...
    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None: ...
    def remove_pending_target(self, workspace_dir: str, submitted_target: str) -> None: ...
    def is_pending_target_dirty(
        self,
        target_path: str,
        workspace_dir: str,
        main_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> bool: ...
