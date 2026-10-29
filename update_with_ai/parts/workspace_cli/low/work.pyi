"""Low-level interface specification for work."""

from dataclasses import dataclass
from typing import Mapping, Optional, Protocol, Sequence
from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import cleanroom_files_ext

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
        remaining_ready_count: Number of unpresented ready tasks beyond current batch.
    """

    ready_items: Sequence[WorkQueueItem]
    blocked_items: Sequence[WorkQueueItem]
    is_clean: bool
    remaining_ready_count: int = 0


@singleton_type("agent_session")
class WorkspaceWorkManager(Singleton[AgentSessionTier], Protocol):
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
        - MUST delete pending work file designated by cleanroom_files_ext from workspace directory.
        """
        ...

    @operation
    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None:
        """Records pending target paths into local buffer file.

        POSTCONDITIONS:
        - When targets sequence is empty, MUST clear pending work buffer.
        - When targets sequence is non-empty, MUST serialize targets to pending work file designated by cleanroom_files_ext.
        """
        ...

    @operation
    def remove_pending_target(self, workspace_dir: str, submitted_target: str) -> None:
        """Removes a submitted target from local pending work buffer.

        POSTCONDITIONS:
        - MUST remove matching target from pending work file designated by cleanroom_files_ext.
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
        - MUST evaluate feedback role dependencies and star role dependencies as implicit role dependencies.
        - WHEN any star role dependency is modified, MUST return true.
        - MUST return true if target is missing, marked dirty, or has unacted feedback.
        """
        ...

    @operation
    def compute_role_work_queue(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: str,
        target_unit: Optional[str] = None,
    ) -> tuple[Sequence[WorkQueueItem], Sequence[WorkQueueItem]]:
        """Computes ready and blocked dirty units directly from build manifests and metadata.

        POSTCONDITIONS:
        - MUST scan part directories in scope for dirty units.
        - MUST evaluate intra-unit upstream contract dependencies for producer roles from declared role dependencies and cross-unit dependencies from declared star role dependencies.
        - WHEN target_unit is specified, MUST restrict discovered dirty items to the target unit and its transitive dependencies.
        - WHEN any star role dependency is modified, MUST mark target dirty.
        - MUST check intra-unit upstream roles, auditor feedback deps, and inter-unit module deps.
        - WHEN role declares fused_roles, MUST relax upstream dependencies internal to the fused role cluster, evaluating units as ready when their prerequisites outside the fused role cluster are clean.
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
        batch_size: Optional[int] = None,
    ) -> WorkQueueSummary:
        """Evaluates dirty units in scope and returns work queue summary.

        POSTCONDITIONS:
        - When pending dirty work remains and force is false, MUST raise RuntimeError.
        - MUST schedule work for directory scope using dynamic role precedence.
        - MUST partition tasks into ready and blocked items.
        - WHEN batch_size is provided and positive, MUST bound ready_items to at most batch_size and record remaining unpresented count.
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
        - MUST resolve the target role from the supplied role name or the target path.
        - WHEN the target role is undeclared, MUST raise KeyError without substituting a fallback role.
        - WHEN the target path matches no configured file pattern of the target role, MUST raise ValueError.
        - MUST discover low-level spec contracts, interface protocols, and definitions for target unit.
        - FOR any unit ending in _impl, MUST automatically include companion interface contracts without the _impl suffix.
        - MUST filter cross-unit dependencies of the target against configured star role dependencies and silent cross-role dependencies.
        - WHEN a cross-unit dependency is declared as a star role dependency, MUST expand that dependency's specification contracts into the resolved contract files.
        - WHEN a cross-unit dependency is declared as a silent cross-role dependency, MUST suppress the peer implementation files matching that dependency from the resolved contract files.
        - MUST return existing readable contract paths relative to workspace root.
        """
        ...

    @operation
    def get_part_units(
        self,
        repo_root: str,
        part_dir: str,
    ) -> Mapping[str, Sequence[str]]:
        """Discovers package unit names and dependencies from specifications or filesystem stems.

        POSTCONDITIONS:
        - MUST discover unit names and dependencies from high-level specifications or filesystem stems in a part directory.
        """
        ...


def __orphan__() -> None:
    """Orphan contracts for package unit discovery routines.

    POSTCONDITIONS:
    - MUST discover unit names and dependencies from high-level specifications or filesystem stems in a part directory.
    """
    ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-26T20:38:00Z
# LAST_CHANGED: 2026-10-26T20:38:00Z
# CHANGE: Add intra-fuse dependency relaxation postcondition to compute_role_work_queue
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
