# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_164340_deepseek-flash_task_queue
# Timestamp: 2026-11-08T16:43:40.930900+00:00
# Benchmark Task: task_queue
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 127,715
#   Cached Inbound Tokens:   4,732,160
#   Outbound Tokens:         72,890
#   Total Tokens:            4,932,765
#   Financial Cost ($USD):   $0.0771
#   Wall Clock Duration:     614.39s
#   Step Latencies (s):      [144.3, 259.7, 115.0, 174.5, 20.3, 20.3]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 2, test: 2 (Total: 6)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       13
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: task_queue.py ===
"""Low-level interface specification for task queue."""

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
        """Appends a new task to the queue awaiting execution."""
        ...

    @operation
    def dispatch(self) -> str:
        """Dispatches the oldest pending task and returns its identifier."""
        ...

    @operation
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome string for a task."""
        ...

    @operation
    def get_outcome(self, task_id: str) -> Optional[str]:
        """Retrieves the recorded outcome for a task."""
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
# LAST_CLEANED: 2026-11-08T16:47:58Z
# LAST_CHANGED: 2026-11-08T16:47:58Z
# CHANGE: Author task_queue interface: queued-domain error types and @poly_type TaskQueue protocol stubs matching low/task_queue.pyi
# --- END AUTOFAB METADATA ---


# === File: task_queue_impl.py ===
"""Low-level implementation specification for bounded task queue."""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, Optional

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import data_type, operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import task_queue
from . import task_worker


@data_type
class QueueFullError(task_queue.QueueError):
    """Raised when attempting to submit to a task queue that has reached capacity."""


@singleton_type("system")
class TaskQueue(task_queue.TaskQueue):
    """Concrete realization of bounded task queue using collections.deque and outcome mapping."""

    tier: str = "system"

    def __init__(self) -> None:
        # Backing state: bounded FIFO storage plus recorded completion outcomes.
        self._capacity: int = 10
        self._queue: Deque[tuple[str, str]] = deque()
        self._outcomes: Dict[str, str] = {}
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
        # Guard: an unavailable queue rejects every submission.
        if not self._is_available:
            raise task_queue.QueueUnavailableException("task queue is unavailable")
        # Guard: a full queue rejects submissions that would exceed capacity.
        if self.is_full:
            raise QueueFullError("task queue is full")
        # Append the task at the queue tail, growing pending_count by one.
        self._queue.append((task_id, payload))

    @operation
    @override
    def dispatch(self) -> str:
        """Dispatches the oldest pending task to the collaborator worker for execution."""
        # Guard: an unavailable queue cannot dispatch.
        if not self._is_available:
            raise task_queue.QueueUnavailableException("task queue is unavailable")
        # Guard: an empty queue has no task to dispatch.
        if self.is_empty:
            raise task_queue.QueueEmptyError("task queue is empty")
        # Pop the oldest task so the queue shrinks before the worker runs.
        task_id, payload = self._queue.popleft()
        # Delegate execution to the collaborator worker resolved on demand.
        worker = get_singleton(task_worker.TaskWorker)
        worker.execute(task_id, payload)
        return task_id

    @operation
    @override
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome string for a task."""
        # Guard: an unavailable queue rejects completion recording.
        if not self._is_available:
            raise task_queue.QueueUnavailableException("task queue is unavailable")
        # Record the outcome keyed by the completed task identifier.
        self._outcomes[task_id] = outcome

    @operation
    @override
    def get_outcome(self, task_id: str) -> Optional[str]:
        """Retrieves the recorded outcome for a task."""
        # Recorded outcome if present, otherwise None for an uncompleted task.
        return self._outcomes.get(task_id)

    @operation
    @override
    def clear(self) -> None:
        """Purges all pending tasks and recorded outcomes from the queue."""
        # Drop all pending tasks, resetting pending_count to zero.
        self._queue.clear()
        # Drop every recorded completion outcome.
        self._outcomes.clear()

    @operation
    @test_only
    @override
    def set_available(self, available: bool) -> None:
        """Test-only hook to toggle task queue availability for operational simulation."""
        self._is_available = available


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        QueueFullError,
        keys=[QueueFullError, task_queue.QueueError],
        tier=system,
    )
    reg.register_singleton(
        TaskQueue,
        keys=[TaskQueue, task_queue.TaskQueue],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T16:53:42Z
# LAST_CHANGED: 2026-11-08T16:48:10Z
# CHANGE: Implement bounded FIFO TaskQueue singleton: deque storage, capacity/availability guards raising QueueUnavailableException and QueueFullError, dispatch delegating to resolved TaskWorker, outcome recording, clear, and test-only availability hook
# COVERAGE_AUDIT: 2026-11-08T16:53:42Z
# QA_AUDIT: 2026-11-08T16:53:19Z
# --- END AUTOFAB METADATA ---


# === File: task_worker.py ===
"""Low-level interface specification for task worker."""

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
        """Executes a workload payload and reports completion to the task queue."""
        ...

    @operation
    def fetch_and_execute(self) -> str:
        """Fetches the next pending task from the collaborator queue and executes it."""
        ...

    @operation
    @test_only
    def set_failing_task(self, task_id: str, failing: bool = True) -> None:
        """Test-only hook to configure designated tasks to fail on execution."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T16:48:04Z
# LAST_CHANGED: 2026-11-08T16:48:04Z
# CHANGE: Author task_worker interface: worker error types and @poly_type TaskWorker protocol stubs matching low/task_worker.pyi
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl.py ===
"""Low-level implementation specification for task execution worker."""

from __future__ import annotations

from typing import Optional, Set

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import task_queue
from . import task_worker


@singleton_type("system")
class TaskWorker(task_worker.TaskWorker):
    """Concrete realization of task worker with payload transformation and execution telemetry."""

    tier: str = "system"

    def __init__(self) -> None:
        # Backing telemetry, busy state, and designated failing task identifiers.
        self._processed_count: int = 0
        self._last_task_id: Optional[str] = None
        self._is_busy: bool = False
        self._failing_tasks: Set[str] = set()

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
        # Guard: designated failing tasks abort execution without recording telemetry.
        if task_id in self._failing_tasks:
            self._is_busy = False
            raise task_worker.WorkerExecutionException(f"task {task_id} failed to execute")
        # Transform the workload payload into its canonical outcome string.
        outcome = f"PROCESSED:{payload.upper()}"
        # Report completion to the collaborator queue resolved on demand.
        queue = get_singleton(task_queue.TaskQueue)
        try:
            queue.complete(task_id, outcome)
        except task_queue.QueueUnavailableException:
            # Queue unavailability reifies as a worker execution failure.
            self._is_busy = False
            raise task_worker.WorkerExecutionException("task queue is unavailable") from None
        # Record telemetry for the successfully reported execution.
        self._last_task_id = task_id
        self._processed_count += 1
        self._is_busy = False
        return outcome

    @operation
    @override
    def fetch_and_execute(self) -> str:
        """Fetches the next pending task from the task queue singleton and executes it."""
        # Resolve the collaborator queue on demand.
        queue = get_singleton(task_queue.TaskQueue)
        try:
            task_id = queue.dispatch()
        except task_queue.QueueEmptyError:
            # An empty collaborator queue surfaces as a worker error.
            raise task_worker.WorkerError("task queue is empty") from None
        except task_queue.QueueUnavailableException:
            # An unavailable collaborator queue surfaces as an execution failure.
            raise task_worker.WorkerExecutionException("task queue is unavailable") from None
        # Dispatch exposes only the identifier; execute it with that identifier as payload.
        self.execute(task_id, task_id)
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


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        TaskWorker,
        keys=[TaskWorker, task_worker.TaskWorker],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T16:53:44Z
# LAST_CHANGED: 2026-11-08T16:48:16Z
# CHANGE: Implement TaskWorker singleton: PAID telemetry, busy tracking, payload-to-outcome transformation, queue completion notification with WorkerExecutionException reification, fetch-and-execute dispatch error translation, reset, and test-only failing-task hook
# COVERAGE_AUDIT: 2026-11-08T16:53:44Z
# QA_AUDIT: 2026-11-08T16:53:21Z
# --- END AUTOFAB METADATA ---
