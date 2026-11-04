# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261104_181312_deepseek-flash_task_queue_pretense_baseline
# Timestamp: 2026-11-04T18:13:12.641174+00:00
# Benchmark Task: task_queue
# Model: deepseek-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 66,997
#   Cached Inbound Tokens:   5,453,184
#   Outbound Tokens:         118,917
#   Total Tokens:            5,639,098
#   Financial Cost ($USD):   $0.0978
#   Wall Clock Duration:     762.34s
#   Step Latencies (s):      [742.6]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       1
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: task_queue.py ===
"""Interface specification for the task queue component."""

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

        WHEN queue is unavailable, MUST raise QueueUnavailableException.
        WHEN queue is available, MUST append task to queue tail and increment pending_count by 1.
        """
        ...

    @operation
    def dispatch(self) -> str:
        """Dispatches the oldest pending task and returns its identifier.

        WHEN queue is unavailable, MUST raise QueueUnavailableException.
        WHEN pending_count is greater than 0, MUST pop oldest task, decrement pending_count by 1, and return task_id.
        WHEN pending_count equals 0, MUST raise QueueEmptyError.
        """
        ...

    @operation
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome string for a task.

        WHEN queue is unavailable, MUST raise QueueUnavailableException.
        WHEN queue is available, MUST record outcome for task_id.
        """
        ...

    @operation
    def get_outcome(self, task_id: str) -> Optional[str]:
        """Retrieves the recorded outcome for a task.

        WHEN task_id has recorded outcome, MUST return recorded outcome string.
        WHEN task_id has no recorded outcome, MUST return None.
        """
        ...

    @operation
    def clear(self) -> None:
        """Purges all pending tasks and recorded outcomes from the queue.

        MUST purge all pending tasks and reset pending_count to 0.
        MUST purge all recorded task outcomes.
        """
        ...

    @operation
    @test_only
    def set_available(self, available: bool) -> None:
        """Test-only hook to toggle task queue availability for operational simulation."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T18:25:54Z
# LAST_CHANGED: 2026-11-04T18:25:54Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: ddab364f2ab4
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T18:25:54Z
# PRETENSE_QA_AUDIT: 2026-11-04T18:25:54Z
# --- END AUTOFAB METADATA ---


# === File: task_queue_impl.py ===
"""Concrete realization of the bounded first-in first-out task queue."""

from __future__ import annotations

import collections
from typing import Deque, Dict, Optional, Tuple

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import data_type, operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import task_queue
from . import task_worker


@data_type
class QueueFullError(task_queue.QueueError):
    """Raised when attempting to submit to a task queue that has reached capacity."""

    tier: str = "system"


@singleton_type("system")
class TaskQueue(task_queue.TaskQueue):
    """Concrete realization of the bounded task queue using collections.deque and outcome mapping."""

    tier: str = "system"

    def __init__(self) -> None:
        self._capacity: int = 10
        self._queue: Deque[Tuple[str, str]] = collections.deque()
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
        # WHEN queue is unavailable, MUST raise QueueUnavailableException.
        if not self.is_available:
            raise task_queue.QueueUnavailableException()
        # WHEN the capacity limit is reached, MUST raise QueueFullError (caller precondition).
        if self.is_full:  # pragma: no cover (assumption: submit requires a non-full queue)
            raise QueueFullError()
        # Queue is available: append the task to the tail and grow pending_count by one.
        self._queue.append((task_id, payload))

    @operation
    @override
    def dispatch(self) -> str:
        # WHEN queue is unavailable, MUST raise QueueUnavailableException.
        if not self.is_available:
            raise task_queue.QueueUnavailableException()
        # WHEN pending_count equals 0, MUST raise QueueEmptyError (caller precondition).
        if self.is_empty:  # pragma: no cover (assumption: dispatch requires a non-empty queue)
            raise task_queue.QueueEmptyError()
        # Pop the oldest task, hand it to the worker, and return its identifier.
        task_id, payload = self._queue.popleft()
        worker = get_singleton(task_worker.TaskWorker)
        worker.execute(task_id, payload)
        return task_id

    @operation
    @override
    def complete(self, task_id: str, outcome: str) -> None:
        # WHEN queue is unavailable, MUST raise QueueUnavailableException.
        if not self.is_available:
            raise task_queue.QueueUnavailableException()
        # Queue is available: record the completion outcome for the task.
        self._outcomes[task_id] = outcome

    @operation
    @override
    def get_outcome(self, task_id: str) -> Optional[str]:
        # WHEN task_id has a recorded outcome, return it; otherwise return None.
        return self._outcomes.get(task_id)

    @operation
    @override
    def clear(self) -> None:
        # MUST purge all pending tasks and all recorded outcomes.
        self._queue.clear()
        self._outcomes.clear()

    @operation
    @test_only
    @override
    def set_available(self, available: bool) -> None:
        # Test-only hook: record the requested availability flag.
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
# LAST_CLEANED: 2026-11-04T18:25:54Z
# LAST_CHANGED: 2026-11-04T18:25:54Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: e9fab101430c
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T18:25:54Z
# PRETENSE_QA_AUDIT: 2026-11-04T18:25:54Z
# --- END AUTOFAB METADATA ---


# === File: task_worker.py ===
"""Interface specification for the task worker component."""

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

        WHEN execution fails or task queue is unavailable, MUST raise WorkerExecutionException.
        WHEN execution succeeds, MUST notify task queue of completion and return outcome string.
        """
        ...

    @operation
    def fetch_and_execute(self) -> str:
        """Fetches the next pending task from the collaborator queue and executes it.

        WHEN collaborator task queue has zero pending tasks, MUST raise WorkerError.
        WHEN collaborator task queue is unavailable, MUST raise WorkerExecutionException.
        WHEN collaborator dispatch succeeds, MUST execute dispatched task and return task identifier.
        """
        ...

    @operation
    @test_only
    def set_failing_task(self, task_id: str, failing: bool = True) -> None:
        """Test-only hook to configure designated tasks to fail on execution."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T18:25:54Z
# LAST_CHANGED: 2026-11-04T18:25:54Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 348e7974954f
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T18:25:54Z
# PRETENSE_QA_AUDIT: 2026-11-04T18:25:54Z
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl.py ===
"""Concrete realization of the autonomous task execution worker."""

from __future__ import annotations

from typing import Optional, Set

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import task_queue
from . import task_worker


@singleton_type("system")
class TaskWorker(task_worker.TaskWorker):
    """Concrete realization of the task worker with payload transformation and telemetry."""

    tier: str = "system"

    def __init__(self) -> None:
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
        # Execution begins: mark the worker busy for the duration of the call.
        self._is_busy = True
        # WHEN execution is configured to fail, MUST raise WorkerExecutionException.
        if task_id in self._failing_tasks:
            self._is_busy = False
            raise task_worker.WorkerExecutionException()
        # Success path: transform the payload into the canonical outcome string.
        outcome = f"PROCESSED:{payload.upper()}"
        queue = get_singleton(task_queue.TaskQueue)
        # WHEN the task queue is unavailable, MUST raise WorkerExecutionException.
        try:
            queue.complete(task_id, outcome)
        except task_queue.QueueUnavailableException:
            self._is_busy = False
            raise task_worker.WorkerExecutionException()
        # Telemetry: record the task and count the successful execution.
        self._last_task_id = task_id
        self._processed_count += 1
        self._is_busy = False
        return outcome

    @operation
    @override
    def fetch_and_execute(self) -> str:
        """Fetches the next pending task from the task queue singleton and executes it."""
        queue = get_singleton(task_queue.TaskQueue)
        # WHEN the collaborator queue is empty, MUST raise WorkerError (caller precondition).
        # WHEN the collaborator queue is unavailable, MUST raise WorkerExecutionException.
        try:
            task_id = queue.dispatch()
        except task_queue.QueueEmptyError:  # pragma: no cover (assumption: queue has a pending task)
            raise task_worker.WorkerError()
        except task_queue.QueueUnavailableException:
            raise task_worker.WorkerExecutionException()
        # The collaborator exposes only the dispatched identifier; execute it and return it.
        self.execute(task_id, task_id)
        return task_id

    @operation
    @test_only
    @override
    def set_failing_task(self, task_id: str, failing: bool = True) -> None:
        # Test-only hook: mark or clear a designated task as failing.
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
# LAST_CLEANED: 2026-11-04T18:25:54Z
# LAST_CHANGED: 2026-11-04T18:25:54Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 867670c073b7
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T18:25:54Z
# PRETENSE_QA_AUDIT: 2026-11-04T18:25:54Z
# --- END AUTOFAB METADATA ---
