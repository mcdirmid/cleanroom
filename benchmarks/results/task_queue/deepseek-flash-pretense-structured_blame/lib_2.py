# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261112_205956_deepseek-flash_task_queue_pretense
# Timestamp: 2026-11-12T20:59:56.688188+00:00
# Benchmark Task: task_queue
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 172,005
#   Cached Inbound Tokens:   12,183,936
#   Outbound Tokens:         193,884
#   Total Tokens:            12,549,825
#   Financial Cost ($USD):   $0.1787
#   Wall Clock Duration:     1076.74s
#   Step Latencies (s):      [222.8, 502.0, 175.9, 10.1, 369.3, 22.8, 20.4]
#   Role Execution Rounds:   lib: 1, pretense: 2, pretense_coverage: 2, pretense_qa: 2 (Total: 7)
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
"""Library interface for the first-in first-out task queue."""

from __future__ import annotations

from typing import Optional, Protocol

from pretense.parts.pretense.lib.pretense import PretenseSpecificationError, test_only

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
# LAST_CLEANED: 2026-11-12T21:03:16Z
# LAST_CHANGED: 2026-11-12T21:03:16Z
# CHANGE: Implement task queue interface protocol with QueueError/QueueEmptyError/QueueUnavailableException data types and TaskQueue protocol operations.
# --- END AUTOFAB METADATA ---


# === File: task_queue_impl.py ===
"""Concrete bounded task queue implementation."""

from __future__ import annotations

from collections import deque
from typing import Optional

from pretense.parts.pretense.lib.pretense import test_only

from support.lib.framework import data_type, operation, override
from support.lib.lifecycle import get_singleton, singleton

from . import task_queue
from . import task_worker


@data_type
class QueueFullError(task_queue.QueueError):
    """Raised when attempting to submit to a task queue that has reached capacity."""


