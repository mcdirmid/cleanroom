# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_165421_deepseek-flash_task_queue_combined
# Timestamp: 2026-11-08T16:54:21.757546+00:00
# Benchmark Task: task_queue
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 439,600
#   Cached Inbound Tokens:   37,312,512
#   Outbound Tokens:         398,263
#   Total Tokens:            38,150,375
#   Financial Cost ($USD):   $0.4168
#   Wall Clock Duration:     2180.36s
#   Step Latencies (s):      [168.7, 337.4, 158.2, 20.5, 95.8, 20.5, 10.1, 648.6, 345.0, 397.1, 53.9, 52.0, 72.9, 20.5, 263.1, 33.4, 54.2, 20.6, 290.1, 72.9, 85.6, 10.0, 20.5, 47.9, 62.4, 12.3, 10.1, 12.3, 10.1]
#   Role Execution Rounds:   coverage: 3, lib: 3, pretense: 5, pretense_coverage: 4, pretense_qa: 8, qa: 4, test: 2 (Total: 29)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       14
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: task_queue.py ===
"""Library interface for the first-in first-out task queue."""

from __future__ import annotations

from typing import Optional, Protocol

from pretense.parts.pretense.lib.pretense import (
    PretenseSpecificationError,
    test_only,
)
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
        """
        ...

    @operation
    def dispatch(self) -> str:
        """Dispatches the oldest pending task and returns its identifier.

        Returns:
            Dispatched task identifier.
        """
        ...

    @operation
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome string for a task.

        Args:
            task_id: Task identifier.
            outcome: Execution result outcome string.
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
# LAST_CLEANED: 2026-11-08T17:00:04Z
# LAST_CHANGED: 2026-11-08T17:00:04Z
# CHANGE: Implement task queue interface: formalize QueueError/QueueEmptyError/QueueUnavailableException and the TaskQueue protocol with contracted operation members decorated per the low-level specification.
# --- END AUTOFAB METADATA ---


# === File: task_queue_impl.py ===
"""Library implementation of the bounded first-in first-out task queue."""

from __future__ import annotations

from collections import deque
from typing import Dict, Optional, Tuple

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import data_type, operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)

from . import task_queue
from . import task_worker


@data_type
class QueueFullError(task_queue.QueueError):
    """Raised when attempting to submit to a task queue that has reached capacity."""

    tier = system


@singleton_type("system")
class TaskQueue(task_queue.TaskQueue):
    """Concrete bounded FIFO task queue backed by a deque and an outcome mapping."""

    tier: str = "system"

    def __init__(self) -> None:
        # Backing state: bounded pending queue, recorded outcomes, availability flag.
        self._capacity: int = 10
        self._queue: deque[Tuple[str, str]] = deque()
        self._outcomes: Dict[str, str] = {}
        self._is_available: bool = True

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0

    @property
    def is_full(self) -> bool:
        return len(self._queue) >= self._capacity

    @property
    def is_available(self) -> bool:
        return self._is_available

    @property
    @override
    def pending_count(self) -> int:
        return len(self._queue)

    @operation
    @override
    def submit(self, task_id: str, payload: str) -> None:
        # An unavailable queue rejects submissions before any state mutation.
        if not self._is_available:
            raise task_queue.QueueUnavailableException()
        # A full queue rejects submissions before appending to the tail.
        if self.is_full:
            raise QueueFullError()
        self._queue.append((task_id, payload))

    @operation
    @override
    def dispatch(self) -> str:
        # An unavailable queue cannot dispatch pending work.
        if not self._is_available:
            raise task_queue.QueueUnavailableException()
        # An empty queue has no oldest task to dispatch.
        if self.is_empty:
            raise task_queue.QueueEmptyError()
        # Pop the oldest task from the head and hand it to the collaborator worker.
        task_id, payload = self._queue.popleft()
        worker = get_singleton(task_worker.TaskWorker)
        worker.execute(task_id, payload)
        return task_id

    @operation
    @override
    def complete(self, task_id: str, outcome: str) -> None:
        # An unavailable queue cannot record completion outcomes.
        if not self._is_available:
            raise task_queue.QueueUnavailableException()
        self._outcomes[task_id] = outcome

    @operation
    @override
    def get_outcome(self, task_id: str) -> Optional[str]:
        return self._outcomes.get(task_id)

    @operation
    @override
    def clear(self) -> None:
        # Purge both pending tasks and recorded outcomes.
        self._queue.clear()
        self._outcomes.clear()

    @operation
    @test_only
    @override
    def set_available(self, available: bool) -> None:
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
# LAST_CLEANED: 2026-11-08T17:27:05Z
# LAST_CHANGED: 2026-11-08T17:00:16Z
# CHANGE: Implement bounded FIFO task queue singleton: deque-backed pending queue with capacity 10, outcome mapping, availability gating, contracted error raising, and worker dispatch via get_singleton.
# COVERAGE_AUDIT: 2026-11-08T17:03:22Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:27:05Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:25:24Z
# QA_AUDIT: 2026-11-08T17:00:41Z
# --- END AUTOFAB METADATA ---


# === File: task_worker.py ===
"""Library interface for the autonomous task execution worker."""

from __future__ import annotations

from typing import Protocol

from pretense.parts.pretense.lib.pretense import (
    PretenseSpecificationError,
    test_only,
)
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
        """
        ...

    @operation
    def fetch_and_execute(self) -> str:
        """Fetches the next pending task from the collaborator queue and executes it.

        Returns:
            Dispatched task identifier.
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
# LAST_CLEANED: 2026-11-08T17:00:10Z
# LAST_CHANGED: 2026-11-08T17:00:10Z
# CHANGE: Implement task worker interface: formalize WorkerError/WorkerExecutionException and the TaskWorker protocol with contracted operation members per the low-level specification.
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl.py ===
"""Library implementation of the autonomous task execution worker."""

from __future__ import annotations

from typing import Optional, Set

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)

from . import task_queue
from . import task_worker


@singleton_type("system")
class TaskWorker(task_worker.TaskWorker):
    """Concrete task execution worker with payload transformation and telemetry."""

    tier: str = "system"

    def __init__(self) -> None:
        # Backing state: telemetry counters, busy flag, and designated failures.
        self._processed_count: int = 0
        self._last_task_id: Optional[str] = None
        self._is_busy: bool = False
        self._failing_tasks: Set[str] = set()

    @property
    def processed_count(self) -> int:
        return self._processed_count

    @property
    def last_task_id(self) -> Optional[str]:
        return self._last_task_id

    @property
    def is_busy(self) -> bool:
        return self._is_busy

    @operation
    def reset(self) -> None:
        self._processed_count = 0
        self._last_task_id = None
        self._is_busy = False

    @operation
    @override
    def execute(self, task_id: str, payload: str) -> str:
        self._is_busy = True
        # A designated failing task aborts without recording completion.
        if task_id in self._failing_tasks:
            self._is_busy = False
            raise task_worker.WorkerExecutionException()
        outcome = f"PROCESSED:{payload.upper()}"
        # Notify the collaborator queue of completion; queue unavailability is a
        # worker execution failure.
        queue = get_singleton(task_queue.TaskQueue)
        try:
            queue.complete(task_id, outcome)
        except task_queue.QueueUnavailableException:
            self._is_busy = False
            raise task_worker.WorkerExecutionException()
        self._last_task_id = task_id
        self._processed_count += 1
        self._is_busy = False
        return outcome

    @operation
    @override
    def fetch_and_execute(self) -> str:
        queue = get_singleton(task_queue.TaskQueue)
        try:
            # Fetch the oldest pending task identifier from the queue.
            task_id = queue.dispatch()
        except task_queue.QueueEmptyError:
            raise task_worker.WorkerError()
        except task_queue.QueueUnavailableException:
            raise task_worker.WorkerExecutionException()
        # The worker itself executes the dispatched task, reporting completion
        # to the queue and recording its own execution telemetry.
        payload = task_id
        self.execute(task_id, payload)
        return task_id

    @operation
    @test_only
    @override
    def set_failing_task(self, task_id: str, failing: bool = True) -> None:
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
# LAST_CLEANED: 2026-11-08T17:30:38Z
# LAST_CHANGED: 2026-11-08T17:29:55Z
# CHANGE: Fix fetch_and_execute state mutation: after dispatching the oldest task identifier (mapping QueueEmptyError to WorkerError and QueueUnavailableException to WorkerExecutionException), the worker now unconditionally calls self.execute(task_id, payload) so it notifies queue completion, sets last_task_id, and increments processed_count before returning the identifier; the conditional guard is gone so no unreachable branch remains.
# COVERAGE_AUDIT: 2026-11-08T17:30:36Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:30:38Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:30:24Z
# QA_AUDIT: 2026-11-08T17:30:21Z
# --- END AUTOFAB METADATA ---
