# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: c0990e9eaec2
# LOW_QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_work."""

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier

PENDING_WORK_FILE: str = ...

@data_type
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
        contract_files: Sequence of companion contract and spec file paths.
    """

    target_file: str
    role_name: str
    dirtiness_reasons: Sequence[str]
    dependency_files: Sequence[str]
    is_ready: bool
    blocked_reasons: Sequence[str] = ()
    contract_files: Sequence[str] = ()


@data_type
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


@singleton_type("agent_session")
class WorkspaceWorkManager(InTier[AgentSessionTier], Protocol):
    """Evaluates dirtiness and task readiness across directory scopes."""

    @operation
    def get_pending_work(self, workspace_dir: str) -> Sequence[str]:
        """Reads target paths from local pending work buffer.

        POSTCONDITIONS:
        - When buffer file is present, MUST return list of pending target paths.
        - When buffer file is missing, MUST return an empty sequence.
        """
        ...

    @operation
    def clear_pending_work(self, workspace_dir: str) -> None:
        """Removes local pending work buffer file if present.

        POSTCONDITIONS:
        - MUST delete .cleanroom_pending_work.json from workspace directory.
        """
        ...

    @operation
    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None:
        """Records pending target paths into local buffer file.

        POSTCONDITIONS:
        - When targets sequence is empty, MUST clear pending work buffer.
        - When targets sequence is non-empty, MUST serialize targets to .cleanroom_pending_work.json.
        """
        ...

    @operation
    def remove_pending_target(self, workspace_dir: str, submitted_target: str) -> None:
        """Removes a submitted target from local pending work buffer.

        POSTCONDITIONS:
        - MUST remove matching target from .cleanroom_pending_work.json.
        """
        ...

    @operation
    def is_pending_target_dirty(
        self,
        target_path: str,
        workspace_dir: str,
        main_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> bool:
        """Checks whether a pending target file is still dirty.

        POSTCONDITIONS:
        - MUST check in-band metadata dirty status across local workspace and main repository.
        - MUST return true if target is missing, marked dirty, or has unacted feedback.
        """
        ...

    @operation
    def compute_role_work_queue(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: str,
    ) -> tuple[Sequence[WorkQueueItem], Sequence[WorkQueueItem]]:
        """Computes ready and blocked dirty units directly from build manifests and metadata.

        POSTCONDITIONS:
        - MUST scan part directories in scope for dirty units.
        - MUST check intra-unit upstream roles, auditor feedback deps, and inter-unit module deps.
        - MUST return tuple of (ready_items, blocked_items) sorted topologically.
        """
        ...

    @operation
    def evaluate_work(
        self,
        dir_scope: str,
        role_name: str,
        workspace_dir: Optional[str] = None,
        force: bool = False,
    ) -> WorkQueueSummary:
        """Evaluates dirty units in scope and returns work queue summary.

        POSTCONDITIONS:
        - When pending dirty work remains and force is false, MUST raise RuntimeError.
        - MUST schedule work for directory scope using dynamic role precedence.
        - MUST partition tasks into ready and blocked items.
        - MUST return WorkQueueSummary detailing ready and blocked items.
        """
        ...

    @operation
    def resolve_contract_files(
        self,
        target_path: str,
        workspace_dir: str,
        role_name: Optional[str] = None,
    ) -> Sequence[str]:
        """Resolves companion specification contracts and interface definitions for target.

        POSTCONDITIONS:
        - MUST discover low-level spec contracts, interface protocols, and definitions for target.
        - MUST return existing readable contract paths relative to workspace root.
        """
        ...
