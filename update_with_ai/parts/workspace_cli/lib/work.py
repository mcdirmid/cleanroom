"""Low-level interface specification for work."""

from __future__ import annotations
from update_with_ai.parts.agent.lib.session import AgentSessionTier
from support.lib.lifecycle import Singleton

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence


# Contract: WorkQueueItem represents a unit task in the work queue.
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


# Contract: WorkQueueSummary provides summary of ready and blocked work items in a directory scope.
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


# Contract: WorkspaceWorkManager protocol evaluates dirtiness and task readiness across directory scopes.
class WorkspaceWorkManager(Singleton[AgentSessionTier], Protocol):
    """Evaluates dirtiness and task readiness across directory scopes."""

    # Contract: Reads target paths from local pending work buffer.
    def get_pending_work(self, workspace_dir: str) -> Sequence[str]: ...

    # Contract: Removes local pending work buffer file if present.
    def clear_pending_work(self, workspace_dir: str) -> None: ...

    # Contract: Records pending target paths into local buffer file.
    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None: ...

    # Contract: Removes a submitted target from local pending work buffer.
    def remove_pending_target(self, workspace_dir: str, submitted_target: str) -> None: ...

    # Contract: Checks whether a pending target file is still dirty across local and main workspaces.
    def is_pending_target_dirty(
        self,
        target_path: str,
        workspace_dir: str,
        main_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> bool: ...

    # Contract: Computes ready and blocked dirty units directly from build manifests and metadata.
    def compute_role_work_queue(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: str,
        target_unit: Optional[str] = None,
    ) -> tuple[Sequence[WorkQueueItem], Sequence[WorkQueueItem]]: ...

    # Contract: Evaluates dirty units in scope and returns work queue summary, scheduling via dynamic role precedence.
    def evaluate_work(
        self,
        dir_scope: str,
        role_name: str,
        workspace_dir: Optional[str] = None,
        force: bool = False,
        batch_size: Optional[int] = None,
    ) -> WorkQueueSummary: ...

    # Contract: Resolves companion specification contracts and interface definitions for target.
    def resolve_contract_files(
        self,
        target_path: str,
        workspace_dir: str,
        role_name: Optional[str] = None,
    ) -> Sequence[str]: ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:42:34Z
# CHANGE: Drop the uncontracted pending work file constant that the grounding specification no longer declares
# --- END CLEANROOM METADATA ---
