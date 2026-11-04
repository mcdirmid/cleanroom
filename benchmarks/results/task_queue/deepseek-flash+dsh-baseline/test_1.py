# === File: task_queue_impl_test.py ===
"""Unit tests for task_queue_impl per its grounding specification."""

from __future__ import annotations

import os
import sys
import unittest
from typing import List, Tuple

_PARTS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, _PARTS_ROOT)
sys.modules.pop("task_queue", None)
sys.modules.pop("task_queue.lib", None)

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from task_queue.lib.task_queue import (
    QueueUnavailableException,
)
from task_queue.lib.task_queue_impl import (
    TaskQueue,
    __initialize__,
)
from task_queue.lib.task_worker import TaskWorker


class MockTaskWorker:
    """Collaborator double recording the tasks handed off by the queue."""

    def __init__(self) -> None:
        self.executions: List[Tuple[str, str]] = []

    def execute(self, task_id: str, payload: str) -> str:
        self.executions.append((task_id, payload))
        return f"PROCESSED:{payload.upper()}"

    def fetch_and_execute(self) -> str:
        return ""

    def set_failing_task(self, task_id: str, failing: bool = True) -> None:
        pass


class TaskQueueImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.worker = MockTaskWorker()
        self.registry.register_instance(self.worker, keys=[TaskWorker], tier=system)

    def test_initial_state_exposes_contracted_defaults(self) -> None:
        """Happy path: a fresh queue is empty, available, and bounded at capacity ten."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            self.assertEqual(queue.pending_count, 0)
            self.assertEqual(queue.capacity, 10)
            self.assertTrue(queue.is_empty)
            self.assertFalse(queue.is_full)
            self.assertTrue(queue.is_available)

    def test_submit_appends_task_and_increments_count(self) -> None:
        """POSTCONDITION: available submit appends to the tail and grows pending_count."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.submit("task-1", "alpha")
            self.assertEqual(queue.pending_count, 1)
            self.assertFalse(queue.is_empty)
            queue.submit("task-2", "beta")
            self.assertEqual(queue.pending_count, 2)

    def test_dispatch_pops_oldest_task_and_delegates_to_worker(self) -> None:
        """POSTCONDITION: dispatch pops the oldest task, executes it, and returns its id."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.submit("task-1", "alpha")
            queue.submit("task-2", "beta")
            dispatched = queue.dispatch()
            self.assertEqual(dispatched, "task-1")
            self.assertEqual(self.worker.executions, [("task-1", "alpha")])
            self.assertEqual(queue.pending_count, 1)

    def test_complete_records_outcome(self) -> None:
        """POSTCONDITION: completed tasks expose their recorded outcome, unknown ids give None."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.submit("task-1", "alpha")
            queue.complete("task-1", "PROCESSED:ALPHA")
            self.assertEqual(queue.get_outcome("task-1"), "PROCESSED:ALPHA")
            self.assertIsNone(queue.get_outcome("task-2"))

    def test_clear_purges_pending_tasks_and_outcomes(self) -> None:
        """POSTCONDITION: clear removes every pending task and every recorded outcome."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.submit("task-1", "alpha")
            queue.complete("task-1", "PROCESSED:ALPHA")
            queue.clear()
            self.assertEqual(queue.pending_count, 0)
            self.assertTrue(queue.is_empty)
            self.assertIsNone(queue.get_outcome("task-1"))

    def test_queue_reports_full_at_capacity(self) -> None:
        """INVARIANT: the queue reports fullness once pending count reaches capacity."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            for index in range(10):
                queue.submit(f"task-{index}", f"payload-{index}")
            self.assertEqual(queue.pending_count, 10)
            self.assertTrue(queue.is_full)

    def test_unavailable_queue_rejects_submit(self) -> None:
        """POSTCONDITION: submit on an unavailable queue raises QueueUnavailableException."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.set_available(False)
            self.assertFalse(queue.is_available)
            with self.assertRaises(QueueUnavailableException):
                queue.submit("task-1", "alpha")

    def test_unavailable_queue_rejects_dispatch(self) -> None:
        """POSTCONDITION: dispatch on an unavailable queue raises QueueUnavailableException."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.submit("task-1", "alpha")
            queue.set_available(False)
            with self.assertRaises(QueueUnavailableException):
                queue.dispatch()

    def test_unavailable_queue_rejects_complete(self) -> None:
        """POSTCONDITION: complete on an unavailable queue raises QueueUnavailableException."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.set_available(False)
            with self.assertRaises(QueueUnavailableException):
                queue.complete("task-1", "PROCESSED:ALPHA")

    def test_set_available_toggles_availability(self) -> None:
        """Hook: availability toggles in both directions."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.set_available(False)
            self.assertFalse(queue.is_available)
            queue.set_available(True)
            self.assertTrue(queue.is_available)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T18:30:55Z
