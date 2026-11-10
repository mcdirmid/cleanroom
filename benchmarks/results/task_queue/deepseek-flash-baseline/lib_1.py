# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261104_181315_deepseek-flash_task_queue_baseline
# Timestamp: 2026-11-04T18:13:15.524500+00:00
# Benchmark Task: task_queue
# Model: deepseek-flash (Tier 2)
# Methodology: baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 76,748
#   Cached Inbound Tokens:   10,827,008
#   Outbound Tokens:         157,957
#   Total Tokens:            11,061,713
#   Financial Cost ($USD):   $0.1388
#   Wall Clock Duration:     1059.94s
#   Step Latencies (s):      [1043.1]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       10
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: task_queue.py ===
"""Interface module for the task queue.

Formalizes ``low/task_queue.pyi``: an abstract FIFO task queue protocol plus the
domain error hierarchy shared with its concrete implementation.
"""

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

        POSTCONDITIONS:
        - WHEN queue is unavailable, MUST raise QueueUnavailableException.
        - WHEN queue is available, MUST append task to queue tail and increment pending_count by 1.
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

        POSTCONDITIONS:
        - WHEN queue is unavailable, MUST raise QueueUnavailableException.
        - WHEN pending_count is greater than 0, MUST pop oldest task, decrement pending_count by 1, and return task_id.
        - WHEN pending_count equals 0, MUST raise QueueEmptyError.
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
        - WHEN queue is unavailable, MUST raise QueueUnavailableException.
        - WHEN queue is available, MUST record outcome for task_id.
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
        - WHEN task_id has recorded outcome, MUST return recorded outcome string.
        - WHEN task_id has no recorded outcome, MUST return None.
        """
        ...

    @operation
    def clear(self) -> None:
        """Purges all pending tasks and recorded outcomes from the queue.

        POSTCONDITIONS:
        - MUST purge all pending tasks and reset pending_count to 0.
        - MUST purge all recorded task outcomes.
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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T18:30:55Z
# LAST_CHANGED: 2026-11-04T18:30:55Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: dea20961d3bf
# COVERAGE_AUDIT: 2026-11-04T18:30:55Z
# QA_AUDIT: 2026-11-04T18:30:55Z
# --- END AUTOFAB METADATA ---


# === File: task_queue_impl.py ===
"""Implementation module for the bounded task queue.

Realizes ``low/task_queue_impl.pyi``: a bounded first-in first-out task queue backed
by ``collections.deque`` with recorded completion outcomes and availability control.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, Optional, Tuple
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


@singleton_type("system")
class TaskQueue(task_queue.TaskQueue):
    """Concrete realization of bounded task queue using collections.deque and outcome mapping."""

    tier: str = "system"

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
        # POSTCONDITION: pending_count reflects the number of queued tasks.
        return len(self._queue)

    @operation
    @override
    def submit(self, task_id: str, payload: str) -> None:
        """Appends a new task to the queue awaiting execution."""
        # POSTCONDITION: unavailable queue raises QueueUnavailableException.
        if not self.is_available:
            raise task_queue.QueueUnavailableException(
                "Cannot submit to an unavailable task queue"
            )
        # PRECONDITION: caller respects the configured capacity bound.
        if self.is_full:  # unreachable (assumption: caller respects capacity bound)
            raise QueueFullError("Cannot submit to a full task queue")
        # POSTCONDITION: available queue appends the task to the tail.
        self._queue.append((task_id, payload))

    @operation
    @override
    def dispatch(self) -> str:
        """Dispatches the oldest pending task to the collaborator worker for execution."""
        # POSTCONDITION: unavailable queue raises QueueUnavailableException.
        if not self.is_available:
            raise task_queue.QueueUnavailableException(
                "Cannot dispatch from an unavailable task queue"
            )
        # PRECONDITION: caller only dispatches when a pending task exists.
        if self.is_empty:  # unreachable (assumption: caller checks pending count)
            raise task_queue.QueueEmptyError("Cannot dispatch from an empty task queue")
        # POSTCONDITION: pops the oldest task and hands it to the worker.
        task_id, payload = self._queue.popleft()
        worker = get_singleton(task_worker.TaskWorker)
        worker.execute(task_id, payload)
        return task_id

    @operation
    @override
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome string for a task."""
        # POSTCONDITION: unavailable queue raises QueueUnavailableException.
        if not self.is_available:
            raise task_queue.QueueUnavailableException(
                "Cannot complete a task on an unavailable task queue"
            )
        # POSTCONDITION: available queue records the outcome for task_id.
        self._outcomes[task_id] = outcome

    @operation
    @override
    def get_outcome(self, task_id: str) -> Optional[str]:
        """Retrieves the recorded outcome for a task."""
        # POSTCONDITION: recorded outcomes are returned, otherwise None.
        return self._outcomes.get(task_id)

    @operation
    @override
    def clear(self) -> None:
        """Purges all pending tasks and recorded outcomes from the queue."""
        # POSTCONDITION: purges every pending task and every recorded outcome.
        self._queue.clear()
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
# LAST_CLEANED: 2026-11-04T18:30:55Z
# LAST_CHANGED: 2026-11-04T18:30:55Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 8d7afd2e3b68
# COVERAGE_AUDIT: 2026-11-04T18:30:55Z
# QA_AUDIT: 2026-11-04T18:30:55Z
# --- END AUTOFAB METADATA ---


