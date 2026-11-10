# === File: task_queue_impl_test.py ===
"""Unit tests for task_queue_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import List, Tuple

from support.lib.lifecycle import LifecycleRegistry, LifecycleScope, enter_phase, system
from task_queue.lib.task_queue import QueueEmptyError, QueueUnavailableException
from task_queue.lib.task_worker import TaskWorker, WorkerExecutionException
from task_queue.lib.task_queue_impl import QueueFullError, TaskQueue, __initialize__


class MockTaskWorker(TaskWorker):
    """Recording test double for the TaskWorker collaborator protocol."""

    tier = system

    def __init__(self) -> None:
        self.executed: List[Tuple[str, str]] = []

    def execute(self, task_id: str, payload: str) -> str:
        self.executed.append((task_id, payload))
        return f"PROCESSED:{payload.upper()}"

    def fetch_and_execute(self) -> str:
        raise WorkerExecutionException("mock worker does not fetch")

    def set_failing_task(self, task_id: str, failing: bool = True) -> None:
        return None


class TaskQueueImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.worker = MockTaskWorker()
        self.registry.register_instance(self.worker, keys=[TaskWorker], tier=system)

    def _resolve_queue(self, scope: LifecycleScope) -> TaskQueue:
        return scope.get_singleton(TaskQueue)

    def _fill_queue(self, scope: LifecycleScope, count: int) -> TaskQueue:
        queue = self._resolve_queue(scope)
        for index in range(count):
            queue.submit(f"task-{index}", f"payload-{index}")
        return queue

    def test_initial_state(self) -> None:
        """Initialization: default capacity 10, empty, full, available, zero pending."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = self._resolve_queue(scope)
            self.assertEqual(queue.capacity, 10)
            self.assertTrue(queue.is_empty)
            self.assertFalse(queue.is_full)
            self.assertTrue(queue.is_available)
            self.assertEqual(queue.pending_count, 0)

    def test_submit_appends_task(self) -> None:
        """appends task tail, increments pending_count."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = self._resolve_queue(scope)
            queue.submit("task-a", "payload-a")
            self.assertEqual(queue.pending_count, 1)
            self.assertFalse(queue.is_empty)

    def test_submit_when_unavailable_raises(self) -> None:
        """unavailable queue raises."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = self._resolve_queue(scope)
            queue.set_available(False)
            with self.assertRaises(QueueUnavailableException):
                queue.submit("task-a", "payload-a")
            self.assertEqual(queue.pending_count, 0)

    def test_submit_when_full_raises(self) -> None:
        """Bounded capacity: submitting beyond capacity raises QueueFullError."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = self._fill_queue(scope, 10)
            self.assertTrue(queue.is_full)
            self.assertEqual(queue.pending_count, 10)
            with self.assertRaises(QueueFullError):
                queue.submit("task-extra", "payload-extra")
            self.assertEqual(queue.pending_count, 10)

    def test_dispatch_pops_oldest_task(self) -> None:
        """pops oldest task, executes it, returns task_id."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = self._resolve_queue(scope)
            queue.submit("task-1", "payload-1")
            queue.submit("task-2", "payload-2")
            dispatched = queue.dispatch()
            self.assertEqual(dispatched, "task-1")
            self.assertEqual(queue.pending_count, 1)
            self.assertEqual(self.worker.executed, [("task-1", "payload-1")])

    def test_dispatch_empty_queue_raises(self) -> None:
        """zero pending tasks raise QueueEmptyError."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = self._resolve_queue(scope)
            with self.assertRaises(QueueEmptyError):
                queue.dispatch()
            self.assertTrue(queue.is_empty)

    def test_dispatch_when_unavailable_raises(self) -> None:
        """unavailable queue raises."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = self._resolve_queue(scope)
            queue.submit("task-1", "payload-1")
            queue.set_available(False)
            with self.assertRaises(QueueUnavailableException):
                queue.dispatch()
            self.assertEqual(queue.pending_count, 1)

    def test_complete_records_outcome(self) -> None:
        """records outcome for a task."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = self._resolve_queue(scope)
            queue.complete("task-1", "DONE")
            self.assertEqual(queue.get_outcome("task-1"), "DONE")

    def test_complete_when_unavailable_raises(self) -> None:
        """unavailable queue raises."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = self._resolve_queue(scope)
            queue.set_available(False)
            with self.assertRaises(QueueUnavailableException):
                queue.complete("task-1", "DONE")
            self.assertIsNone(queue.get_outcome("task-1"))

    def test_get_outcome_uncompleted_task(self) -> None:
        """unknown task returns None."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = self._resolve_queue(scope)
            self.assertIsNone(queue.get_outcome("missing-task"))

    def test_get_outcome_completed_task(self) -> None:
        """completed task returns outcome."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = self._resolve_queue(scope)
            queue.complete("task-7", "OUTCOME")
            self.assertEqual(queue.get_outcome("task-7"), "OUTCOME")

    def test_clear_purges_tasks_and_outcomes(self) -> None:
        """clear resets pending tasks and outcomes."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = self._resolve_queue(scope)
            queue.submit("task-1", "payload-1")
            queue.complete("task-1", "DONE")
            queue.clear()
            self.assertEqual(queue.pending_count, 0)
            self.assertTrue(queue.is_empty)
            self.assertIsNone(queue.get_outcome("task-1"))

    def test_set_available_toggles_availability(self) -> None:
        """Test-only availability hook toggles is_available in both directions."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = self._resolve_queue(scope)
            queue.set_available(False)
            self.assertFalse(queue.is_available)
            queue.set_available(True)
            self.assertTrue(queue.is_available)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:03:22Z
