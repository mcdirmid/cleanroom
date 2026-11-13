# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_203549_deepseek-flash_task_queue_pretense
# Timestamp: 2026-11-13T20:35:49.092080+00:00
# Benchmark Task: task_queue
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 4
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 290,002
#   Cached Inbound Tokens:   23,055,360
#   Outbound Tokens:         230,257
#   Total Tokens:            23,575,619
#   Financial Cost ($USD):   $0.2508
#   Wall Clock Duration:     1332.93s
#   Step Latencies (s):      [202.2, 543.5, 41.6, 162.2, 124.7, 20.5, 114.4, 152.1, 22.7, 51.8, 85.1, 20.6, 76.9, 10.1, 74.8, 30.9, 74.5, 10.1, 24.7, 10.2, 61.9, 30.8, 20.4, 20.4]
#   Role Execution Rounds:   lib: 1, pretense: 8, pretense_coverage: 7, pretense_qa: 8 (Total: 24)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       2
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: task_queue.py ===
"""Interface protocol and error hierarchy for first-in first-out task queues."""

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
        """
        ...

    @operation
    def get_outcome(self, task_id: str) -> Optional[str]:
        """Retrieves the recorded outcome for a task.

        Args:
            task_id: Task identifier.

        Returns:
            Recorded outcome string if completed, else None.
        """
        ...

    @operation
    def clear(self) -> None:
        """Purges all pending tasks and recorded outcomes from the queue."""
        ...

    @operation
    @test_only
    def set_available(self, available: bool) -> None:
        """Test-only hook to toggle task queue availability for operational simulation.

        Args:
            available: Availability flag to set.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T20:38:49Z
# LAST_CHANGED: 2026-11-13T20:38:49Z
# CHANGE: Define TaskQueue protocol with pending_count property and submit/dispatch/complete/get_outcome/clear/set_available stubs, plus QueueError/QueueEmptyError/QueueUnavailableException data types matching the low-level interface spec.
# --- END AUTOFAB METADATA ---


# === File: task_queue_impl.py ===
"""Concrete bounded first-in first-out task queue implementation."""

from __future__ import annotations

from collections import deque
from typing import Optional

from pretense import test_only

from support.lib.framework import data_type, operation, override
from support.lib.lifecycle import get_singleton, singleton

from . import task_queue, task_worker


@data_type
class QueueFullError(task_queue.QueueError):
    """Raised when attempting to submit to a task queue that has reached capacity."""


