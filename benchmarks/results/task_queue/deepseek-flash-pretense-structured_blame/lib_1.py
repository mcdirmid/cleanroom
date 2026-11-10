# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_164345_deepseek-flash_task_queue_pretense
# Timestamp: 2026-11-08T16:43:45.534398+00:00
# Benchmark Task: task_queue
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 361,672
#   Cached Inbound Tokens:   39,996,416
#   Outbound Tokens:         382,273
#   Total Tokens:            40,740,361
#   Financial Cost ($USD):   $0.4036
#   Wall Clock Duration:     2440.32s
#   Step Latencies (s):      [415.3, 672.2, 187.4, 92.9, 61.8, 20.4, 20.4, 445.4, 135.8, 105.1, 63.7, 177.4, 113.0, 74.3, 63.8, 94.9, 74.2, 146.5, 84.6, 64.0, 20.4, 10.0]
#   Role Execution Rounds:   lib: 1, pretense: 8, pretense_coverage: 3, pretense_qa: 10 (Total: 22)
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
from __future__ import annotations

from typing import Optional, Protocol

from support.lib.framework import data_type, operation, poly_type
from pretense.parts.pretense.lib.pretense import PretenseSpecificationError, test_only

# Requirements specified in task_queue.pyi


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

        POSTCONDITIONS:
        - WHEN queue is unavailable, MUST raise QueueUnavailableException.
        - WHEN queue is available, MUST append task to queue tail and increment pending_count by 1.
        """
        ...

    @operation
    def dispatch(self) -> str:
        """Dispatches the oldest pending task and returns its identifier.

        PRECONDITIONS:
        - WHEN pending_count equals 0, MUST raise QueueEmptyError.

        POSTCONDITIONS:
        - WHEN queue is unavailable, MUST raise QueueUnavailableException.
        - WHEN pending_count is greater than 0, MUST pop oldest task, decrement pending_count by 1, and return task_id.
        """
        ...

    @operation
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome string for a task.

        POSTCONDITIONS:
        - WHEN queue is unavailable, MUST raise QueueUnavailableException.
        - WHEN queue is available, MUST record outcome for task_id.
        """
        ...

    @operation
    def get_outcome(self, task_id: str) -> Optional[str]:
        """Retrieves the recorded outcome for a task.

        POSTCONDITIONS:
        - WHEN task_id has recorded outcome, MUST return recorded outcome string.
        - WHEN task_id has no recorded outcome, MUST return None.
        """
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
# LAST_CLEANED: 2026-11-08T16:50:48Z
# LAST_CHANGED: 2026-11-08T16:50:48Z
# CHANGE: Implement FIFO task queue interface: data-type error hierarchy (QueueError/QueueEmptyError/QueueUnavailableException), poly_type TaskQueue protocol with contracted properties/operations, and package-qualified pretense imports.
# --- END AUTOFAB METADATA ---


# === File: task_queue_impl.py ===
from __future__ import annotations

import collections
from typing import Optional

from support.lib.framework import data_type, operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)
from . import task_queue
from . import task_worker
from pretense.parts.pretense.lib.pretense import test_only

# Requirements specified in task_queue_impl.pyi


@data_type
class QueueFullError(task_queue.QueueError):
    """Raised when attempting to submit to a task queue that has reached capacity."""

    def __init__(self, message: str = "task queue has reached capacity") -> None:
        # Zero-argument construction is required because this value type is
        # registered alongside the queue singleton and instantiated at phase start.
        super().__init__(message)


