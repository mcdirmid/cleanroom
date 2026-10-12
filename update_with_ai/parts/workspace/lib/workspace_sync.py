# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:04Z
# LAST_CHANGED: 2026-10-11T05:04:11Z
# CHANGE: Prune the surplus public copy helper from the interface so it holds only the sync result and synchronizer protocol
# CODE_HASH: 62c1357b69e0
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_sync."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence


@dataclass(frozen=True)
class SyncResult:
    """Outcome of a synchronization operation.

    Args:
        pulled_files: Number of files pulled from main to workspace.
        harvested_files: Number of files harvested from workspace to main.
        stamped_audits: Sequence of target paths with attested audits.
        flushed_blames: Sequence of culprit paths receiving blame feedback.
    """

    pulled_files: int
    harvested_files: int
    stamped_audits: Sequence[str]
    flushed_blames: Sequence[str]


class WorkspaceSynchronizer(Protocol):
    """Coordinates bi-directional synchronization and blame flushing."""

    def pull(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
        silent: bool = False,
    ) -> int: ...

    def refresh_system_files(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
        silent: bool = False,
    ) -> int: ...

    def harvest(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
    ) -> SyncResult: ...

    def flush_blame_buffer(
        self, workspace_dir: str, main_root: str
    ) -> Sequence[str]: ...
