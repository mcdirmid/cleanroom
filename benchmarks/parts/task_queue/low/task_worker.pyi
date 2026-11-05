"""Low-level interface specification for task worker."""

from __future__ import annotations

from typing import Protocol
from pretense import PretenseSpecificationError, test_only
from support.lib.framework import data_type, operation, poly_type


@data_type
class WorkerError(PretenseSpecificationError):
    """Base exception for all task worker operations."""


@data_type
class WorkerExecutionException(Exception):
    """Raised when an operational execution failure occurs in the worker."""


@poly_type
class TaskWorker(Protocol):
    """Autonomous task execution worker protocol."""

    @operation
    def execute(self, task_id: str, payload: str) -> str:
        """Executes a workload payload and reports completion to the task queue.

        Args:
            task_id: Unique task identifier.
            payload: Workload payload string.

        Returns:
            Computed execution outcome string.

        Raises:
            WorkerExecutionException: If the task queue is unavailable or task fails.

        POSTCONDITIONS:
        - WHEN execution fails or task queue is unavailable, MUST raise WorkerExecutionException.
        - WHEN execution succeeds, MUST notify task queue of completion and return outcome string.
        """
        ...

    @operation
    def fetch_and_execute(self) -> str:
        """Fetches the next pending task from the collaborator queue and executes it.

        Returns:
            Dispatched task identifier.

        Raises:
            WorkerError: If the collaborator task queue contains zero pending tasks.
            WorkerExecutionException: If the collaborator task queue is unavailable.

        PRECONDITIONS:
        - WHEN collaborator task queue has zero pending tasks, MUST raise WorkerError.

        POSTCONDITIONS:
        - WHEN collaborator task queue is unavailable, MUST raise WorkerExecutionException.
        - WHEN collaborator dispatch succeeds, MUST execute dispatched task and return task identifier.
        """
        ...

    @operation
    @test_only
    def set_failing_task(self, task_id: str, failing: bool = True) -> None:
        """Test-only hook to configure designated tasks to fail on execution.

        Args:
            task_id: Task identifier.
            failing: Whether the task should fail.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-11-03T23:10:00Z
# LAST_CHANGED: 2026-11-03T23:10:00Z
# CHANGE: Streamline worker interface contracts by moving telemetry and busy state to implementation
# SPEC_QA_AUDIT: 2026-11-03T23:10:00Z
# --- END CLEANROOM METADATA ---
