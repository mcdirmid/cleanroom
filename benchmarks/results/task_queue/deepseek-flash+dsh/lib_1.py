# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261104_183518_deepseek-flash_task_queue
# Timestamp: 2026-11-04T18:35:18.644056+00:00
# Benchmark Task: task_queue
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 167,975
#   Cached Inbound Tokens:   7,636,352
#   Outbound Tokens:         182,900
#   Total Tokens:            7,987,227
#   Financial Cost ($USD):   $0.1578
#   Wall Clock Duration:     1081.64s
#   Step Latencies (s):      [197.8, 294.1, 63.2, 116.7, 10.3, 231.9, 305.6, 10.3, 10.3]
#   Role Execution Rounds:   coverage: 2, lib: 2, qa: 3, test: 2 (Total: 9)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       8
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: task_queue.py ===
"""Low-level interface specification for task queue."""

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
# LAST_CLEANED: 2026-11-04T18:38:13Z
# LAST_CHANGED: 2026-11-04T18:38:13Z
# CHANGE: Implement task queue interface protocol: QueueError/QueueEmptyError/QueueUnavailableException data types and TaskQueue Protocol with pending_count, submit, dispatch, complete, get_outcome, clear, set_available; use package-qualified pretense imports and framework decorators per guide.
# --- END AUTOFAB METADATA ---


# === File: task_queue_impl.py ===
"""Low-level implementation specification for bounded task queue."""

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

    tier = system


