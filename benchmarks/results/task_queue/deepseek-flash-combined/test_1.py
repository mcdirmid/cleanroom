# === File: task_queue_impl_test.py ===
"""Unit tests for task_queue_impl per its grounding specification."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from task_queue.lib.task_queue import QueueError, QueueUnavailableException
from task_queue.lib.task_worker import TaskWorker as TaskWorkerProtocol
from task_queue.lib.task_queue_impl import (
    QueueFullError,
    TaskQueue,
    __initialize__,
)


class MockTaskWorker:
    """Test double for the task_worker.TaskWorker collaborator protocol."""

    tier = system

    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, str]] = []
        self.fetch_and_execute_calls: int = 0

    def execute(self, task_id: str, payload: str) -> str:
        self.execute_calls.append((task_id, payload))
        return f"PROCESSED:{payload.upper()}"

    def fetch_and_execute(self) -> str:
        self.fetch_and_execute_calls += 1
        return "mock-task"

    def set_failing_task(self, task_id: str, failing: bool = True) -> None:
        return None


class TaskQueueImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.mock_worker = MockTaskWorker()
        self.registry.register_instance(
            self.mock_worker,
            keys=[TaskWorkerProtocol],
            tier=system,
        )

    def test_initial_state(self) -> None:
        """Happy path: fresh queue starts empty, available, with default capacity 10."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            self.assertEqual(queue.capacity, 10)
            self.assertEqual(queue.pending_count, 0)
            self.assertTrue(queue.is_empty)
            self.assertFalse(queue.is_full)
            self.assertTrue(queue.is_available)
            self.assertIsNone(queue.get_outcome("task-1"))
            self.assertTrue(issubclass(QueueFullError, QueueError))

    def test_submit_appends_task(self) -> None:
        """WHEN queue is available, MUST append task and increment pending_count by 1."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.submit("task-1", "payload-1")
            self.assertEqual(queue.pending_count, 1)
            self.assertFalse(queue.is_empty)
            queue.submit("task-2", "payload-2")
            self.assertEqual(queue.pending_count, 2)
            self.assertFalse(queue.is_full)

    def test_submit_reaching_capacity_marks_full(self) -> None:
        """Bounded queue MUST become full once capacity pending tasks are stored."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            for index in range(queue.capacity):
                queue.submit(f"task-{index}", f"payload-{index}")
            self.assertEqual(queue.pending_count, queue.capacity)
            self.assertFalse(queue.is_empty)
            self.assertTrue(queue.is_full)

    def test_dispatch_pops_oldest_and_hands_off_to_worker(self) -> None:
        """WHEN pending_count > 0, MUST pop oldest task, decrement count, return task_id, and call worker.execute."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.submit("task-1", "alpha")
            queue.submit("task-2", "beta")
            dispatched = queue.dispatch()
            self.assertEqual(dispatched, "task-1")
            self.assertEqual(queue.pending_count, 1)
            self.assertEqual(self.mock_worker.execute_calls, [("task-1", "alpha")])

    def test_complete_records_outcome(self) -> None:
        """WHEN queue is available, MUST record outcome; get_outcome MUST return it."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.complete("task-1", "PROCESSED:ALPHA")
            self.assertEqual(queue.get_outcome("task-1"), "PROCESSED:ALPHA")
            self.assertIsNone(queue.get_outcome("task-2"))

    def test_clear_purges_tasks_and_outcomes(self) -> None:
        """MUST purge pending tasks (pending_count reset to 0) and all recorded outcomes."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.submit("task-1", "alpha")
            queue.complete("task-1", "PROCESSED:ALPHA")
            queue.clear()
            self.assertEqual(queue.pending_count, 0)
            self.assertTrue(queue.is_empty)
            self.assertIsNone(queue.get_outcome("task-1"))

    def test_unavailable_queue_rejects_submit(self) -> None:
        """WHEN queue is unavailable, MUST raise QueueUnavailableException on submit."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.set_available(False)
            with self.assertRaises(QueueUnavailableException):
                queue.submit("task-1", "alpha")
            self.assertEqual(queue.pending_count, 0)

    def test_unavailable_queue_rejects_dispatch(self) -> None:
        """WHEN queue is unavailable, MUST raise QueueUnavailableException on dispatch."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.submit("task-1", "alpha")
            queue.set_available(False)
            with self.assertRaises(QueueUnavailableException):
                queue.dispatch()
            self.assertEqual(queue.pending_count, 1)
            self.assertEqual(self.mock_worker.execute_calls, [])

    def test_unavailable_queue_rejects_complete(self) -> None:
        """WHEN queue is unavailable, MUST raise QueueUnavailableException on complete."""
        with enter_phase(system, registry=self.registry) as scope:
            queue = scope.get_singleton(TaskQueue)
            queue.set_available(False)
            with self.assertRaises(QueueUnavailableException):
                queue.complete("task-1", "PROCESSED:ALPHA")
            self.assertIsNone(queue.get_outcome("task-1"))


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - QueueFullError precondition branch on submit (checked precondition, not testable).
# - QueueEmptyError precondition branch on dispatch (checked precondition, not testable).

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T21:10:22Z
# LAST_CHANGED: 2026-11-04T20:46:45Z
# CHANGE: Implement task_queue_impl unit tests: initial state/capacity, submit append, capacity boundary, dispatch FIFO handoff to mocked TaskWorker, complete/get_outcome, clear purge, and QueueUnavailableException seeding for submit/dispatch/complete. Add part-parent sys.path bootstrap so required task_queue.lib imports resolve during collection.
# COVERAGE_AUDIT: 2026-11-04T21:10:22Z
# QA_AUDIT: 2026-11-04T21:10:07Z
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl_test.py ===
"""Unit tests for task_worker_impl per its grounding specification."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from task_queue.lib.task_queue import QueueUnavailableException, TaskQueue as TaskQueueProtocol
from task_queue.lib.task_worker import WorkerExecutionException
from task_queue.lib.task_worker_impl import (
    TaskWorker,
    __initialize__,
)


