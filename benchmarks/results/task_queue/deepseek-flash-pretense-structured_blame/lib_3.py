# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_001807_deepseek-flash_task_queue_pretense
# Timestamp: 2026-11-13T00:18:07.836000+00:00
# Benchmark Task: task_queue
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 164,554
#   Cached Inbound Tokens:   10,824,064
#   Outbound Tokens:         121,914
#   Total Tokens:            11,110,532
#   Financial Cost ($USD):   $0.1303
#   Wall Clock Duration:     826.20s
#   Step Latencies (s):      [191.5, 564.2, 20.5, 64.4, 117.0, 75.1, 20.5, 54.1, 10.1, 10.0]
#   Role Execution Rounds:   lib: 1, pretense: 3, pretense_coverage: 3, pretense_qa: 3 (Total: 10)
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
"""Interface specification for the task queue component."""

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
# LAST_CLEANED: 2026-11-13T00:20:54Z
# LAST_CHANGED: 2026-11-13T00:20:54Z
# CHANGE: Implement task queue interface: QueueError/QueueEmptyError/QueueUnavailableException data types and TaskQueue Protocol with pending_count, submit, dispatch, complete, get_outcome, clear, and test-only set_available stubs matching low/task_queue.pyi
# --- END AUTOFAB METADATA ---


# === File: task_queue_impl.py ===
"""Concrete bounded task queue implementation."""

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
    """Concrete bounded first-in first-out task queue."""

    tier = "system"

    def __init__(self) -> None:
        # Bounded FIFO storage holding pending task identifiers and payloads.
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
        # Unavailable queues reject every submission before capacity is considered.
        if not self._is_available:
            raise task_queue.QueueUnavailableException()
        # A queue that already holds its maximum number of tasks rejects new work.
        if self.is_full:
            raise QueueFullError()
        self._queue.append((task_id, payload))

    @operation
    @override
    def dispatch(self) -> str:
        """Dispatches the oldest pending task to the collaborator worker for execution."""
        # Unavailable queues cannot dispatch pending work.
        if not self._is_available:
            raise task_queue.QueueUnavailableException()
        # Dispatching requires at least one pending task.
        if not self._queue:
            raise task_queue.QueueEmptyError()
        # The oldest pending task leaves the queue before it is handed to the worker.
        task_id, payload = self._queue.popleft()
        worker = get_singleton(task_worker.TaskWorker)
        worker.execute(task_id, payload)
        return task_id

    @operation
    @override
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome string for a task."""
        if not self._is_available:
            raise task_queue.QueueUnavailableException()
        # Store the reported outcome so it can be retrieved later.
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
# LAST_CLEANED: 2026-11-13T00:31:50Z
# LAST_CHANGED: 2026-11-13T00:21:06Z
# CHANGE: Implement concrete bounded task queue singleton: deque-backed FIFO with capacity 10, availability guards, QueueFullError on overflow, dispatch-to-worker handoff, outcome recording, clear, and telemetry properties matching low/task_queue_impl.pyi
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:31:50Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:31:38Z
# --- END AUTOFAB METADATA ---


# === File: task_worker.py ===
"""Interface specification for the task worker component."""

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
# LAST_CLEANED: 2026-11-13T00:21:00Z
# LAST_CHANGED: 2026-11-13T00:21:00Z
# CHANGE: Implement task worker interface: WorkerError/WorkerExecutionException data types and TaskWorker Protocol with execute, fetch_and_execute, and test-only set_failing_task stubs matching low/task_worker.pyi
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl.py ===
"""Concrete task execution worker implementation."""

from __future__ import annotations

from typing import Optional

from pretense import test_only
from support.lib.framework import operation, override
from support.lib.lifecycle import get_singleton, singleton

from . import task_queue, task_worker


@singleton
class TaskWorker(task_worker.TaskWorker):
    """Concrete task worker with payload transformation and execution telemetry."""

    tier = "system"

    def __init__(self) -> None:
        # Execution telemetry along with the set of tasks marked as failing.
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
        """Executes a workload payload, reports completion to the task queue, and updates telemetry."""
        self._is_busy = True
        # Tasks configured as failing abort execution without reporting completion.
        if task_id in self._failing_tasks:
            self._is_busy = False
            raise task_worker.WorkerExecutionException()
        # Normalize the payload into the reported outcome form.
        outcome = f"PROCESSED:{payload.upper()}"
        queue = get_singleton(task_queue.TaskQueue)
        try:
            queue.complete(task_id, outcome)
        except task_queue.QueueUnavailableException:
            # An unavailable queue turns successful execution into a reported failure.
            self._is_busy = False
            raise task_worker.WorkerExecutionException()
        self._last_task_id = task_id
        self._processed_count += 1
        self._is_busy = False
        return outcome

    @operation
    @override
    def fetch_and_execute(self) -> str:
        """Fetches the next pending task from the task queue and executes it."""
        queue = get_singleton(task_queue.TaskQueue)
        try:
            # Dispatch pops the oldest task and hands it to this worker for execution.
            task_id = queue.dispatch()
        except task_queue.QueueEmptyError:
            raise task_worker.WorkerError()
        except task_queue.QueueUnavailableException:
            raise task_worker.WorkerExecutionException()
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
# LAST_CLEANED: 2026-11-13T00:30:54Z
# LAST_CHANGED: 2026-11-13T00:21:12Z
# CHANGE: Implement concrete task worker singleton: payload uppercasing with PROCESSED prefix, failing-task hooks, completion notification with unavailable-queue conversion, dispatch-driven fetch_and_execute, telemetry properties and reset matching low/task_worker_impl.pyi
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:30:54Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:30:37Z
# --- END AUTOFAB METADATA ---