# === File: task_worker.py ===
"""Interface module for the task worker.

Formalizes ``low/task_worker.pyi``: an abstract autonomous task execution worker
protocol plus the worker domain error hierarchy.
"""

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

        POSTCONDITIONS:
        - WHEN collaborator task queue has zero pending tasks, MUST raise WorkerError.
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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T18:30:55Z
# LAST_CHANGED: 2026-11-04T18:30:55Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: a0a11c06ce9f
# COVERAGE_AUDIT: 2026-11-04T18:30:55Z
# QA_AUDIT: 2026-11-04T18:30:55Z
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl.py ===
"""Implementation module for the task execution worker.

Realizes ``low/task_worker_impl.pyi``: an autonomous worker that transforms payloads,
reports completion to the task queue, and tracks execution telemetry.
"""

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
    """Concrete realization of task worker with payload transformation and execution telemetry."""

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
        # POSTCONDITION: telemetry counters and busy state are cleared.
        self._processed_count = 0
        self._last_task_id = None
        self._is_busy = False

    @operation
    @override
    def execute(self, task_id: str, payload: str) -> str:
        """Executes a workload payload, reports completion to task queue, and updates telemetry."""
        # POSTCONDITION: the worker is busy while a task executes.
        self._is_busy = True
        # POSTCONDITION: designated failing tasks raise WorkerExecutionException.
        if task_id in self._failing_tasks:
            self._is_busy = False
            raise task_worker.WorkerExecutionException(
                f"Task '{task_id}' failed during execution"
            )
        # POSTCONDITION: payloads are transformed into an uppercased outcome.
        outcome = f"PROCESSED:{payload.upper()}"
        queue = get_singleton(task_queue.TaskQueue)
        try:
            # POSTCONDITION: successful execution notifies the task queue of completion.
            queue.complete(task_id, outcome)
        except task_queue.QueueUnavailableException as exc:
            # POSTCONDITION: an unavailable queue raises WorkerExecutionException.
            self._is_busy = False
            raise task_worker.WorkerExecutionException(
                "Cannot report completion to an unavailable task queue"
            ) from exc
        # POSTCONDITION: telemetry records the executed task and clears the busy state.
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
            # POSTCONDITION: dispatch transfers the oldest task to this worker for execution.
            task_id = queue.dispatch()
        except task_queue.QueueEmptyError as exc:  # unreachable (assumption: caller checks pending count)
            # POSTCONDITION: an empty collaborator queue raises WorkerError.
            raise task_worker.WorkerError("Cannot fetch from an empty task queue") from exc
        except task_queue.QueueUnavailableException as exc:
            # POSTCONDITION: an unavailable collaborator queue raises WorkerExecutionException.
            raise task_worker.WorkerExecutionException(
                "Cannot fetch from an unavailable task queue"
            ) from exc
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
# LAST_CLEANED: 2026-11-04T18:30:55Z
# LAST_CHANGED: 2026-11-04T18:30:55Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: cff130e3fbc8
# COVERAGE_AUDIT: 2026-11-04T18:30:55Z
# QA_AUDIT: 2026-11-04T18:30:55Z
# --- END AUTOFAB METADATA ---