# LAST_CHANGED: 2026-11-04T18:30:55Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: b9b8efe1d927
# COVERAGE_AUDIT: 2026-11-04T18:30:55Z
# QA_AUDIT: 2026-11-04T18:30:55Z
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl_test.py ===
"""Unit tests for task_worker_impl per its grounding specification."""

from __future__ import annotations

import os
import sys
import unittest
from typing import List, Optional, Tuple

_PARTS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, _PARTS_ROOT)
sys.modules.pop("task_queue", None)
sys.modules.pop("task_queue.lib", None)

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from task_queue.lib.task_queue import (
    QueueUnavailableException,
    TaskQueue,
)
from task_queue.lib.task_worker import WorkerExecutionException
from task_queue.lib.task_worker_impl import (
    TaskWorker,
    __initialize__,
)


class MockTaskQueue:
    """Collaborator double recording completions reported by the worker."""

    def __init__(self) -> None:
        self.completions: List[Tuple[str, str]] = []
        self.dispatch_count: int = 0
        self.dispatch_result: str = "task-1"
        self.available: bool = True

    @property
    def pending_count(self) -> int:
        return 1

    def submit(self, task_id: str, payload: str) -> None:
        pass

    def dispatch(self) -> str:
        self.dispatch_count += 1
        if not self.available:
            raise QueueUnavailableException("Task queue is unavailable")
        return self.dispatch_result

    def complete(self, task_id: str, outcome: str) -> None:
        if not self.available:
            raise QueueUnavailableException("Task queue is unavailable")
        self.completions.append((task_id, outcome))

    def get_outcome(self, task_id: str) -> Optional[str]:
        return None

    def clear(self) -> None:
        pass

    def set_available(self, available: bool) -> None:
        self.available = available


class TaskWorkerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.queue = MockTaskQueue()
        self.registry.register_instance(self.queue, keys=[TaskQueue], tier=system)

    def test_initial_telemetry(self) -> None:
        """Happy path: a fresh worker has no processed tasks and is idle."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            self.assertEqual(worker.processed_count, 0)
            self.assertIsNone(worker.last_task_id)
            self.assertFalse(worker.is_busy)

    def test_execute_reports_completion_and_records_telemetry(self) -> None:
        """POSTCONDITION: successful execution notifies the queue and updates telemetry."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            outcome = worker.execute("task-1", "alpha")
            self.assertEqual(outcome, "PROCESSED:ALPHA")
            self.assertEqual(self.queue.completions, [("task-1", "PROCESSED:ALPHA")])
            self.assertEqual(worker.processed_count, 1)
            self.assertEqual(worker.last_task_id, "task-1")
            self.assertFalse(worker.is_busy)

    def test_execute_failing_task_raises_execution_exception(self) -> None:
        """POSTCONDITION: designated failing tasks raise WorkerExecutionException."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            worker.set_failing_task("task-1")
            with self.assertRaises(WorkerExecutionException):
                worker.execute("task-1", "alpha")
            self.assertEqual(self.queue.completions, [])
            self.assertEqual(worker.processed_count, 0)
            self.assertFalse(worker.is_busy)

    def test_execute_unavailable_queue_raises_execution_exception(self) -> None:
        """POSTCONDITION: an unavailable queue raises WorkerExecutionException."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            self.queue.available = False
            with self.assertRaises(WorkerExecutionException):
                worker.execute("task-1", "alpha")
            self.assertFalse(worker.is_busy)

    def test_set_failing_task_can_clear_designation(self) -> None:
        """Hook: clearing the failing designation lets the task execute successfully."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            worker.set_failing_task("task-1")
            worker.set_failing_task("task-1", False)
            outcome = worker.execute("task-1", "alpha")
            self.assertEqual(outcome, "PROCESSED:ALPHA")
            self.assertEqual(worker.processed_count, 1)

    def test_reset_clears_telemetry(self) -> None:
        """POSTCONDITION: reset clears counters, last task id, and busy state."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            worker.execute("task-1", "alpha")
            worker.reset()
            self.assertEqual(worker.processed_count, 0)
            self.assertIsNone(worker.last_task_id)
            self.assertFalse(worker.is_busy)

    def test_fetch_and_execute_dispatches_pending_task(self) -> None:
        """POSTCONDITION: dispatch succeeds and the dispatched task identifier is returned."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            task_id = worker.fetch_and_execute()
            self.assertEqual(task_id, "task-1")
            self.assertEqual(self.queue.dispatch_count, 1)

    def test_fetch_and_execute_unavailable_queue_raises_execution_exception(self) -> None:
        """POSTCONDITION: an unavailable queue raises WorkerExecutionException."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            self.queue.available = False
            with self.assertRaises(WorkerExecutionException):
                worker.fetch_and_execute()


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T18:30:55Z
# LAST_CHANGED: 2026-11-04T18:30:55Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 1303ff8e7064
# COVERAGE_AUDIT: 2026-11-04T18:30:55Z
# QA_AUDIT: 2026-11-04T18:30:55Z
# --- END AUTOFAB METADATA ---
