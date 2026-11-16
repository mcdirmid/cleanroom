# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261114_204258_deepseek-flash_task_queue_pretense
# Timestamp: 2026-11-14T20:42:58.605590+00:00
# Benchmark Task: task_queue
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 5
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 178,276
#   Cached Inbound Tokens:   7,270,784
#   Outbound Tokens:         168,194
#   Total Tokens:            7,617,254
#   Financial Cost ($USD):   $0.1495
#   Wall Clock Duration:     1026.42s
#   Step Latencies (s):      [190.8, 438.4, 20.4, 115.7, 157.2, 227.5, 20.5, 55.7, 10.1, 20.4]
#   Role Execution Rounds:   lib: 1, pretense: 3, pretense_coverage: 3, pretense_qa: 3 (Total: 10)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       3
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: task_queue.py ===
"""Interface specification for the first-in first-out task queue."""

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
        """Appends a new task to the queue awaiting execution."""
        ...

    @operation
    def dispatch(self) -> str:
        """Dispatches the oldest pending task and returns its identifier.

        Raises:
            QueueEmptyError: If the task queue contains zero pending tasks.
            QueueUnavailableException: If the task queue is unavailable.
        """
        ...

    @operation
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome string for a task."""
        ...

    @operation
    def get_outcome(self, task_id: str) -> Optional[str]:
        """Retrieves the recorded outcome for a task, if any."""
        ...

    @operation
    def clear(self) -> None:
        """Purges all pending tasks and recorded outcomes from the queue."""
        ...

    @operation
    @test_only
    def set_available(self, available: bool) -> None:
        """Test-only hook to toggle task queue availability for operational simulation."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T20:45:40Z
# LAST_CHANGED: 2026-11-14T20:45:40Z
# CHANGE: Implement task queue interface: QueueError/QueueEmptyError/QueueUnavailableException hierarchy and TaskQueue Protocol with pending_count, submit, dispatch, complete, get_outcome, clear, and test-only set_available operations per low/task_queue.pyi.
# --- END AUTOFAB METADATA ---


# === File: task_queue_impl.py ===
"""Concrete bounded first-in first-out task queue implementation."""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, Optional, Tuple

from pretense import test_only

from support.lib.framework import data_type, operation, override
from support.lib.lifecycle import get_singleton, singleton

from . import task_queue, task_worker


@data_type
class QueueFullError(task_queue.QueueError):
    """Raised when attempting to submit to a task queue that has reached capacity."""