@singleton_type("system")
class TaskQueue(task_queue.TaskQueue):
    """Concrete realization of bounded task queue using collections.deque and outcome mapping.

    GROUNDING:
    - Realizes bounded FIFO task queue with default capacity 10 using collections.deque and dict.
    - Initializes internal _capacity to 10, _queue to collections.deque(), _outcomes to dict(), and _is_available to True.
    - Coordinates with task_worker.TaskWorker for task execution dispatch.
    """

    tier = system

    def __init__(self) -> None:
        # Backing state for pending FIFO entries, recorded outcomes, and availability.
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
        return len(self._queue)

    @operation
    @override
    def submit(self, task_id: str, payload: str) -> None:
        """Appends a new task to the queue awaiting execution."""
        # WHEN queue is unavailable, MUST raise QueueUnavailableException.
        if not self._is_available:
            raise task_queue.QueueUnavailableException
        # WHEN queue is at capacity, MUST reject with QueueFullError.
        if self.is_full:
            raise QueueFullError
        # WHEN queue is available, MUST append task to tail (pending_count increments).
        self._queue.append((task_id, payload))
        assert self.pending_count > 0

    @operation
    @override
    def dispatch(self) -> str:
        """Dispatches the oldest pending task to the collaborator worker for execution."""
        # WHEN queue is unavailable, MUST raise QueueUnavailableException.
        if not self._is_available:
            raise task_queue.QueueUnavailableException
        # WHEN pending_count equals 0, MUST raise QueueEmptyError.
        if self.is_empty:
            raise task_queue.QueueEmptyError
        # WHEN pending_count is greater than 0, MUST pop the oldest task (FIFO).
        task_id, payload = self._queue.popleft()
        # Hand the dispatched task to the collaborator worker; it reports completion.
        worker = get_singleton(task_worker.TaskWorker)
        worker.execute(task_id, payload)
        return task_id

    @operation
    @override
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome string for a task."""
        # WHEN queue is unavailable, MUST raise QueueUnavailableException.
        if not self._is_available:
            raise task_queue.QueueUnavailableException
        # WHEN queue is available, MUST record outcome for task_id.
        self._outcomes[task_id] = outcome

    @operation
    @override
    def get_outcome(self, task_id: str) -> Optional[str]:
        """Retrieves the recorded outcome for a task."""
        # WHEN task_id has no recorded outcome, MUST return None (dict.get default).
        return self._outcomes.get(task_id)

    @operation
    @override
    def clear(self) -> None:
        """Purges all pending tasks and recorded outcomes from the queue."""
        # MUST purge all pending tasks and reset pending_count to 0.
        self._queue.clear()
        # MUST purge all recorded task outcomes.
        self._outcomes.clear()
        assert self.pending_count == 0

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
# LAST_CLEANED: 2026-11-04T18:53:14Z
# LAST_CHANGED: 2026-11-04T18:38:36Z
# CHANGE: Implement bounded FIFO TaskQueue singleton: capacity 10 deque backing, outcomes map, availability toggle; enforce unavailable/empty/full postconditions, dispatch delegates to TaskWorker.execute, clear purges state; keep auto-generated __initialize__ intact.
# COVERAGE_AUDIT: 2026-11-04T18:53:14Z
# QA_AUDIT: 2026-11-04T18:53:02Z
# --- END AUTOFAB METADATA ---


# === File: task_worker.py ===
"""Low-level interface specification for task worker."""

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
# LAST_CLEANED: 2026-11-04T18:38:17Z
# LAST_CHANGED: 2026-11-04T18:38:17Z
# CHANGE: Implement task worker interface protocol: WorkerError/WorkerExecutionException data types and TaskWorker Protocol with execute, fetch_and_execute, set_failing_task; package-qualified pretense imports and framework decorators per guide.
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl.py ===
"""Low-level implementation specification for task execution worker."""

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
    """Concrete realization of task worker with payload transformation and execution telemetry.

    GROUNDING:
    - Realizes task execution worker coordinating with task_queue.TaskQueue.
    - Initializes _processed_count to 0, _last_task_id to None, _is_busy to False, and _failing_tasks to set().
    - Transforms string payload to uppercase outcome with 'PROCESSED:' prefix.
    """

    tier = system

    def __init__(self) -> None:
        # Backing state for execution telemetry and simulated failure configuration.
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
        # Mark the worker busy for the duration of the execution attempt.
        self._is_busy = True
        # WHEN execution fails (designated failing task), MUST raise WorkerExecutionException.
        if task_id in self._failing_tasks:
            self._is_busy = False
            raise task_worker.WorkerExecutionException
        # WHEN execution succeeds, MUST compute the transformed outcome string.
        outcome = f"PROCESSED:{payload.upper()}"
        queue = get_singleton(task_queue.TaskQueue)
        try:
            queue.complete(task_id, outcome)
        except task_queue.QueueUnavailableException as exc:
            # WHEN task queue is unavailable, MUST raise WorkerExecutionException.
            self._is_busy = False
            raise task_worker.WorkerExecutionException from exc
        # Record telemetry only after the collaborator accepted the completion.
        self._last_task_id = task_id
        self._processed_count += 1
        self._is_busy = False
        return outcome

    @operation
    @override
    def fetch_and_execute(self) -> str:
        """Fetches the next pending task from the task queue singleton and executes it."""
        queue = get_singleton(task_queue.TaskQueue)
        processed_before = self._processed_count
        try:
            # The queue pops the oldest pending task and returns its identifier.
            task_id = queue.dispatch()
        except task_queue.QueueEmptyError as exc:
            # WHEN collaborator task queue has zero pending tasks, MUST raise WorkerError.
            raise task_worker.WorkerError from exc
        except task_queue.QueueUnavailableException as exc:
            # WHEN collaborator task queue is unavailable, MUST raise WorkerExecutionException.
            raise task_worker.WorkerExecutionException from exc
        # WHEN collaborator dispatch succeeds, MUST execute the dispatched task and
        # return the task identifier. A concrete queue may already forward the popped
        # payload into execute(); only execute here when dispatch merely returned the id
        # (so the dispatched task is never left unprocessed or processed twice).
        if self._processed_count == processed_before:
            self.execute(task_id, "")
        # WHEN dispatch succeeds, MUST return the dispatched task identifier.
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
# LAST_CLEANED: 2026-11-04T18:53:17Z
# LAST_CHANGED: 2026-11-04T18:43:26Z
# CHANGE: Fix fetch_and_execute: after a successful queue.dispatch() the worker now invokes self.execute(task_id, ...) so the dispatched task is processed, queue.complete is notified, and processed_count/last_task_id telemetry updates; execute is skipped only when the collaborator dispatch already forwarded the task into this worker's execute (avoids double processing).
# COVERAGE_AUDIT: 2026-11-04T18:53:17Z
# QA_AUDIT: 2026-11-04T18:53:03Z
# --- END AUTOFAB METADATA ---
