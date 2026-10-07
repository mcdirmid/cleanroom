# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T22:55:00Z
# CHANGE: new file
# CODE_HASH: 8d4c8fff50e5
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


@dataclass(frozen=True)
class WorkQueueSummary:
    """Overall summary of work items in a directory scope.

    Args:
        ready_items: Sequence of tasks ready for execution.
        blocked_items: Sequence of tasks blocked on prerequisites.
        is_clean: True if all units in scope evaluate clean.
    """

    ready_items: Sequence[WorkQueueItem]
    blocked_items: Sequence[WorkQueueItem]
    is_clean: bool


class WorkspaceWorkManager(Protocol):
    """Evaluates dirtiness and task readiness across directory scopes."""

    def get_pending_work(self, workspace_dir: str) -> Sequence[str]: ...

    def clear_pending_work(self, workspace_dir: str) -> None: ...

    def evaluate_work(
        self,
        dir_scope: str,
        role_name: str,
        workspace_dir: Optional[str] = None,
        force: bool = False,
    ) -> WorkQueueSummary: ...