@singleton
class TaskQueue(task_queue.TaskQueue):
    """Bounded FIFO task queue backed by a deque and an outcome mapping."""

    tier = "system"

    def __init__(self) -> None:
        self._capacity: int = 10
        self._queue: Deque[Tuple[str, str]] = deque()
        self._outcomes: Dict[str, str] = {}
        self._is_available: bool = True

    @property
    def capacity(self) -> int:
        """Maximum number of pending tasks permitted in the queue."""
        return self._capacity

    @property
    def is_empty(self) -> bool:
        """Indicates whether the queue holds zero pending tasks."""
        return len(self._queue) == 0

    @property
    def is_full(self) -> bool:
        """Indicates whether the queue has reached its capacity limit."""
        return len(self._queue) >= self._capacity

    @property
    def is_available(self) -> bool:
        """Indicates whether the queue accepts operations."""
        return self._is_available

    @property
    @override
    def pending_count(self) -> int:
        """Current number of pending tasks stored in the queue."""
        return len(self._queue)

    @operation
    @override
    def submit(self, task_id: str, payload: str) -> None:
        """Appends a task to the queue tail once availability and capacity allow it."""
        if not self._is_available:
            raise task_queue.QueueUnavailableException("Task queue is unavailable.")
        # Reject submissions only after the bounded queue has reached its capacity.
        if self.is_full:
            raise QueueFullError(
                f"Task queue is full: capacity of {self._capacity} pending tasks reached."
            )
        self._queue.append((task_id, payload))

    @operation
    @override
    def dispatch(self) -> str:
        """Pops the oldest task and hands it to the collaborator worker for execution."""
        if not self._is_available:
            raise task_queue.QueueUnavailableException("Task queue is unavailable.")
        # An available queue with no pending tasks cannot dispatch anything.
        if self.is_empty:
            raise task_queue.QueueEmptyError("Task queue is empty: no task to dispatch.")
        task_id, payload = self._queue.popleft()
        worker = get_singleton(task_worker.TaskWorker)
        worker.execute(task_id, payload)
        return task_id

    @operation
    @override
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome for a task while the queue is available."""
        if not self._is_available:
            raise task_queue.QueueUnavailableException("Task queue is unavailable.")
        self._outcomes[task_id] = outcome

    @operation
    @override
    def get_outcome(self, task_id: str) -> Optional[str]:
        """Returns the recorded outcome for a task, or None when it has not completed."""
        return self._outcomes.get(task_id)

    @operation
    @override
    def clear(self) -> None:
        """Purges every pending task and every recorded outcome."""
        self._queue.clear()
        self._outcomes.clear()

    @operation
    @test_only
    @override
    def set_available(self, available: bool) -> None:
        """Test-only hook toggling queue availability for operational simulation."""
        self._is_available = available

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T20:58:56Z
# LAST_CHANGED: 2026-11-14T20:45:58Z
# CHANGE: Implement bounded FIFO task queue singleton with deque backing and outcome mapping: capacity 10, availability/emptiness/fullness properties, submit with QueueFullError and QueueUnavailableException guards, dispatch that pops the oldest task and invokes the TaskWorker collaborator, complete/get_outcome recording, clear purge, and test-only set_available.
# PRETENSE_COVERAGE_AUDIT: 2026-11-14T20:58:56Z
# PRETENSE_QA_AUDIT: 2026-11-14T20:55:03Z
# --- END AUTOFAB METADATA ---


# === File: task_worker.py ===
"""Interface specification for the autonomous task execution worker."""

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

        Raises:
            WorkerExecutionException: If the task queue is unavailable or task fails.
        """
        ...

    @operation
    def fetch_and_execute(self) -> str:
        """Fetches the next pending task from the collaborator queue and executes it.

        Raises:
            WorkerError: If the collaborator task queue contains zero pending tasks.
            WorkerExecutionException: If the collaborator task queue is unavailable.
        """
        ...

    @operation
    @test_only
    def set_failing_task(self, task_id: str, failing: bool = True) -> None:
        """Test-only hook to configure designated tasks to fail on execution."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T20:45:46Z
# LAST_CHANGED: 2026-11-14T20:45:46Z
# CHANGE: Implement task worker interface: WorkerError/WorkerExecutionException hierarchy and TaskWorker Protocol with execute, fetch_and_execute, and test-only set_failing_task operations per low/task_worker.pyi.
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl.py ===
"""Concrete task execution worker implementation."""

from __future__ import annotations

from typing import Optional, Set

from pretense import test_only

from support.lib.framework import operation, override
from support.lib.lifecycle import get_singleton, singleton

from . import task_queue, task_worker


@singleton
class TaskWorker(task_worker.TaskWorker):
    """Executes workloads, reports completions, and records execution telemetry."""

    tier = "system"

    def __init__(self) -> None:
        self._processed_count: int = 0
        self._last_task_id: Optional[str] = None
        self._is_busy: bool = False
        self._failing_tasks: Set[str] = set()

    @property
    def processed_count(self) -> int:
        """Number of tasks successfully processed so far."""
        return self._processed_count

    @property
    def last_task_id(self) -> Optional[str]:
        """Identifier of the most recently executed task, if any."""
        return self._last_task_id

    @property
    def is_busy(self) -> bool:
        """Indicates whether the worker is currently executing a task."""
        return self._is_busy

    @operation
    def reset(self) -> None:
        """Resets telemetry counters and clears the last task and busy state."""
        self._processed_count = 0
        self._last_task_id = None
        self._is_busy = False

    @operation
    @override
    def execute(self, task_id: str, payload: str) -> str:
        """Processes a payload, reports completion to the queue, and returns the outcome."""
        self._is_busy = True
        # A designated failing task aborts execution before any outcome is recorded.
        if task_id in self._failing_tasks:
            self._is_busy = False
            raise task_worker.WorkerExecutionException(
                f"Task '{task_id}' failed during execution."
            )
        outcome = f"PROCESSED:{payload.upper()}"
        queue = get_singleton(task_queue.TaskQueue)
        try:
            queue.complete(task_id, outcome)
        except task_queue.QueueUnavailableException as exc:
            self._is_busy = False
            raise task_worker.WorkerExecutionException(
                f"Task queue unavailable while reporting completion of '{task_id}'."
            ) from exc
        self._last_task_id = task_id
        self._processed_count += 1
        self._is_busy = False
        return outcome

    @operation
    @override
    def fetch_and_execute(self) -> str:
        """Dispatches the next pending task from the queue and returns its identifier."""
        queue = get_singleton(task_queue.TaskQueue)
        try:
            task_id = queue.dispatch()
        except task_queue.QueueEmptyError as exc:
            raise task_worker.WorkerError(
                "Cannot fetch a task: the task queue holds no pending tasks."
            ) from exc
        except task_queue.QueueUnavailableException as exc:
            raise task_worker.WorkerExecutionException(
                "Cannot fetch a task: the task queue is unavailable."
            ) from exc
        return task_id

    @operation
    @test_only
    @override
    def set_failing_task(self, task_id: str, failing: bool = True) -> None:
        """Test-only hook designating a task to fail (or stop failing) on execution."""
        if failing:
            self._failing_tasks.add(task_id)
        else:
            self._failing_tasks.discard(task_id)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T20:59:52Z
# LAST_CHANGED: 2026-11-14T20:46:04Z
# CHANGE: Implement task worker singleton: telemetry (processed_count, last_task_id, is_busy), reset, execute that transforms payloads into PROCESSED:<upper> outcomes, records completion through the TaskQueue collaborator, translates queue unavailability and designated failing tasks into WorkerExecutionException, and fetch_and_execute that dispatches from the queue translating QueueEmptyError to WorkerError and QueueUnavailableException to WorkerExecutionException.
# PRETENSE_COVERAGE_AUDIT: 2026-11-14T20:59:52Z
# PRETENSE_QA_AUDIT: 2026-11-14T20:59:39Z
# --- END AUTOFAB METADATA ---
