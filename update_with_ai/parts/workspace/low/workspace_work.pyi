# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 40b8b6ec0ae5
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_work."""

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier


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
    """

    target_file: str
    role_name: str
    dirtiness_reasons: Sequence[str]
    dependency_files: Sequence[str]
    is_ready: bool
    blocked_reasons: Sequence[str] = ()


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
