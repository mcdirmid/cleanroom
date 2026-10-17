# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:04:11Z
# CHANGE: Prune the surplus public copy helper from the interface so it holds only the sync result and synchronizer protocol
# CODE_HASH: 62c1357b69e0
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_sync."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence


# Contract: SyncResult data type represents the outcome of a synchronization operation.
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


# Contract: WorkspaceSynchronizer coordinates bi-directional synchronization and blame flushing.
class WorkspaceSynchronizer(Protocol):
    """Coordinates bi-directional synchronization and blame flushing."""

    # Contract: Pulls updated upstream contracts and source files into role workspace.
    def pull(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
        silent: bool = False,
    ) -> int: ...

    # Contract: Refreshes non-parts system files into role workspace.
    def refresh_system_files(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
        silent: bool = False,
    ) -> int: ...

    # Contract: Harvests modified targets, stamps audits, and flushes blame back to main.
    def harvest(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
    ) -> SyncResult: ...

    # Contract: Flushes buffered blame feedback entries from workspace into main.
    def flush_blame_buffer(
        self, workspace_dir: str, main_root: str
    ) -> Sequence[str]: ...