@singleton
class TaskQueue(task_queue.TaskQueue):
    tier = "system"

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
        """Whether the queue holds no pending tasks."""
        return len(self._queue) == 0

    @property
    def is_full(self) -> bool:
        """Whether the queue has reached its configured capacity."""
        return len(self._queue) >= self._capacity

    @property
    def is_available(self) -> bool:
        """Whether the queue currently accepts operations."""
        return self._is_available

    @property
    @override
    def pending_count(self) -> int:
        """Number of tasks currently awaiting dispatch."""
        return len(self._queue)

    @operation
    @override
    def submit(self, task_id: str, payload: str) -> None:
        """Appends a new task to the queue awaiting execution."""
        # Reject submissions while the queue is operationally unavailable.
        if not self._is_available:
            raise task_queue.QueueUnavailableException()
        # Reject submissions once the queue has reached its capacity bound.
        if self.is_full:
            raise QueueFullError()
        self._queue.append((task_id, payload))

    @operation
    @override
    def dispatch(self) -> str:
        """Dispatches the oldest pending task to the collaborator worker."""
        # Reject dispatch while the queue is operationally unavailable.
        if not self._is_available:
            raise task_queue.QueueUnavailableException()
        # Reject dispatch when there is nothing left to hand out.
        if self.is_empty:
            raise task_queue.QueueEmptyError()
        task_id, payload = self._queue.popleft()
        # Hand the dequeued work to the worker for execution.
        worker = get_singleton(task_worker.TaskWorker)
        worker.execute(task_id, payload)
        return task_id

    @operation
    @override
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome string for a task."""
        # Completions are only accepted while the queue is available.
        if not self._is_available:
            raise task_queue.QueueUnavailableException()
        self._outcomes[task_id] = outcome

    @operation
    @override
    def get_outcome(self, task_id: str) -> Optional[str]:
        """Retrieves the recorded outcome for a task, if any."""
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
        """Test-only hook to toggle task queue availability."""
        self._is_available = available

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:17:39Z
# LAST_CHANGED: 2026-11-12T21:03:27Z
# CHANGE: Implement bounded FIFO TaskQueue singleton with capacity 10, deque/dict backing state, availability and capacity guards, worker dispatch, outcomes, clear, and test-only availability hook.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T21:17:39Z
# PRETENSE_QA_AUDIT: 2026-11-12T21:17:26Z
# --- END AUTOFAB METADATA ---


# === File: task_worker.py ===
"""Library interface for the autonomous task execution worker."""

from __future__ import annotations

from typing import Protocol

from pretense.parts.pretense.lib.pretense import PretenseSpecificationError, test_only

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
# LAST_CLEANED: 2026-11-12T21:03:21Z
# LAST_CHANGED: 2026-11-12T21:03:21Z
# CHANGE: Implement task worker interface protocol with WorkerError/WorkerExecutionException data types and TaskWorker protocol operations.
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl.py ===
"""Concrete task execution worker implementation."""

from __future__ import annotations

from typing import Optional

from pretense.parts.pretense.lib.pretense import test_only

from support.lib.framework import operation, override
from support.lib.lifecycle import get_singleton, singleton

from . import task_queue
from . import task_worker


@singleton
class TaskWorker(task_worker.TaskWorker):
    tier = "system"

    def __init__(self) -> None:
        self._processed_count: int = 0
        self._last_task_id: Optional[str] = None
        self._is_busy: bool = False
        self._failing_tasks: set[str] = set()

    @property
    def processed_count(self) -> int:
        """Number of tasks successfully processed by the worker."""
        return self._processed_count

    @property
    def last_task_id(self) -> Optional[str]:
        """Identifier of the most recently executed task, if any."""
        return self._last_task_id

    @property
    def is_busy(self) -> bool:
        """Whether the worker is currently executing a task."""
        return self._is_busy

    @operation
    def reset(self) -> None:
        """Resets execution telemetry counters and clears transient state."""
        self._processed_count = 0
        self._last_task_id = None
        self._is_busy = False

    @operation
    @override
    def execute(self, task_id: str, payload: str) -> str:
        """Executes a workload payload and reports completion to the task queue."""
        self._is_busy = True
        # Designated failing tasks abort execution before any work is produced.
        if task_id in self._failing_tasks:
            self._is_busy = False
            raise task_worker.WorkerExecutionException()
        # Normalize the workload into the reported outcome form.
        outcome = f"PROCESSED:{payload.upper()}"
        queue = get_singleton(task_queue.TaskQueue)
        try:
            queue.complete(task_id, outcome)
        except task_queue.QueueUnavailableException as exc:
            self._is_busy = False
            raise task_worker.WorkerExecutionException() from exc
        self._last_task_id = task_id
        self._processed_count += 1
        self._is_busy = False
        return outcome

    @operation
    @override
    def fetch_and_execute(self) -> str:
        """Fetches the next pending task from the queue and executes it."""
        queue = get_singleton(task_queue.TaskQueue)
        try:
            task_id = queue.dispatch()
        except task_queue.QueueEmptyError as exc:
            raise task_worker.WorkerError() from exc
        except task_queue.QueueUnavailableException as exc:
            raise task_worker.WorkerExecutionException() from exc
        # The dispatched identifier doubles as the workload payload available here.
        self.execute(task_id, task_id)
        return task_id

    @operation
    @test_only
    @override
    def set_failing_task(self, task_id: str, failing: bool = True) -> None:
        """Test-only hook to designate whether a task should fail on execution."""
        if failing:
            self._failing_tasks.add(task_id)
        else:
            self._failing_tasks.discard(task_id)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:17:41Z
# LAST_CHANGED: 2026-11-12T21:03:32Z
# CHANGE: Implement TaskWorker singleton with payload uppercase PROCESSED outcome, busy/telemetry state, queue completion notification, failure and unavailable error translation, fetch-and-execute, reset, and test-only failing-task hook.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T21:17:41Z
# PRETENSE_QA_AUDIT: 2026-11-12T21:17:28Z
# --- END AUTOFAB METADATA ---