# LAST_CHANGED: 2026-11-08T16:57:24Z
# CHANGE: Implement lifecycle-scoped unit tests for TaskQueue: initial state (capacity 10, empty/full/available/pending_count), submit append plus unavailable/full errors, dispatch oldest-to-worker plus empty/unavailable errors, complete/get_outcome recording and uncompleted None, clear purge, and test-only set_available toggling.
# COVERAGE_AUDIT: 2026-11-08T17:03:22Z
# QA_AUDIT: 2026-11-08T17:00:41Z
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl_test.py ===
"""Unit tests for task_worker_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Dict, List, Optional, Tuple

from support.lib.lifecycle import LifecycleRegistry, LifecycleScope, enter_phase, system
from task_queue.lib.task_queue import (
    QueueEmptyError,
    QueueUnavailableException,
    TaskQueue as TaskQueueProtocol,
)
from task_queue.lib.task_worker import WorkerError, WorkerExecutionException
from task_queue.lib.task_worker_impl import TaskWorker, __initialize__


class MockTaskQueue(TaskQueueProtocol):
    """Recording test double for the TaskQueue collaborator protocol."""

    tier = system

    def __init__(self) -> None:
        self.pending: List[Tuple[str, str]] = []
        self.completed: List[Tuple[str, str]] = []
        self.outcomes: Dict[str, str] = {}
        self.unavailable = False
        self.dispatch_error: Optional[Exception] = None

    @property
    def pending_count(self) -> int:
        return len(self.pending)

    def submit(self, task_id: str, payload: str) -> None:
        if self.unavailable:
            raise QueueUnavailableException("queue unavailable")
        self.pending.append((task_id, payload))

    def dispatch(self) -> str:
        if self.dispatch_error is not None:
            raise self.dispatch_error
        if not self.pending:
            raise QueueEmptyError("queue empty")
        task_id, payload = self.pending.pop(0)
        return task_id

    def complete(self, task_id: str, outcome: str) -> None:
        if self.unavailable:
            raise QueueUnavailableException("queue unavailable")
        self.completed.append((task_id, outcome))
        self.outcomes[task_id] = outcome

    def get_outcome(self, task_id: str) -> Optional[str]:
        return self.outcomes.get(task_id)

    def clear(self) -> None:
        self.pending.clear()
        self.outcomes.clear()

    def set_available(self, available: bool) -> None:
        self.unavailable = not available


class TaskWorkerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.queue = MockTaskQueue()
        self.registry.register_instance(
            self.queue, keys=[TaskQueueProtocol], tier=system
        )

    def _resolve_worker(self, scope: LifecycleScope) -> TaskWorker:
        return scope.get_singleton(TaskWorker)

    def test_initial_telemetry(self) -> None:
        """Initialization: zero processed tasks, no last task, not busy."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = self._resolve_worker(scope)
            self.assertEqual(worker.processed_count, 0)
            self.assertIsNone(worker.last_task_id)
            self.assertFalse(worker.is_busy)

    def test_execute_success_notification(self) -> None:
        """Successful execution notifies the queue and returns the outcome string."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = self._resolve_worker(scope)
            outcome = worker.execute("task-1", "payload")
            self.assertEqual(outcome, "PROCESSED:PAYLOAD")
            self.assertEqual(self.queue.completed, [("task-1", "PROCESSED:PAYLOAD")])
            self.assertEqual(self.queue.get_outcome("task-1"), "PROCESSED:PAYLOAD")
            self.assertEqual(worker.processed_count, 1)
            self.assertEqual(worker.last_task_id, "task-1")
            self.assertFalse(worker.is_busy)

    def test_execute_failing_task_raises(self) -> None:
        """Designated failing tasks raise a worker execution exception."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = self._resolve_worker(scope)
            worker.set_failing_task("task-bad")
            with self.assertRaises(WorkerExecutionException):
                worker.execute("task-bad", "payload")
            self.assertEqual(worker.processed_count, 0)
            self.assertIsNone(worker.last_task_id)
            self.assertFalse(worker.is_busy)
            self.assertEqual(self.queue.completed, [])

    def test_execute_when_queue_unavailable_raises(self) -> None:
        """Completion notification failure surfaces as a worker execution exception."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = self._resolve_worker(scope)
            self.queue.unavailable = True
            with self.assertRaises(WorkerExecutionException):
                worker.execute("task-1", "payload")
            self.assertEqual(worker.processed_count, 0)
            self.assertIsNone(worker.last_task_id)
            self.assertFalse(worker.is_busy)

    def test_fetch_and_execute_success(self) -> None:
        """Successful fetch dispatches the oldest task, executes it, returns the task id."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = self._resolve_worker(scope)
            self.queue.submit("task-7", "hello")
            fetched = worker.fetch_and_execute()
            self.assertEqual(fetched, "task-7")
            self.assertEqual(self.queue.pending_count, 0)
            self.assertEqual([task_id for task_id, _ in self.queue.completed], ["task-7"])
            self.assertEqual(worker.processed_count, 1)
            self.assertEqual(worker.last_task_id, "task-7")

    def test_fetch_and_execute_empty_queue_raises(self) -> None:
        """Empty collaborator queue raises a worker contract error."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = self._resolve_worker(scope)
            with self.assertRaises(WorkerError):
                worker.fetch_and_execute()
            self.assertEqual(worker.processed_count, 0)

    def test_fetch_and_execute_unavailable_queue_raises(self) -> None:
        """Unavailable collaborator queue raises a worker execution exception."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = self._resolve_worker(scope)
            self.queue.dispatch_error = QueueUnavailableException("queue unavailable")
            with self.assertRaises(WorkerExecutionException):
                worker.fetch_and_execute()
            self.assertEqual(worker.processed_count, 0)

    def test_reset_clears_telemetry(self) -> None:
        """Reset returns telemetry counters to their initial state."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = self._resolve_worker(scope)
            worker.execute("task-1", "payload")
            worker.reset()
            self.assertEqual(worker.processed_count, 0)
            self.assertIsNone(worker.last_task_id)
            self.assertFalse(worker.is_busy)

    def test_set_failing_task_can_be_cleared(self) -> None:
        """Clearing a designated failure lets the task execute normally."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = self._resolve_worker(scope)
            worker.set_failing_task("task-2")
            worker.set_failing_task("task-2", False)
            outcome = worker.execute("task-2", "payload")
            self.assertEqual(outcome, "PROCESSED:PAYLOAD")
            self.assertEqual(worker.processed_count, 1)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:30:36Z
# LAST_CHANGED: 2026-11-08T17:04:28Z
# CHANGE: Address fetch_and_execute success feedback: the queue double returns only the dispatched task id from dispatch, so drop the payload-derived completion-outcome assertion and instead verify the contracted postcondition - fetch dispatches and executes the task, returns the dispatched identifier, notifies completion for that task id, and records processed telemetry.
# COVERAGE_AUDIT: 2026-11-08T17:30:36Z
# QA_AUDIT: 2026-11-08T17:30:21Z
# --- END AUTOFAB METADATA ---