@singleton
class TaskQueue(task_queue.TaskQueue):
    """Bounded task queue storing payloads and outcomes, delegating execution to the worker."""

    tier: str = "system"

    def __init__(self) -> None:
        self._capacity: int = 10
        self._queue: deque[tuple[str, str]] = deque()
        self._outcomes: dict[str, str] = {}
        self._is_available: bool = True

    @property
    def capacity(self) -> int:
        """Maximum number of pending tasks permitted in the queue."""
        return self._capacity

    @property
    def is_empty(self) -> bool:
        """Indicates whether the task queue contains zero pending tasks."""
        return len(self._queue) == 0

    @property
    def is_full(self) -> bool:
        """Indicates whether the task queue has reached its capacity limit."""
        return len(self._queue) >= self._capacity

    @property
    def is_available(self) -> bool:
        """Indicates whether the task queue is available for operations."""
        return self._is_available

    @property
    @override
    def pending_count(self) -> int:
        """Current number of pending tasks stored in the queue."""
        return len(self._queue)

    @operation
    @override
    def submit(self, task_id: str, payload: str) -> None:
        """Appends a new task to the queue awaiting execution."""
        # Reject submissions while the queue is unavailable.
        if not self.is_available:
            raise task_queue.QueueUnavailableException("Task queue is unavailable")
        # Reject submissions once the bounded capacity has been reached.
        if self.is_full:
            raise QueueFullError(f"Task queue is full at capacity {self._capacity}")
        self._queue.append((task_id, payload))

    @operation
    @override
    def dispatch(self) -> str:
        """Dispatches the oldest pending task and returns its identifier."""
        # Refuse to dispatch while the queue is unavailable.
        if not self.is_available:
            raise task_queue.QueueUnavailableException("Task queue is unavailable")
        # Refuse to dispatch when no pending tasks remain.
        if self.is_empty:
            raise task_queue.QueueEmptyError("Task queue is empty")
        task_id, payload = self._queue.popleft()
        # Hand the dispatched payload to the collaborating worker for execution.
        worker = get_singleton(task_worker.TaskWorker)
        worker.execute(task_id, payload)
        return task_id

    @operation
    @override
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome string for a task."""
        # Refuse to record outcomes while the queue is unavailable.
        if not self.is_available:
            raise task_queue.QueueUnavailableException("Task queue is unavailable")
        self._outcomes[task_id] = outcome

    @operation
    @override
    def get_outcome(self, task_id: str) -> Optional[str]:
        """Retrieves the recorded outcome for a task."""
        return self._outcomes.get(task_id)

    @operation
    @override
    def clear(self) -> None:
        """Purges all pending tasks and recorded outcomes from the queue."""
        self._queue.clear()
        self._outcomes.clear()

    @operation
    @test_only
    @override
    def set_available(self, available: bool) -> None:
        """Test-only hook to toggle task queue availability for operational simulation."""
        self._is_available = available

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T20:57:48Z
# LAST_CHANGED: 2026-11-13T20:39:04Z
# CHANGE: Implement singleton TaskQueue with bounded deque capacity 10, outcome mapping, availability guards, QueueFullError on overflow, and dispatch delegating payload execution to the TaskWorker collaborator.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T20:57:48Z
# PRETENSE_QA_AUDIT: 2026-11-13T20:57:26Z
# --- END AUTOFAB METADATA ---


# === File: task_worker.py ===
"""Interface protocol and error hierarchy for autonomous task execution workers."""

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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T20:38:55Z
# LAST_CHANGED: 2026-11-13T20:38:55Z
# CHANGE: Define TaskWorker protocol with execute/fetch_and_execute/set_failing_task stubs and WorkerError/WorkerExecutionException data types matching the low-level interface spec.
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl.py ===
"""Concrete task worker implementation with payload transformation and execution telemetry."""

from __future__ import annotations

from typing import Optional

from pretense import test_only

from support.lib.framework import operation, override
from support.lib.lifecycle import get_singleton, singleton

from . import task_queue, task_worker


@singleton
class TaskWorker(task_worker.TaskWorker):
    """Executes task payloads, records completion outcomes, and tracks execution telemetry."""

    tier: str = "system"

    def __init__(self) -> None:
        self._processed_count: int = 0
        self._last_task_id: Optional[str] = None
        self._is_busy: bool = False
        self._failing_tasks: set[str] = set()

    @property
    def processed_count(self) -> int:
        """Current number of tasks successfully processed by the worker."""
        return self._processed_count

    @property
    def last_task_id(self) -> Optional[str]:
        """Identifier of the most recently executed task, or None if no tasks processed."""
        return self._last_task_id

    @property
    def is_busy(self) -> bool:
        """Indicates whether the worker is currently executing a task."""
        return self._is_busy

    @operation
    def reset(self) -> None:
        """Resets telemetry counters, clearing last task identifier and busy state."""
        self._processed_count = 0
        self._last_task_id = None
        self._is_busy = False

    @operation
    @override
    def execute(self, task_id: str, payload: str) -> str:
        """Executes a workload payload, reports completion to task queue, and updates telemetry."""
        self._is_busy = True
        # Designated failing tasks abort immediately without recording an outcome.
        if task_id in self._failing_tasks:
            self._is_busy = False
            raise task_worker.WorkerExecutionException(f"Task {task_id} failed during execution")
        outcome = f"PROCESSED:{payload.upper()}"
        queue = get_singleton(task_queue.TaskQueue)
        try:
            queue.complete(task_id, outcome)
        except task_queue.QueueUnavailableException as exc:
            # Surface collaborator unavailability as an execution failure.
            self._is_busy = False
            raise task_worker.WorkerExecutionException("Task queue is unavailable") from exc
        self._last_task_id = task_id
        self._processed_count += 1
        self._is_busy = False
        return outcome

    @operation
    @override
    def fetch_and_execute(self) -> str:
        """Fetches the next pending task from the task queue singleton and executes it."""
        queue = get_singleton(task_queue.TaskQueue)
        try:
            task_id = queue.dispatch()
        except task_queue.QueueEmptyError as exc:
            # An empty collaborator queue is a worker-level failure.
            raise task_worker.WorkerError("Task queue is empty") from exc
        except task_queue.QueueUnavailableException as exc:
            # An unavailable collaborator queue is an execution failure.
            raise task_worker.WorkerExecutionException("Task queue is unavailable") from exc
        # Dispatch normally delegates execution back to this worker; when a collaborating
        # queue only pops the oldest task, execute it here to honor the execution contract.
        if self._last_task_id != task_id:
            self.execute(task_id, "")
        return task_id

    @operation
    @test_only
    @override
    def set_failing_task(self, task_id: str, failing: bool = True) -> None:
        """Test-only hook to configure designated tasks to fail on execution."""
        if failing:
            self._failing_tasks.add(task_id)
        else:
            self._failing_tasks.discard(task_id)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T20:55:35Z
# LAST_CHANGED: 2026-11-13T20:39:10Z
# CHANGE: Implement singleton TaskWorker with PROCESSED: outcome transformation, completion notification via TaskQueue, telemetry counters, failing-task hook, and fetch_and_execute mapping empty/unavailable queue errors to WorkerError/WorkerExecutionException.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T20:55:35Z
# PRETENSE_QA_AUDIT: 2026-11-13T20:55:23Z
# --- END AUTOFAB METADATA ---
