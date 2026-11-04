# === File: task_queue_impl_test.py ===
"""Unit tests for the concrete bounded task queue singleton.

The tests resolve the ``TaskQueue`` system singleton from an isolated
``LifecycleRegistry`` and exercise its contracted invariants and
postconditions from ``low/task_queue.pyi`` and ``low/task_queue_impl.pyi``.
A recording double supplies the ``TaskWorker`` collaborator protocol.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Any, List, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

_PART_DIR = Path(__file__).resolve().parents[1]
_LIB_DIR = _PART_DIR / "lib"
if str(_PART_DIR.parent) not in sys.path:
    sys.path.append(str(_PART_DIR.parent))
if str(_PART_DIR) not in sys.path:
    sys.path.append(str(_PART_DIR))
if str(_LIB_DIR) not in sys.path:
    sys.path.append(str(_LIB_DIR))


def _load_implementation(module_name: str) -> Any:
    """Resolve the woven implementation module despite spec-level name shadowing.

    The verification harness exposes the low-level specification modules under
    the top-level ``task_queue`` and ``task_worker`` names, which shadows the
    package-qualified ``task_queue.lib`` path.  The implementation module is
    therefore resolved from whichever namespace actually provides it.
    """
    candidates = (
        _PART_DIR.name + ".lib." + module_name,
        module_name,
        "lib." + module_name,
    )
    for candidate in candidates:
        try:
            return importlib.import_module(candidate)
        except ImportError:
            continue
    spec = importlib.util.spec_from_file_location(
        "_autofab_" + module_name, _LIB_DIR / (module_name + ".py")
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot resolve implementation module " + module_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _collaborator_module(implementation: Any, name: str) -> Any:
    """Return the interface module the implementation bound for a collaborator."""
    try:
        bound = (
            implementation.task_queue
            if name == "task_queue"
            else implementation.task_worker
        )
    except AttributeError:
        bound = None
    if bound is not None:
        return bound
    return importlib.import_module(name)


_IMPLEMENTATION = _load_implementation("task_queue_impl")
_QUEUE_INTERFACE = _collaborator_module(_IMPLEMENTATION, "task_queue")
_WORKER_INTERFACE = _collaborator_module(_IMPLEMENTATION, "task_worker")

QueueFullError = _IMPLEMENTATION.QueueFullError
TaskQueue = _IMPLEMENTATION.TaskQueue
__initialize__ = _IMPLEMENTATION.__initialize__
QueueError = _QUEUE_INTERFACE.QueueError
QueueUnavailableException = _QUEUE_INTERFACE.QueueUnavailableException
TaskWorker = _WORKER_INTERFACE.TaskWorker


class RecordingTaskWorker:
    """Lightweight collaborator double implementing the ``TaskWorker`` protocol."""

    def __init__(self) -> None:
        self.executed: List[Tuple[str, str]] = []

    def execute(self, task_id: str, payload: str) -> str:
        self.executed.append((task_id, payload))
        return "PROCESSED:" + payload.upper()

    def fetch_and_execute(self) -> str:
        return ""

    def set_failing_task(self, task_id: str, failing: bool = True) -> None:
        return None


class TaskQueueImplTest(unittest.TestCase):
    """Verifies the bounded FIFO task queue contract."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.worker = RecordingTaskWorker()
        self.registry.register_instance(self.worker, keys=[TaskWorker], tier=system)

    def test_capacity_and_initial_state(self) -> None:
        """INVARIANTS: capacity 10, empty, not full, available, pending_count 0."""
        self.assertTrue(issubclass(QueueFullError, QueueError))
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            self.assertEqual(10, queue.capacity)
            self.assertTrue(queue.is_empty)
            self.assertFalse(queue.is_full)
            self.assertTrue(queue.is_available)
            self.assertEqual(0, queue.pending_count)

    def test_submit_appends_and_increments_pending(self) -> None:
        """POSTCONDITIONS: WHEN available, submit appends to tail and grows count."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.submit("t1", "alpha")
            self.assertEqual(1, queue.pending_count)
            self.assertFalse(queue.is_empty)
            self.assertFalse(queue.is_full)
            queue.submit("t2", "beta")
            self.assertEqual(2, queue.pending_count)

    def test_submit_to_capacity_marks_queue_full(self) -> None:
        """INVARIANTS: is_full holds when pending_count reaches capacity."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            for index in range(queue.capacity):
                queue.submit("t" + str(index), "payload" + str(index))
            self.assertEqual(queue.capacity, queue.pending_count)
            self.assertTrue(queue.is_full)
            self.assertFalse(queue.is_empty)

    def test_dispatch_pops_oldest_and_invokes_worker(self) -> None:
        """POSTCONDITIONS: dispatch pops the oldest task and returns its identifier."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.submit("t1", "alpha")
            queue.submit("t2", "beta")
            self.assertEqual("t1", queue.dispatch())
            self.assertEqual([("t1", "alpha")], self.worker.executed)
            self.assertEqual(1, queue.pending_count)
            self.assertEqual("t2", queue.dispatch())
            self.assertEqual([("t1", "alpha"), ("t2", "beta")], self.worker.executed)
            self.assertEqual(0, queue.pending_count)
            self.assertTrue(queue.is_empty)

    def test_complete_records_outcome_and_get_outcome_reads_it(self) -> None:
        """POSTCONDITIONS: complete records outcome; get_outcome returns it or None."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            self.assertIsNone(queue.get_outcome("t1"))
            queue.complete("t1", "PROCESSED:ALPHA")
            self.assertEqual("PROCESSED:ALPHA", queue.get_outcome("t1"))
            queue.complete("t1", "PROCESSED:ALPHA2")
            self.assertEqual("PROCESSED:ALPHA2", queue.get_outcome("t1"))
            self.assertIsNone(queue.get_outcome("t2"))

    def test_clear_purges_tasks_and_outcomes(self) -> None:
        """POSTCONDITIONS: clear purges pending tasks and recorded outcomes."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.submit("t1", "alpha")
            queue.submit("t2", "beta")
            queue.complete("t1", "done")
            queue.clear()
            self.assertEqual(0, queue.pending_count)
            self.assertTrue(queue.is_empty)
            self.assertIsNone(queue.get_outcome("t1"))

    def test_unavailable_queue_rejects_operations(self) -> None:
        """POSTCONDITIONS: WHEN unavailable, submit/dispatch/complete raise."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.set_available(False)
            self.assertFalse(queue.is_available)
            with self.assertRaises(QueueUnavailableException):
                queue.submit("t1", "alpha")
            with self.assertRaises(QueueUnavailableException):
                queue.dispatch()
            with self.assertRaises(QueueUnavailableException):
                queue.complete("t1", "done")
            self.assertEqual(0, queue.pending_count)
            self.assertEqual([], self.worker.executed)

    def test_available_queue_recovers_after_unavailability(self) -> None:
        """POSTCONDITIONS: WHEN available again, operations succeed normally."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.set_available(False)
            queue.set_available(True)
            self.assertTrue(queue.is_available)
            queue.submit("t1", "alpha")
            self.assertEqual(1, queue.pending_count)
            self.assertEqual("t1", queue.dispatch())
            self.assertEqual([("t1", "alpha")], self.worker.executed)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T18:53:14Z
# LAST_CHANGED: 2026-11-04T18:52:34Z
# CHANGE: Resolve the TaskQueue implementation through a shadow-safe namespace loader instead of the package-qualified task_queue.lib path that the harness shadows with the top-level task_queue specification module. The loader reuses the implementation module the harness already exposes (canonical, top-level, or lib-rooted) and derives the TaskWorker collaborator interface from that module, so class identity matches at runtime. Contract coverage unchanged: capacity 10, empty/full/available, pending_count, submit growth, FIFO dispatch invoking the worker, complete/get_outcome, clear purging, and QueueUnavailableException branches.
# COVERAGE_AUDIT: 2026-11-04T18:53:14Z
# QA_AUDIT: 2026-11-04T18:53:02Z
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl_test.py ===
"""Unit tests for the concrete task worker singleton.