@singleton_type("system")
class TaskQueue(task_queue.TaskQueue):
    """Concrete realization of bounded task queue using collections.deque and outcome mapping.

    GROUNDING:
    - Realizes bounded FIFO task queue with default capacity 10 using collections.deque and dict.
    - Initializes internal _capacity to 10, _queue to collections.deque(), _outcomes to dict(), and _is_available to True.
    - Coordinates with task_worker.TaskWorker for task execution dispatch.
    """

    tier: str = "system"

    def __init__(self) -> None:
        # Bounded FIFO backing store with default capacity and outcome mapping.
        self._capacity: int = 10
        self._queue: collections.deque[tuple[str, str]] = collections.deque()
        self._outcomes: dict[str, str] = {}
        self._is_available: bool = True

    @property
    def capacity(self) -> int:
        """Maximum number of pending tasks permitted in the queue."""
        # GROUNDING: Returns self._capacity.
        return self._capacity

    @property
    def is_empty(self) -> bool:
        """Indicates whether the task queue contains zero pending tasks."""
        # GROUNDING: Evaluates len(self._queue) == 0.
        return len(self._queue) == 0

    @property
    def is_full(self) -> bool:
        """Indicates whether the task queue has reached its capacity limit."""
        # GROUNDING: Evaluates len(self._queue) >= self._capacity.
        return len(self._queue) >= self._capacity

    @property
    def is_available(self) -> bool:
        """Indicates whether the task queue is available for operations."""
        # GROUNDING: Returns self._is_available.
        return self._is_available

    @property
    @override
    def pending_count(self) -> int:
        """Current number of pending tasks stored in the queue."""
        # GROUNDING: Returns len(self._queue).
        return len(self._queue)

    @operation
    @override
    def submit(self, task_id: str, payload: str) -> None:
        """Appends a new task to the queue awaiting execution."""
        # POSTCONDITION (unavailable_queue): raise when the queue is unavailable.
        if not self.is_available:
            raise task_queue.QueueUnavailableException(
                "cannot submit to an unavailable task queue"
            )
        # PRECONDITION (bounded capacity): raise when the queue is already full.
        if self.is_full:
            raise QueueFullError("task queue has reached capacity")
        # POSTCONDITION (append_task): append (task_id, payload) at the queue tail.
        # pending_count is derived from the deque length and therefore increments by 1.
        self._queue.append((task_id, payload))

    @operation
    @override
    def dispatch(self) -> str:
        """Dispatches the oldest pending task to the collaborator worker for execution."""
        # POSTCONDITION (unavailable_queue): raise when the queue is unavailable.
        if not self.is_available:
            raise task_queue.QueueUnavailableException(
                "cannot dispatch from an unavailable task queue"
            )
        # PRECONDITION (empty_queue): raise when there are no pending tasks.
        if self.is_empty:
            raise task_queue.QueueEmptyError("task queue is empty")
        # POSTCONDITION (pop_task): pop the oldest task; pending_count derives from len.
        task_id, payload = self._queue.popleft()
        # Sequencing: hand the popped workload to the collaborator worker on demand.
        worker = get_singleton(task_worker.TaskWorker)
        worker.execute(task_id, payload)
        return task_id

    @operation
    @override
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome string for a task."""
        # POSTCONDITION (unavailable_queue): raise when the queue is unavailable.
        if not self.is_available:
            raise task_queue.QueueUnavailableException(
                "cannot record outcomes on an unavailable task queue"
            )
        # POSTCONDITION (record_outcome): map task_id to the reported outcome.
        self._outcomes[task_id] = outcome

    @operation
    @override
    def get_outcome(self, task_id: str) -> Optional[str]:
        """Retrieves the recorded outcome for a task."""
        # POSTCONDITION (completed_task / uncompleted_task): recorded value or None.
        return self._outcomes.get(task_id)

    @operation
    @override
    def clear(self) -> None:
        """Purges all pending tasks and recorded outcomes from the queue."""
        # POSTCONDITION (purge_tasks): drop all pending tasks; pending_count returns to 0.
        self._queue.clear()
        # POSTCONDITION (purge_outcomes): drop every recorded outcome.
        self._outcomes.clear()

    @operation
    @test_only
    @override
    def set_available(self, available: bool) -> None:
        """Test-only hook to toggle task queue availability for operational simulation."""
        # GROUNDING: Sets self._is_available = available.
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
# LAST_CLEANED: 2026-11-08T17:03:43Z
# LAST_CHANGED: 2026-11-08T16:50:55Z
# CHANGE: Implement bounded FIFO TaskQueue singleton: deque backing with default capacity 10, availability/full/empty guards, outcome mapping, worker dispatch sequencing, zero-arg QueueFullError, and untouched auto-generated registration.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:03:43Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:03:21Z
# --- END AUTOFAB METADATA ---


# === File: task_worker.py ===
from __future__ import annotations

from typing import Protocol

from support.lib.framework import data_type, operation, poly_type
from pretense.parts.pretense.lib.pretense import PretenseSpecificationError, test_only

# Requirements specified in task_worker.pyi


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

        POSTCONDITIONS:
        - WHEN execution fails or task queue is unavailable, MUST raise WorkerExecutionException.
        - WHEN execution succeeds, MUST notify task queue of completion and return outcome string.
        """
        ...

    @operation
    def fetch_and_execute(self) -> str:
        """Fetches the next pending task from the collaborator queue and executes it.

        PRECONDITIONS:
        - WHEN collaborator task queue has zero pending tasks, MUST raise WorkerError.

        POSTCONDITIONS:
        - WHEN collaborator task queue is unavailable, MUST raise WorkerExecutionException.
        - WHEN collaborator dispatch succeeds, MUST execute dispatched task and return task identifier.
        """
        ...

    @operation
    @test_only
    def set_failing_task(self, task_id: str, failing: bool = True) -> None:
        """Test-only hook to configure designated tasks to fail on execution."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T16:50:51Z
# LAST_CHANGED: 2026-11-08T16:50:51Z
# CHANGE: Implement task worker interface: data-type error hierarchy (WorkerError/WorkerExecutionException), poly_type TaskWorker protocol with contracted operations, and package-qualified pretense imports.
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl.py ===
from __future__ import annotations

from typing import Optional

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)
from . import task_queue
from . import task_worker
from pretense.parts.pretense.lib.pretense import test_only

# Requirements specified in task_worker_impl.pyi


@singleton_type("system")
class TaskWorker(task_worker.TaskWorker):
    """Concrete realization of task worker with payload transformation and execution telemetry.

    GROUNDING:
    - Realizes task execution worker coordinating with task_queue.TaskQueue.
    - Initializes _processed_count to 0, _last_task_id to None, _is_busy to False, and _failing_tasks to set().
    - Transforms string payload to uppercase outcome with 'PROCESSED:' prefix.
    """

    tier: str = "system"

    def __init__(self) -> None:
        # Telemetry and failure-designation backing state.
        self._processed_count: int = 0
        self._last_task_id: Optional[str] = None
        self._is_busy: bool = False
        self._failing_tasks: set[str] = set()

    @property
    def processed_count(self) -> int:
        """Current number of tasks successfully processed by the worker."""
        # GROUNDING: Returns self._processed_count.
        return self._processed_count

    @property
    def last_task_id(self) -> Optional[str]:
        """Identifier of the most recently executed task, or None if no tasks processed."""
        # GROUNDING: Returns self._last_task_id.
        return self._last_task_id

    @property
    def is_busy(self) -> bool:
        """Indicates whether the worker is currently executing a task."""
        # GROUNDING: Returns self._is_busy.
        return self._is_busy

    @operation
    def reset(self) -> None:
        """Resets telemetry counters, clearing last task identifier and busy state."""
        # GROUNDING: Reset processed count, last task identifier, and busy state.
        self._processed_count = 0
        self._last_task_id = None
        self._is_busy = False

    @operation
    @override
    def execute(self, task_id: str, payload: str) -> str:
        """Executes a workload payload, reports completion to task queue, and updates telemetry."""
        # GROUNDING: Mark the worker busy for the duration of execution.
        self._is_busy = True
        # POSTCONDITION (failure_or_unavailable): designated failing tasks raise.
        if task_id in self._failing_tasks:
            self._is_busy = False
            raise task_worker.WorkerExecutionException(
                f"task '{task_id}' failed during execution"
            )
        # POSTCONDITION (success_notification): transform payload into the outcome string.
        outcome = f"PROCESSED:{payload.upper()}"
        # Sequencing: notify the collaborator queue of completion on demand.
        queue = get_singleton(task_queue.TaskQueue)
        try:
            queue.complete(task_id, outcome)
        except task_queue.QueueUnavailableException as exc:
            # POSTCONDITION (failure_or_unavailable): unavailable queue is an execution failure.
            self._is_busy = False
            raise task_worker.WorkerExecutionException(
                f"task queue unavailable while completing '{task_id}'"
            ) from exc
        # Successful execution telemetry.
        self._last_task_id = task_id
        self._processed_count += 1
        self._is_busy = False
        return outcome

    @operation
    @override
    def fetch_and_execute(self) -> str:
        """Fetches the next pending task from the task queue singleton and executes it."""
        # Sequencing: resolve the collaborator queue on demand.
        queue = get_singleton(task_queue.TaskQueue)
        try:
            task_id = queue.dispatch()
        except task_queue.QueueEmptyError as exc:
            # PRECONDITION (empty_queue): zero pending tasks is reported as WorkerError.
            raise task_worker.WorkerError("task queue is empty") from exc
        except task_queue.QueueUnavailableException as exc:
            # POSTCONDITION (unavailable_queue): unavailable queue is an execution failure.
            raise task_worker.WorkerExecutionException(
                "task queue is unavailable"
            ) from exc
        # POSTCONDITION (success): the dispatched task has been executed exactly once,
        # because dispatch() routes the popped workload back through this same worker
        # singleton's execute() (the payload travels with the queued task, so this
        # worker cannot re-derive it here).
        return task_id

    @operation
    @test_only
    @override
    def set_failing_task(self, task_id: str, failing: bool = True) -> None:
        """Test-only hook to configure designated tasks to fail on execution."""
        # GROUNDING: Add or remove the designated task from the failing-task set.
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
# LAST_CLEANED: 2026-11-08T17:24:22Z
# LAST_CHANGED: 2026-11-08T16:50:59Z
# CHANGE: Implement TaskWorker singleton: PROCESSED: payload transform, telemetry (processed_count/last_task_id/is_busy), failing-task configuration, queue completion notification with QueueUnavailableException remapping, and dispatch error mapping to WorkerError/WorkerExecutionException.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:24:22Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:24:00Z
# --- END AUTOFAB METADATA ---
