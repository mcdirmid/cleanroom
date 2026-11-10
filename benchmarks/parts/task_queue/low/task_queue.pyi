"""Low-level interface specification for task queue."""

from __future__ import annotations

from typing import Optional, Protocol
from pretense import PretenseSpecificationError, test_only
from support.lib.framework import data_type, operation, poly_type


@data_type
class QueueError(PretenseSpecificationError):
    """Base exception for all task queue operations."""


@data_type
class QueueEmptyError(QueueError):
    """Raised when attempting to dispatch from an empty task queue."""


@data_type
class QueueUnavailableException(Exception):
    """Raised when attempting an operation on an unavailable task queue."""


@poly_type
class TaskQueue(Protocol):
    """First-in first-out task queue protocol."""

    @property
    def pending_count(self) -> int:
        """Current number of pending tasks stored in the queue."""
        ...

    @operation
    def submit(self, task_id: str, payload: str) -> None:
        """Appends a new task to the queue awaiting execution.

        Args:
            task_id: Unique task identifier.
            payload: Workload payload string.

        Raises:
            QueueUnavailableException: If the task queue is unavailable.

        POSTCONDITIONS:
        - [slug:task_queue.submit.unavailable_queue]: WHEN queue is unavailable, MUST raise QueueUnavailableException.
        - [slug:task_queue.submit.append_task]: WHEN queue is available, MUST append task to queue tail and increment pending_count by 1.
        """
        ...

    @operation
    def dispatch(self) -> str:
        """Dispatches the oldest pending task and returns its identifier.

        Returns:
            Dispatched task identifier.

        Raises:
            QueueEmptyError: If the task queue contains zero pending tasks.
            QueueUnavailableException: If the task queue is unavailable.

        PRECONDITIONS:
        - [slug:task_queue.dispatch.empty_queue]: WHEN pending_count equals 0, MUST raise QueueEmptyError.

        POSTCONDITIONS:
        - [slug:task_queue.dispatch.unavailable_queue]: WHEN queue is unavailable, MUST raise QueueUnavailableException.
        - [slug:task_queue.dispatch.pop_task]: WHEN pending_count is greater than 0, MUST pop oldest task, decrement pending_count by 1, and return task_id.
        """
        ...

    @operation
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome string for a task.

        Args:
            task_id: Task identifier.
            outcome: Execution result outcome string.

        Raises:
            QueueUnavailableException: If the task queue is unavailable.

        POSTCONDITIONS:
        - [slug:task_queue.complete.unavailable_queue]: WHEN queue is unavailable, MUST raise QueueUnavailableException.
        - [slug:task_queue.complete.record_outcome]: WHEN queue is available, MUST record outcome for task_id.
        """
        ...

    @operation
    def get_outcome(self, task_id: str) -> Optional[str]:
        """Retrieves the recorded outcome for a task.

        Args:
            task_id: Task identifier.

        Returns:
            Recorded outcome string if completed, else None.

        POSTCONDITIONS:
        - [slug:task_queue.get_outcome.completed_task]: WHEN task_id has recorded outcome, MUST return recorded outcome string.
        - [slug:task_queue.get_outcome.uncompleted_task]: WHEN task_id has no recorded outcome, MUST return None.
        """
        ...

    @operation
    def clear(self) -> None:
        """Purges all pending tasks and recorded outcomes from the queue.

        POSTCONDITIONS:
        - [slug:task_queue.clear.purge_tasks]: MUST purge all pending tasks and reset pending_count to 0.
        - [slug:task_queue.clear.purge_outcomes]: MUST purge all recorded task outcomes.
        """
        ...

    @operation
    @test_only
    def set_available(self, available: bool) -> None:
        """Test-only hook to toggle task queue availability for operational simulation.

        Args:
            available: Availability flag to set.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-11-03T23:10:00Z
# LAST_CHANGED: 2026-11-03T23:10:00Z
# CHANGE: Streamline interface contracts by moving capacity limits and derived emptiness/fullness checks to implementation
# SPEC_QA_AUDIT: 2026-11-03T23:10:00Z
# --- END CLEANROOM METADATA ---
