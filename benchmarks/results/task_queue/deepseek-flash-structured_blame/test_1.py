# === File: task_queue_impl_test.py ===
"""Unit tests for task_queue_impl per its grounding specification."""

from __future__ import annotations

import unittest
from contextlib import ExitStack

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from task_queue.lib.task_queue import (
    QueueEmptyError,
    QueueError,
    QueueUnavailableException,
)
from task_queue.lib.task_queue_impl import (
    QueueFullError,
    TaskQueue,
    __initialize__,
)
from task_queue.lib.task_worker import TaskWorker


class MockTaskWorker:
    """Collaborator double for the task worker protocol."""

    tier = system

    def __init__(self) -> None:
        self.executed: list[tuple[str, str]] = []

    def execute(self, task_id: str, payload: str) -> str:
        self.executed.append((task_id, payload))
        return f"PROCESSED:{payload.upper()}"

    def fetch_and_execute(self) -> str:
        return ""


class TaskQueueImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.worker = MockTaskWorker()
        self.registry.register_instance(
            self.worker,
            keys=[TaskWorker],
            tier=system,
        )
        self.exit_stack = ExitStack()
        self.phase_scope = self.exit_stack.enter_context(
            enter_phase(system, registry=self.registry)
        )
        self.queue = self.phase_scope.get_singleton(TaskQueue)

    def tearDown(self) -> None:
        self.exit_stack.close()

    def test_initial_state(self) -> None:
        """Initial invariant: capacity 10, empty queue, available, not full."""
        self.assertEqual(self.queue.capacity, 10)
        self.assertEqual(self.queue.pending_count, 0)
        self.assertTrue(self.queue.is_empty)
        self.assertFalse(self.queue.is_full)
        self.assertTrue(self.queue.is_available)

    def test_submit_appends_task(self) -> None:
        """Submitting on an available queue appends the task and increments the pending count."""
        self.queue.submit("task-1", "payload-1")
        self.assertEqual(self.queue.pending_count, 1)
        self.assertFalse(self.queue.is_empty)

    def test_submit_raises_when_unavailable(self) -> None:
        """Submitting on an unavailable queue raises QueueUnavailableException."""
        self.queue.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.queue.submit("task-1", "payload-1")
        self.assertEqual(self.queue.pending_count, 0)

    def test_submit_raises_when_full(self) -> None:
        """Submitting at capacity raises QueueFullError and preserves the pending tasks."""
        for index in range(9):
            self.queue.submit(f"task-{index}", f"payload-{index}")
        self.assertFalse(self.queue.is_full)
        self.queue.submit("task-9", "payload-9")
        self.assertTrue(self.queue.is_full)
        self.assertEqual(self.queue.pending_count, 10)
        with self.assertRaises(QueueFullError):
            self.queue.submit("overflow", "payload-overflow")
        self.assertEqual(self.queue.pending_count, 10)

    def test_dispatch_pops_oldest_task_and_executes(self) -> None:
        """Dispatching pops the oldest pending task, decrements the count, and returns its id."""
        self.queue.submit("task-1", "payload-1")
        self.queue.submit("task-2", "payload-2")
        dispatched = self.queue.dispatch()
        self.assertEqual(dispatched, "task-1")
        self.assertEqual(self.queue.pending_count, 1)
        self.assertEqual(self.worker.executed, [("task-1", "payload-1")])
        dispatched = self.queue.dispatch()
        self.assertEqual(dispatched, "task-2")
        self.assertTrue(self.queue.is_empty)
        self.assertEqual(
            self.worker.executed,
            [("task-1", "payload-1"), ("task-2", "payload-2")],
        )

    def test_dispatch_raises_when_empty(self) -> None:
        """Dispatching from an empty queue raises QueueEmptyError."""
        self.assertTrue(self.queue.is_empty)
        with self.assertRaises(QueueEmptyError):
            self.queue.dispatch()
        self.assertEqual(self.worker.executed, [])

    def test_dispatch_raises_when_unavailable(self) -> None:
        """Dispatching on an unavailable queue raises QueueUnavailableException."""
        self.queue.submit("task-1", "payload-1")
        self.queue.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.queue.dispatch()
        self.assertEqual(self.queue.pending_count, 1)
        self.assertEqual(self.worker.executed, [])

    def test_complete_records_outcome(self) -> None:
        """Completing a task records its outcome for later retrieval."""
        self.queue.complete("task-1", "SUCCESS")
        self.assertEqual(self.queue.get_outcome("task-1"), "SUCCESS")

    def test_complete_raises_when_unavailable(self) -> None:
        """Completing a task on an unavailable queue raises QueueUnavailableException."""
        self.queue.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.queue.complete("task-1", "SUCCESS")
        self.assertIsNone(self.queue.get_outcome("task-1"))

    def test_get_outcome_returns_none_for_pending_task(self) -> None:
        """Retrieving the outcome of an uncompleted task yields None."""
        self.queue.submit("task-1", "payload-1")
        self.assertIsNone(self.queue.get_outcome("task-1"))
        self.assertIsNone(self.queue.get_outcome("missing-task"))

    def test_clear_purges_tasks_and_outcomes(self) -> None:
        """Clearing purges all pending tasks and recorded outcomes."""
        self.queue.submit("task-1", "payload-1")
        self.queue.submit("task-2", "payload-2")
        self.queue.complete("task-1", "SUCCESS")
        self.queue.clear()
        self.assertEqual(self.queue.pending_count, 0)
        self.assertTrue(self.queue.is_empty)
        self.assertIsNone(self.queue.get_outcome("task-1"))

    def test_set_available_toggles_availability(self) -> None:
        """Test hook: toggles is_available flag both ways."""
        self.queue.set_available(False)
        self.assertFalse(self.queue.is_available)
        self.queue.set_available(True)
        self.assertTrue(self.queue.is_available)

    def test_queue_full_error_is_queue_error(self) -> None:
        """Data type: QueueFullError refines the QueueError hierarchy."""
        self.assertTrue(issubclass(QueueFullError, QueueError))


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T16:53:42Z
# LAST_CHANGED: 2026-11-08T16:52:54Z
# CHANGE: Fix phase scope activation: enter enter_phase(system, registry=...) as a live context manager via ExitStack in setUp and close it in tearDown so MockTaskWorker and TaskQueue singletons resolve during dispatch tests
# COVERAGE_AUDIT: 2026-11-08T16:53:42Z
# QA_AUDIT: 2026-11-08T16:53:19Z
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl_test.py ===
"""Unit tests for task_worker_impl per its grounding specification."""

