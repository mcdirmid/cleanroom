from __future__ import annotations
from update_with_ai.parts.agent.lib.session import AgentSessionTier
from support.lib.lifecycle import Singleton
from typing import Optional, Protocol, Sequence


# Contract: WorkspacePendingManager protocol tracks active pending tasks and buffer persistence within role workspaces.
class WorkspacePendingManager(Singleton[AgentSessionTier], Protocol):
    """Tracks active pending tasks and buffer persistence within role workspaces."""

    # Contract: Reads target paths from local pending work buffer.
    def get_pending_work(self, workspace_dir: str) -> Sequence[str]: ...

    # Contract: Removes local pending work buffer file if present.
    def clear_pending_work(self, workspace_dir: str) -> None: ...

    # Contract: Records pending target paths into local buffer file.
    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None: ...

    # Contract: Removes a submitted target from local pending work buffer.
    def remove_pending_target(self, workspace_dir: str, submitted_target: str) -> None: ...

    # Contract: Checks whether a pending target file is still dirty across local workspace and main repository.
    def is_pending_target_dirty(
        self,
        target_path: str,
        workspace_dir: str,
        main_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> bool: ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:40:00Z
# CHANGE: Define pending interface
# --- END CLEANROOM METADATA ---
