# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:36Z
# LAST_CHANGED: 2026-10-11T05:42:34Z
# CHANGE: Drop the uncontracted pending work file constant that the grounding specification no longer declares
# CODE_HASH: 9d826860f054
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_work."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence


@dataclass(frozen=True)
class WorkQueueItem:
    """A task item in the work queue.

    Args:
        target_file: Relative path to target file.
        role_name: Target role name.
        dirtiness_reasons: Sequence of reasons why the target is dirty.
        dependency_files: Sequence of dependency file paths.
        is_ready: True if all non-silent dependencies are clean.
        blocked_reasons: Sequence of reasons why the target is blocked.
    """

    target_file: str
    role_name: str
    dirtiness_reasons: Sequence[str]
    dependency_files: Sequence[str]
    is_ready: bool
    blocked_reasons: Sequence[str] = ()
    contract_files: Sequence[str] = ()


@dataclass(frozen=True)
class WorkQueueSummary:
    """Overall summary of work items in a directory scope.

    Args:
        ready_items: Sequence of tasks ready for execution.
        blocked_items: Sequence of tasks blocked on prerequisites.
        is_clean: True if all units in scope evaluate clean.
        remaining_ready_count: Number of unpresented ready tasks beyond current batch.
    """

    ready_items: Sequence[WorkQueueItem]
    blocked_items: Sequence[WorkQueueItem]
    is_clean: bool
    remaining_ready_count: int = 0


class WorkspaceWorkManager(Protocol):
    """Evaluates dirtiness and task readiness across directory scopes."""

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

    def compute_role_work_queue(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: str,
    ) -> tuple[Sequence[WorkQueueItem], Sequence[WorkQueueItem]]: ...

    def evaluate_work(
        self,
        dir_scope: str,
        role_name: str,
        workspace_dir: Optional[str] = None,
        force: bool = False,
        batch_size: Optional[int] = None,
    ) -> WorkQueueSummary: ...

    def resolve_contract_files(
        self,
        target_path: str,
        workspace_dir: str,
        role_name: Optional[str] = None,
    ) -> Sequence[str]: ...