class MockTaskQueue:
    """Test double for the task_queue.TaskQueue collaborator protocol."""

    tier = system

    def __init__(self) -> None:
        self.pending: list[tuple[str, str]] = []
        self.complete_calls: list[tuple[str, str]] = []
        self.outcomes: dict[str, str] = {}
        self.available: bool = True
        self.dispatch_error: Optional[Exception] = None
        self.complete_error: Optional[Exception] = None

    @property
    def pending_count(self) -> int:
        return len(self.pending)

    def submit(self, task_id: str, payload: str) -> None:
        self.pending.append((task_id, payload))

    def dispatch(self) -> str:
        if self.dispatch_error is not None:
            raise self.dispatch_error
        task_id, _payload = self.pending.pop(0)
        return task_id

    def complete(self, task_id: str, outcome: str) -> None:
        if self.complete_error is not None:
            raise self.complete_error
        self.complete_calls.append((task_id, outcome))
        self.outcomes[task_id] = outcome

    def get_outcome(self, task_id: str) -> Optional[str]:
        return self.outcomes.get(task_id)

    def clear(self) -> None:
        self.pending.clear()
        self.outcomes.clear()

    def set_available(self, available: bool) -> None:
        self.available = available


class TaskWorkerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.mock_queue = MockTaskQueue()
        self.registry.register_instance(
            self.mock_queue,
            keys=[TaskQueueProtocol],
            tier=system,
        )

    def test_initial_state(self) -> None:
        """Happy path: fresh worker starts idle with empty telemetry."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            self.assertEqual(worker.processed_count, 0)
            self.assertIsNone(worker.last_task_id)
            self.assertFalse(worker.is_busy)

    def test_execute_reports_completion_and_updates_telemetry(self) -> None:
        """WHEN execution succeeds, MUST notify queue of completion and return outcome string."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            outcome = worker.execute("task-1", "alpha")
            self.assertEqual(outcome, "PROCESSED:ALPHA")
            self.assertEqual(self.mock_queue.complete_calls, [("task-1", "PROCESSED:ALPHA")])
            self.assertEqual(worker.processed_count, 1)
            self.assertEqual(worker.last_task_id, "task-1")
            self.assertFalse(worker.is_busy)

    def test_execute_accumulates_telemetry_across_tasks(self) -> None:
        """MUST track the most recent task identifier and count every processed task."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            worker.execute("task-1", "alpha")
            worker.execute("task-2", "beta")
            self.assertEqual(worker.processed_count, 2)
            self.assertEqual(worker.last_task_id, "task-2")
            self.assertEqual(
                self.mock_queue.complete_calls,
                [("task-1", "PROCESSED:ALPHA"), ("task-2", "PROCESSED:BETA")],
            )

    def test_execute_designated_failing_task_raises(self) -> None:
        """WHEN execution fails, MUST raise WorkerExecutionException and clear busy state."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            worker.set_failing_task("task-1")
            with self.assertRaises(WorkerExecutionException):
                worker.execute("task-1", "alpha")
            self.assertFalse(worker.is_busy)
            self.assertEqual(worker.processed_count, 0)
            self.assertIsNone(worker.last_task_id)
            self.assertEqual(self.mock_queue.complete_calls, [])

    def test_execute_reenabled_task_succeeds(self) -> None:
        """Test-only hook MUST stop designating a task as failing when failing is False."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            worker.set_failing_task("task-1")
            worker.set_failing_task("task-1", False)
            outcome = worker.execute("task-1", "beta")
            self.assertEqual(outcome, "PROCESSED:BETA")
            self.assertEqual(worker.processed_count, 1)
            self.assertEqual(worker.last_task_id, "task-1")

    def test_execute_propagates_unavailable_queue(self) -> None:
        """WHEN task queue is unavailable, MUST raise WorkerExecutionException on execute."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            self.mock_queue.complete_error = QueueUnavailableException()
            with self.assertRaises(WorkerExecutionException):
                worker.execute("task-1", "alpha")
            self.assertFalse(worker.is_busy)
            self.assertEqual(worker.processed_count, 0)
            self.assertIsNone(worker.last_task_id)

    def test_fetch_and_execute_processes_pending_task(self) -> None:
        """WHEN collaborator dispatch succeeds, MUST execute dispatched task and return task identifier."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            self.mock_queue.submit("task-1", "alpha")
            task_id = worker.fetch_and_execute()
            self.assertEqual(task_id, "task-1")
            self.assertEqual(worker.last_task_id, "task-1")
            self.assertEqual(worker.processed_count, 1)
            self.assertFalse(worker.is_busy)
            self.assertEqual(len(self.mock_queue.complete_calls), 1)
            self.assertEqual(self.mock_queue.complete_calls[0][0], "task-1")
            self.assertTrue(self.mock_queue.complete_calls[0][1].startswith("PROCESSED:"))

    def test_fetch_and_execute_propagates_unavailable_queue(self) -> None:
        """WHEN collaborator task queue is unavailable, MUST raise WorkerExecutionException."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            self.mock_queue.dispatch_error = QueueUnavailableException()
            with self.assertRaises(WorkerExecutionException):
                worker.fetch_and_execute()
            self.assertEqual(worker.processed_count, 0)
            self.assertIsNone(worker.last_task_id)
            self.assertEqual(self.mock_queue.complete_calls, [])

    def test_reset_clears_telemetry(self) -> None:
        """MUST reset processed count, last task identifier, and busy state."""
        with enter_phase(system, registry=self.registry) as scope:
            worker = scope.get_singleton(TaskWorker)
            worker.execute("task-1", "alpha")
            worker.reset()
            self.assertEqual(worker.processed_count, 0)
            self.assertIsNone(worker.last_task_id)
            self.assertFalse(worker.is_busy)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - WorkerError branch raised when the collaborator queue is empty (checked precondition, not testable).

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T21:10:24Z
# LAST_CHANGED: 2026-11-04T20:46:50Z
# CHANGE: Implement task_worker_impl unit tests: initial telemetry, execute outcome transform and queue.complete handoff, telemetry accumulation, failing-task WorkerExecutionException with busy-state reset, failing-task re-enable, QueueUnavailableException propagation from complete and dispatch, fetch_and_execute success, and reset. Add part-parent sys.path bootstrap so required task_queue.lib imports resolve during collection.
# COVERAGE_AUDIT: 2026-11-04T21:10:24Z
# QA_AUDIT: 2026-11-04T21:10:08Z
# --- END AUTOFAB METADATA ---