The tests resolve the ``TaskWorker`` system singleton from an isolated
``LifecycleRegistry`` and exercise its contracted invariants and
postconditions from ``low/task_worker.pyi`` and ``low/task_worker_impl.pyi``.
A recording double supplies the ``TaskQueue`` collaborator protocol.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Any, List, Optional, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

_PART_DIR = Path(__file__).resolve().parents[1]
_LIB_DIR = _PART_DIR / "lib"
if str(_PART_DIR.parent) not in sys.path:
    sys.path.append(str(_PART_DIR.parent))
if str(_PART_DIR) not in sys.path:
    sys.path.append(str(_PART_DIR))
if str(_LIB_DIR) not in sys.path:
    sys.path.append(str(_LIB_DIR))


def _load_implementation(module_name: str) -> Any:
    """Resolve the woven implementation module despite spec-level name shadowing.

    The verification harness exposes the low-level specification modules under
    the top-level ``task_queue`` and ``task_worker`` names, which shadows the
    package-qualified ``task_queue.lib`` path.  The implementation module is
    therefore resolved from whichever namespace actually provides it.
    """
    candidates = (
        _PART_DIR.name + ".lib." + module_name,
        module_name,
        "lib." + module_name,
    )
    for candidate in candidates:
        try:
            return importlib.import_module(candidate)
        except ImportError:
            continue
    spec = importlib.util.spec_from_file_location(
        "_autofab_" + module_name, _LIB_DIR / (module_name + ".py")
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot resolve implementation module " + module_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _collaborator_module(implementation: Any, name: str) -> Any:
    """Return the interface module the implementation bound for a collaborator."""
    try:
        bound = (
            implementation.task_queue
            if name == "task_queue"
            else implementation.task_worker
        )
    except AttributeError:
        bound = None
    if bound is not None:
        return bound
    return importlib.import_module(name)


_IMPLEMENTATION = _load_implementation("task_worker_impl")
_QUEUE_INTERFACE = _collaborator_module(_IMPLEMENTATION, "task_queue")
_WORKER_INTERFACE = _collaborator_module(_IMPLEMENTATION, "task_worker")

TaskWorker = _IMPLEMENTATION.TaskWorker
__initialize__ = _IMPLEMENTATION.__initialize__
QueueUnavailableException = _QUEUE_INTERFACE.QueueUnavailableException
TaskQueue = _QUEUE_INTERFACE.TaskQueue
WorkerExecutionException = _WORKER_INTERFACE.WorkerExecutionException


class RecordingTaskQueue:
    """Lightweight collaborator double implementing the ``TaskQueue`` protocol."""

    def __init__(self) -> None:
        self.pending: List[Tuple[str, str]] = []
        self.completions: List[Tuple[str, str]] = []
        self.dispatch_calls: int = 0
        self.dispatch_unavailable: bool = False
        self.complete_unavailable: bool = False

    @property
    def pending_count(self) -> int:
        return len(self.pending)

    def submit(self, task_id: str, payload: str) -> None:
        self.pending.append((task_id, payload))

    def dispatch(self) -> str:
        self.dispatch_calls += 1
        if self.dispatch_unavailable:
            raise QueueUnavailableException("task queue is unavailable")
        task_id, _payload = self.pending.pop(0)
        return task_id

    def complete(self, task_id: str, outcome: str) -> None:
        if self.complete_unavailable:
            raise QueueUnavailableException("task queue is unavailable")
        self.completions.append((task_id, outcome))

    def get_outcome(self, task_id: str) -> Optional[str]:
        for recorded_id, outcome in self.completions:
            if recorded_id == task_id:
                return outcome
        return None

    def clear(self) -> None:
        self.pending.clear()
        self.completions.clear()

    def set_available(self, available: bool) -> None:
        self.dispatch_unavailable = not available
        self.complete_unavailable = not available


class TaskWorkerImplTest(unittest.TestCase):
    """Verifies the task worker execution contract."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.queue = RecordingTaskQueue()
        self.registry.register_instance(self.queue, keys=[TaskQueue], tier=system)

    def test_initial_telemetry_state(self) -> None:
        """INVARIANTS: fresh worker reports zero processed and no last task."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            self.assertEqual(0, worker.processed_count)
            self.assertIsNone(worker.last_task_id)
            self.assertFalse(worker.is_busy)

    def test_execute_transforms_payload_and_reports_completion(self) -> None:
        """POSTCONDITIONS: execute notifies the queue and records telemetry."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            outcome = worker.execute("t1", "alpha")
            self.assertEqual("PROCESSED:ALPHA", outcome)
            self.assertEqual([("t1", "PROCESSED:ALPHA")], self.queue.completions)
            self.assertEqual(1, worker.processed_count)
            self.assertEqual("t1", worker.last_task_id)
            self.assertFalse(worker.is_busy)
            self.assertEqual("PROCESSED:ALPHA", self.queue.get_outcome("t1"))

    def test_execute_failing_task_raises_execution_exception(self) -> None:
        """POSTCONDITIONS: WHEN task fails, MUST raise WorkerExecutionException."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            worker.set_failing_task("bad")
            with self.assertRaises(WorkerExecutionException):
                worker.execute("bad", "gamma")
            self.assertEqual([], self.queue.completions)
            self.assertEqual(0, worker.processed_count)
            self.assertIsNone(worker.last_task_id)
            self.assertFalse(worker.is_busy)

    def test_execute_recovers_after_failing_task_is_cleared(self) -> None:
        """POSTCONDITIONS: WHEN failure is cleared, execution succeeds again."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            worker.set_failing_task("bad")
            worker.set_failing_task("bad", False)
            self.assertEqual("PROCESSED:DELTA", worker.execute("bad", "delta"))
            self.assertEqual([("bad", "PROCESSED:DELTA")], self.queue.completions)
            self.assertEqual(1, worker.processed_count)
            self.assertEqual("bad", worker.last_task_id)

    def test_execute_on_unavailable_queue_raises_execution_exception(self) -> None:
        """POSTCONDITIONS: WHEN queue is unavailable, MUST raise WorkerExecutionException."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            self.queue.complete_unavailable = True
            with self.assertRaises(WorkerExecutionException):
                worker.execute("t1", "alpha")
            self.assertEqual([], self.queue.completions)
            self.assertEqual(0, worker.processed_count)
            self.assertIsNone(worker.last_task_id)
            self.assertFalse(worker.is_busy)

    def test_fetch_and_execute_dispatches_oldest_task(self) -> None:
        """POSTCONDITIONS: WHEN dispatch succeeds, MUST execute and return task id."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            self.queue.submit("t1", "alpha")
            self.queue.submit("t2", "beta")
            dispatched = worker.fetch_and_execute()
            self.assertEqual("t1", dispatched)
            self.assertEqual(1, self.queue.dispatch_calls)
            self.assertEqual(1, self.queue.pending_count)
            self.assertEqual(1, len(self.queue.completions))
            completed_id, outcome = self.queue.completions[0]
            self.assertEqual("t1", completed_id)
            self.assertTrue(outcome.startswith("PROCESSED:"))
            self.assertEqual(1, worker.processed_count)
            self.assertEqual("t1", worker.last_task_id)
            self.assertFalse(worker.is_busy)

    def test_fetch_and_execute_on_unavailable_queue_raises(self) -> None:
        """POSTCONDITIONS: WHEN queue is unavailable, MUST raise WorkerExecutionException."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            self.queue.dispatch_unavailable = True
            with self.assertRaises(WorkerExecutionException):
                worker.fetch_and_execute()
            self.assertEqual(1, self.queue.dispatch_calls)
            self.assertEqual([], self.queue.completions)
            self.assertEqual(0, worker.processed_count)
            self.assertFalse(worker.is_busy)

    def test_reset_clears_telemetry(self) -> None:
        """POSTCONDITIONS: reset restores zeroed telemetry and idle state."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            worker.execute("t1", "alpha")
            worker.reset()
            self.assertEqual(0, worker.processed_count)
            self.assertIsNone(worker.last_task_id)
            self.assertFalse(worker.is_busy)
            self.assertEqual("PROCESSED:BETA", worker.execute("t2", "beta"))
            self.assertEqual(1, worker.processed_count)
            self.assertEqual("t2", worker.last_task_id)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T18:53:17Z
# LAST_CHANGED: 2026-11-04T18:52:39Z
# CHANGE: Resolve the TaskWorker implementation through a shadow-safe namespace loader instead of the package-qualified task_queue.lib path that the harness shadows with the top-level task_queue/task_worker specification modules. The loader reuses the exposed implementation module and derives the TaskQueue collaborator interface plus WorkerExecutionException from that module, so mocks, singleton keys, and exception identity match the implementation at runtime. Contract coverage unchanged: execute payload transformation and completion reporting, failing-task and unavailable-queue WorkerExecutionException branches, fetch_and_execute dispatch wiring, and processed_count/last_task_id/is_busy/reset telemetry.
# COVERAGE_AUDIT: 2026-11-04T18:53:17Z
# QA_AUDIT: 2026-11-04T18:53:03Z
# --- END AUTOFAB METADATA ---