from __future__ import annotations

import unittest
from contextlib import ExitStack
from typing import Optional

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from task_queue.lib.task_queue import (
    QueueEmptyError,
    QueueUnavailableException,
    TaskQueue,
)
from task_queue.lib.task_worker import (
    WorkerError,
    WorkerExecutionException,
)
from task_queue.lib.task_worker_impl import (
    TaskWorker,
    __initialize__,
)


class MockTaskQueue:
    """Collaborator double for the task queue protocol."""

    tier = system

    def __init__(self) -> None:
        self.pending: list[str] = []
        self.completed: list[tuple[str, str]] = []
        self.dispatch_error: Optional[Exception] = None
        self.complete_error: Optional[Exception] = None

    @property
    def pending_count(self) -> int:
        return len(self.pending)

    def submit(self, task_id: str, payload: str) -> None:
        self.pending.append(task_id)

    def dispatch(self) -> str:
        error = self.dispatch_error
        if error is not None:
            raise error
        if not self.pending:
            raise QueueEmptyError()
        return self.pending.pop(0)

    def complete(self, task_id: str, outcome: str) -> None:
        error = self.complete_error
        if error is not None:
            raise error
        self.completed.append((task_id, outcome))

    def get_outcome(self, task_id: str) -> Optional[str]:
        for completed_id, outcome in self.completed:
            if completed_id == task_id:
                return outcome
        return None

    def clear(self) -> None:
        self.pending.clear()
        self.completed.clear()

    def set_available(self, available: bool) -> None:
        pass


class TaskWorkerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.queue = MockTaskQueue()
        self.registry.register_instance(
            self.queue,
            keys=[TaskQueue],
            tier=system,
        )
        self.exit_stack = ExitStack()
        self.phase_scope = self.exit_stack.enter_context(
            enter_phase(system, registry=self.registry)
        )
        self.worker = self.phase_scope.get_singleton(TaskWorker)

    def tearDown(self) -> None:
        self.exit_stack.close()

    def test_initial_telemetry(self) -> None:
        """Initial invariant: zero processed tasks, no last task, and not busy."""
        self.assertEqual(self.worker.processed_count, 0)
        self.assertIsNone(self.worker.last_task_id)
        self.assertFalse(self.worker.is_busy)

    def test_execute_reports_completion_and_updates_telemetry(self) -> None:
        """Executing a task reports the transformed outcome and updates telemetry."""
        outcome = self.worker.execute("task-1", "hello")
        self.assertEqual(outcome, "PROCESSED:HELLO")
        self.assertEqual(self.queue.completed, [("task-1", "PROCESSED:HELLO")])
        self.assertEqual(self.worker.processed_count, 1)
        self.assertEqual(self.worker.last_task_id, "task-1")
        self.assertFalse(self.worker.is_busy)

    def test_execute_accumulates_telemetry_across_tasks(self) -> None:
        """Each successful execution increments the processed count and tracks the last task."""
        self.worker.execute("task-1", "alpha")
        self.worker.execute("task-2", "beta")
        self.assertEqual(self.worker.processed_count, 2)
        self.assertEqual(self.worker.last_task_id, "task-2")
        self.assertEqual(
            self.queue.completed,
            [("task-1", "PROCESSED:ALPHA"), ("task-2", "PROCESSED:BETA")],
        )

    def test_execute_failing_task_raises(self) -> None:
        """Executing a designated failing task raises WorkerExecutionException and clears busy state."""
        self.worker.set_failing_task("task-bad")
        with self.assertRaises(WorkerExecutionException):
            self.worker.execute("task-bad", "hello")
        self.assertFalse(self.worker.is_busy)
        self.assertEqual(self.worker.processed_count, 0)
        self.assertIsNone(self.worker.last_task_id)
        self.assertEqual(self.queue.completed, [])

    def test_execute_raises_when_queue_unavailable(self) -> None:
        """Completion reporting on an unavailable queue raises WorkerExecutionException."""
        self.queue.complete_error = QueueUnavailableException()
        with self.assertRaises(WorkerExecutionException):
            self.worker.execute("task-1", "hello")
        self.assertFalse(self.worker.is_busy)
        self.assertEqual(self.queue.completed, [])

    def test_set_failing_task_can_be_cleared(self) -> None:
        """A task marked as failing can be restored to successful execution."""
        self.worker.set_failing_task("task-1")
        self.worker.set_failing_task("task-1", False)
        outcome = self.worker.execute("task-1", "hello")
        self.assertEqual(outcome, "PROCESSED:HELLO")
        self.assertEqual(self.worker.processed_count, 1)

    def test_reset_clears_telemetry(self) -> None:
        """Resetting clears the processed count, last task id, and busy state."""
        self.worker.execute("task-1", "hello")
        self.worker.reset()
        self.assertEqual(self.worker.processed_count, 0)
        self.assertIsNone(self.worker.last_task_id)
        self.assertFalse(self.worker.is_busy)

    def test_fetch_and_execute_dispatches_task(self) -> None:
        """Fetching dispatches the next pending task, executes it, and returns its id."""
        self.queue.submit("task-7", "payload-7")
        returned = self.worker.fetch_and_execute()
        self.assertEqual(returned, "task-7")
        self.assertEqual(self.worker.processed_count, 1)
        self.assertEqual(self.worker.last_task_id, "task-7")
        self.assertEqual(len(self.queue.completed), 1)
        self.assertEqual(self.queue.completed[0][0], "task-7")
        self.assertTrue(self.queue.completed[0][1].startswith("PROCESSED:"))

    def test_fetch_and_execute_raises_worker_error_when_empty(self) -> None:
        """Fetching from an empty collaborator queue raises WorkerError."""
        with self.assertRaises(WorkerError):
            self.worker.fetch_and_execute()
        self.assertEqual(self.worker.processed_count, 0)

    def test_fetch_and_execute_raises_execution_exception_when_unavailable(self) -> None:
        """Fetching from an unavailable collaborator queue raises WorkerExecutionException."""
        self.queue.dispatch_error = QueueUnavailableException()
        with self.assertRaises(WorkerExecutionException):
            self.worker.fetch_and_execute()
        self.assertEqual(self.worker.processed_count, 0)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T16:53:44Z
# LAST_CHANGED: 2026-11-08T16:53:00Z
# CHANGE: Fix phase scope activation: enter enter_phase(system, registry=...) as a live context manager via ExitStack in setUp and close it in tearDown so MockTaskQueue and TaskWorker singletons resolve during execute and fetch_and_execute tests
# COVERAGE_AUDIT: 2026-11-08T16:53:44Z
# QA_AUDIT: 2026-11-08T16:53:21Z
# --- END AUTOFAB METADATA ---
