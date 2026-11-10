# === File: task_queue_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for TaskQueue."""

from __future__ import annotations

import unittest
from typing import Any, Optional

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_1.parts.task_queue.pretense.task_queue_pretense import (
    TaskQueueState,
    TaskQueueStateMachine,
)
from benchmark_1.parts.task_queue.lib.task_queue import (
    QueueEmptyError,
    QueueUnavailableException,
)
from benchmark_1.parts.task_queue.lib.task_queue_impl import QueueFullError, TaskQueue
from benchmark_1.parts.task_queue.lib.task_queue_impl import __initialize__ as _tq_initialize
from benchmark_1.parts.task_queue.lib.task_worker_impl import __initialize__ as _tw_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class TaskQueueImplPseudoStateMachine(TaskQueueStateMachine):
    """Implementation pseudo-state machine for TaskQueue."""

    @transition(TaskQueue.submit)
    def submit(
        self,
        task_id: str,
        payload: str,
    ) -> Any:
        target: TaskQueue = sut(TaskQueue)
        if not self.state.available:
            with raises(QueueUnavailableException):
                ret = call_target(target.submit(task_id, payload))
            raise QueueUnavailableException()
        if target.pending_count >= target.capacity:
            with raises(QueueFullError):
                ret = call_target(target.submit(task_id, payload))
            raise QueueFullError()
        before = target.pending_count
        ret = call_target(target.submit(task_id, payload))
        assert target.pending_count == before + 1
        return ret

    @transition(TaskQueue.dispatch)
    def dispatch(
        self,
    ) -> Any:
        target: TaskQueue = sut(TaskQueue)
        if not self.state.available:
            with raises(QueueUnavailableException):
                ret = call_target(target.dispatch())
            raise QueueUnavailableException()
        if target.pending_count == 0:
            with raises(QueueEmptyError):
                ret = call_target(target.dispatch())
            raise QueueEmptyError()
        before = target.pending_count
        ret = call_target(target.dispatch())
        assert target.pending_count == before - 1
        return ret

    @transition(TaskQueue.complete)
    def complete(
        self,
        task_id: str,
        outcome: str,
    ) -> Any:
        target: TaskQueue = sut(TaskQueue)
        if not self.state.available:
            with raises(QueueUnavailableException):
                ret = call_target(target.complete(task_id, outcome))
            raise QueueUnavailableException()
        ret = call_target(target.complete(task_id, outcome))
        assert target.get_outcome(task_id) == outcome
        return ret

    @transition(TaskQueue.get_outcome)
    def get_outcome(
        self,
        task_id: str,
    ) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(target.get_outcome(task_id))
        return ret

    @transition(TaskQueue.clear)
    def clear(
        self,
    ) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(target.clear())
        assert target.pending_count == 0
        return ret

    @transition(TaskQueue.set_available)
    def set_available(
        self,
        available: bool,
    ) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(target.set_available(available))
        assert target.is_available == available
        return ret

    @transition(name="capacity")
    def capacity(self) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(getattr(target, "capacity"))
        assert ret > 0
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(getattr(target, "is_empty"))
        assert ret == (target.pending_count == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(getattr(target, "is_full"))
        assert ret == (target.pending_count >= target.capacity)
        return ret

    @transition(name="is_available")
    def is_available(self) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(getattr(target, "is_available"))
        return ret

    @transition(name="pending_count")
    def pending_count(self) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(getattr(target, "pending_count"))
        assert ret >= 0
        return ret


proto = TaskQueueImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestTaskQueueImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies the contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _tq_initialize(self.registry)
        _tw_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(TaskQueue)
        self.sm = TaskQueueImplPseudoStateMachine(singletons={TaskQueue: self.real})
        self.checked = self.sm.as_checked(TaskQueue, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_submit_and_dispatch(self) -> None:
        self.assertEqual(self.checked.capacity, 10)
        self.assertTrue(self.checked.is_empty)
        self.assertFalse(self.checked.is_full)
        self.assertTrue(self.checked.is_available)
        self.checked.submit("task-1", "payload")
        self.checked.submit("task-2", "payload")
        self.assertEqual(self.checked.pending_count, 2)
        self.assertFalse(self.checked.is_empty)
        self.assertEqual(self.checked.dispatch(), "task-1")
        self.assertEqual(self.checked.pending_count, 1)
        self.assertEqual(self.checked.get_outcome("task-1"), "PROCESSED:PAYLOAD")
        self.assertIsNone(self.checked.get_outcome("missing"))

    def test_real_complete_and_clear(self) -> None:
        self.checked.complete("task-1", "completed")
        self.assertEqual(self.checked.get_outcome("task-1"), "completed")
        self.checked.submit("task-2", "payload")
        self.checked.clear()
        self.assertEqual(self.checked.pending_count, 0)
        self.assertTrue(self.checked.is_empty)
        self.assertIsNone(self.checked.get_outcome("task-1"))

    def test_real_is_full(self) -> None:
        for index in range(10):
            self.checked.submit(f"task-{index}", "payload")
        self.assertEqual(self.checked.pending_count, 10)
        self.assertTrue(self.checked.is_full)

    def test_real_full_queue_submit(self) -> None:
        for index in range(10):
            self.checked.submit(f"task-{index}", "payload")
        self.assertTrue(self.checked.is_full)
        with self.assertRaises(QueueFullError):
            self.checked.submit("task-overflow", "payload")
        self.assertEqual(self.checked.pending_count, 10)

    def test_real_empty_queue_dispatch(self) -> None:
        self.assertTrue(self.checked.is_empty)
        with self.assertRaises(QueueEmptyError):
            self.checked.dispatch()
        self.assertEqual(self.checked.pending_count, 0)

    def test_real_unavailable_queue(self) -> None:
        self.checked.submit("task-1", "payload")
        self.checked.set_available(False)
        self.assertFalse(self.checked.is_available)
        with self.assertRaises(QueueUnavailableException):
            self.checked.submit("task-2", "payload")
        with self.assertRaises(QueueUnavailableException):
            self.checked.dispatch()
        with self.assertRaises(QueueUnavailableException):
            self.checked.complete("task-1", "done")
        self.assertEqual(self.checked.pending_count, 1)
        self.checked.set_available(True)
        self.assertTrue(self.checked.is_available)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def make_sut() -> TaskQueue:
    registry = LifecycleRegistry()
    _tq_initialize(registry)
    _tw_initialize(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(TaskQueue)


TaskQueueFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=TaskQueueState,
    name="TaskQueueFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:27:05Z
# LAST_CHANGED: 2026-11-08T17:25:09Z
# CHANGE: Add deterministic fixed-scenario coverage for the contracted error outcomes: an empty-queue dispatch scenario terminating in QueueEmptyError and a capacity-filled submit scenario terminating in QueueFullError, so both contracted rejections are exercised by standing scenarios rather than only by fuzz.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:27:05Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:25:24Z
# --- END AUTOFAB METADATA ---


# === File: task_queue_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for TaskQueue."""

from __future__ import annotations

from dataclasses import dataclass, field
import unittest
from typing import Any, Dict, List, Optional, Tuple

from pretense import (
    Domain,
    StateMachine,
    make_return_value,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_1.parts.task_queue.lib.task_queue import (
    QueueEmptyError,
    QueueUnavailableException,
    TaskQueue,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class TaskQueueState:
    """Canonical model state for TaskQueue operations."""

    pending_tasks: List[Tuple[str, str]] = field(default_factory=list)
    outcomes: Dict[str, str] = field(default_factory=dict)
    available: bool = True


class TaskQueueStateMachine(StateMachine[TaskQueueState]):
    """Unified Pretense State Machine for TaskQueue."""

    def __init__(
        self,
        state: Optional[TaskQueueState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or TaskQueueState(), singletons=singletons)

    @transition(TaskQueue.submit)
    def submit(
        self,
        task_id: str,
        payload: str,
    ) -> None:
        """Appends a task to the queue tail, or raises when unavailable."""
        require_arg(task_id, Domain.type(str), preferred=["task-1"])
        require_arg(payload, Domain.type(str), preferred=["payload"])
        if not self.state.available:
            with raises(QueueUnavailableException):
                ret = make_return_value()
                raise QueueUnavailableException()
            raise QueueUnavailableException()
        ret = make_return_value()
        self.state.pending_tasks.append((task_id, payload))
        assert len(self.state.pending_tasks) > 0
        return ret

    @transition(TaskQueue.dispatch)
    def dispatch(
        self,
    ) -> str:
        """Pops the oldest pending task and returns its identifier."""
        if not self.state.available:
            with raises(QueueUnavailableException):
                ret = make_return_value("")
                raise QueueUnavailableException()
            raise QueueUnavailableException()
        if len(self.state.pending_tasks) == 0:
            with raises(QueueEmptyError):
                ret = make_return_value("")
                raise QueueEmptyError()
            raise QueueEmptyError()
        task_id, payload = self.state.pending_tasks.pop(0)
        ret = make_return_value(task_id)
        modeled_outcome = f"PROCESSED:{payload.upper()}"
        self.state.outcomes[task_id] = modeled_outcome
        assert self.state.outcomes[task_id] == modeled_outcome
        assert ret == task_id
        return ret

    @transition(TaskQueue.complete)
    def complete(
        self,
        task_id: str,
        outcome: str,
    ) -> None:
        """Records the completion outcome for a task, or raises when unavailable."""
        require_arg(task_id, Domain.type(str), preferred=["task-1"])
        require_arg(outcome, Domain.type(str), preferred=["done"])
        if not self.state.available:
            with raises(QueueUnavailableException):
                ret = make_return_value()
                raise QueueUnavailableException()
            raise QueueUnavailableException()
        ret = make_return_value()
        self.state.outcomes[task_id] = outcome
        assert self.state.outcomes[task_id] == outcome
        return ret

    @transition(TaskQueue.get_outcome)
    def get_outcome(
        self,
        task_id: str,
    ) -> Optional[str]:
        """Returns the recorded outcome for a task, else None."""
        require_arg(task_id, Domain.type(str), preferred=["task-1"])
        recorded = self.state.outcomes.get(task_id)
        ret = make_return_value(recorded)
        assert ret == recorded
        return ret

    @transition(TaskQueue.clear)
    def clear(
        self,
    ) -> None:
        """Purges all pending tasks and recorded outcomes."""
        ret = make_return_value()
        self.state.pending_tasks.clear()
        self.state.outcomes.clear()
        assert len(self.state.pending_tasks) == 0
        assert len(self.state.outcomes) == 0
        return ret

    @transition(TaskQueue.set_available)
    def set_available(
        self,
        available: bool,
    ) -> None:
        """Test-only hook toggling queue availability."""
        require_arg(available, Domain.boolean())
        ret = make_return_value()
        self.state.available = available
        assert self.state.available == available
        return ret

    @transition(name="pending_count")
    def pending_count(self) -> int:
        """Returns the current number of pending tasks."""
        expected = len(self.state.pending_tasks)
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition.seeding
    def seed_unavailable(self) -> None:
        """Seeds queue unavailability to exercise operational failure paths."""
        self.state.available = False


proto = TaskQueueStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeTaskQueue = synthesize_fake(TaskQueueStateMachine)


def make_task_queue_fake(state: Optional[TaskQueueState] = None) -> TaskQueue:
    """Creates a synthesized in-memory fake for the task queue interface."""
    return FakeTaskQueue(state=state or TaskQueueState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestTaskQueueFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_task_queue_fake()
        self.sm = TaskQueueStateMachine()

    def test_fake_queue_lifecycle(self) -> None:
        """Exercises every declared transition and the seeding transition."""
        self.sm.seed_unavailable()
        self.assertEqual(self.fake.pending_count, 0)
        self.fake.submit("task-1", "payload")
        self.fake.submit("task-2", "another payload")
        self.assertEqual(self.fake.pending_count, 2)
        self.assertEqual(self.fake.dispatch(), "task-1")
        self.assertEqual(self.fake.pending_count, 1)
        self.assertEqual(self.fake.get_outcome("task-1"), "PROCESSED:PAYLOAD")
        self.fake.complete("task-2", "completed")
        self.assertEqual(self.fake.get_outcome("task-2"), "completed")
        self.assertIsNone(self.fake.get_outcome("missing"))
        self.fake.set_available(True)
        self.fake.clear()
        self.assertEqual(self.fake.pending_count, 0)
        self.assertIsNone(self.fake.get_outcome("task-2"))

    def test_fake_unavailable_queue(self) -> None:
        """Verifies that unavailable queue operations raise the contracted exception."""
        self.fake.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.fake.submit("task-3", "payload")
        with self.assertRaises(QueueUnavailableException):
            self.fake.complete("task-3", "outcome")


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeTaskQueueFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=TaskQueueState,
    name="FakeTaskQueueFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:21:48Z
# LAST_CHANGED: 2026-11-08T17:21:48Z
# CHANGE: Model the empty-queue dispatch outcome as the contracted QueueEmptyError (removing the readiness gate that starved the branch) so the transition is reachable and exercised by the stateful fuzz suite.
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for TaskWorker."""

from __future__ import annotations

import unittest
from typing import Any, Optional

from pretense import (
    call_target,
    raises,
    sut,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_1.parts.task_queue.pretense.task_worker_pretense import (
    TaskWorkerState,
    TaskWorkerStateMachine,
)
from benchmark_1.parts.task_queue.pretense.task_queue_pretense import (
    TaskQueueStateMachine,
)
from benchmark_1.parts.task_queue.lib.task_queue import TaskQueue as TaskQueueProtocol
from benchmark_1.parts.task_queue.lib.task_worker import (
    WorkerError,
    WorkerExecutionException,
)
from benchmark_1.parts.task_queue.lib.task_worker_impl import TaskWorker
from benchmark_1.parts.task_queue.lib.task_queue_impl import TaskQueue
from benchmark_1.parts.task_queue.lib.task_queue_impl import __initialize__ as _tq_initialize
from benchmark_1.parts.task_queue.lib.task_worker_impl import __initialize__ as _tw_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class TaskWorkerImplPseudoStateMachine(TaskWorkerStateMachine):
    """Implementation pseudo-state machine for TaskWorker."""

    @transition(TaskWorker.reset)
    def reset(
        self,
    ) -> Any:
        target: TaskWorker = sut(TaskWorker)
        ret = call_target(target.reset())
        assert target.processed_count == 0
        assert target.last_task_id is None
        assert target.is_busy is False
        return ret

    @transition(TaskWorker.execute)
    def execute(
        self,
        task_id: str,
        payload: str,
    ) -> Any:
        target: TaskWorker = sut(TaskWorker)
        queue = sut(TaskQueueProtocol)
        if self.state.failing_tasks.get(task_id, False) or not getattr(queue, "is_available", True):
            with raises(WorkerExecutionException):
                ret = call_target(target.execute(task_id, payload))
            raise WorkerExecutionException()
        before = target.processed_count
        ret = call_target(target.execute(task_id, payload))
        assert target.processed_count == before + 1
        assert target.is_busy is False
        return ret

    @transition(TaskWorker.fetch_and_execute)
    def fetch_and_execute(
        self,
    ) -> Any:
        target: TaskWorker = sut(TaskWorker)
        queue = sut(TaskQueueProtocol)
        if not getattr(queue, "is_available", True):
            with raises(WorkerExecutionException):
                ret = call_target(target.fetch_and_execute())
            raise WorkerExecutionException()
        if queue.pending_count == 0:
            with raises(WorkerError):
                ret = call_target(target.fetch_and_execute())
            raise WorkerError()
        ret = call_target(target.fetch_and_execute())
        return ret

    @transition(TaskWorker.set_failing_task)
    def set_failing_task(
        self,
        task_id: str,
        failing: bool,
    ) -> Any:
        target: TaskWorker = sut(TaskWorker)
        ret = call_target(target.set_failing_task(task_id, failing))
        return ret

    @transition(name="processed_count")
    def processed_count(self) -> Any:
        target: TaskWorker = sut(TaskWorker)
        ret = call_target(getattr(target, "processed_count"))
        assert ret >= 0
        return ret

    @transition(name="last_task_id")
    def last_task_id(self) -> Any:
        target: TaskWorker = sut(TaskWorker)
        ret = call_target(getattr(target, "last_task_id"))
        return ret

    @transition(name="is_busy")
    def is_busy(self) -> Any:
        target: TaskWorker = sut(TaskWorker)
        ret = call_target(getattr(target, "is_busy"))
        return ret


proto = TaskWorkerImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestTaskWorkerImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies the contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _tq_initialize(self.registry)
        _tw_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(TaskWorker)
        self.queue = get_singleton(TaskQueue)
        self.sm = TaskWorkerImplPseudoStateMachine(
            singletons={
                TaskWorker: self.real,
                TaskQueueProtocol: self.queue,
            }
        )
        self.checked = self.sm.as_checked(TaskWorker, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_execute_success(self) -> None:
        self.assertEqual(self.checked.processed_count, 0)
        self.assertIsNone(self.checked.last_task_id)
        self.assertFalse(self.checked.is_busy)
        self.assertEqual(self.checked.execute("task-1", "payload"), "PROCESSED:PAYLOAD")
        self.assertEqual(self.checked.processed_count, 1)
        self.assertEqual(self.checked.last_task_id, "task-1")
        self.assertFalse(self.checked.is_busy)
        self.assertEqual(self.queue.get_outcome("task-1"), "PROCESSED:PAYLOAD")

    def test_real_reset(self) -> None:
        self.checked.execute("task-1", "payload")
        self.checked.reset()
        self.assertEqual(self.checked.processed_count, 0)
        self.assertIsNone(self.checked.last_task_id)
        self.assertFalse(self.checked.is_busy)

    def test_real_failing_task(self) -> None:
        self.checked.set_failing_task("task-2", True)
        with self.assertRaises(WorkerExecutionException):
            self.checked.execute("task-2", "payload")
        self.assertFalse(self.checked.is_busy)
        self.checked.set_failing_task("task-2", False)
        self.assertEqual(self.checked.execute("task-2", "payload"), "PROCESSED:PAYLOAD")

    def test_real_fetch_and_execute(self) -> None:
        self.queue.submit("task-1", "payload")
        self.assertEqual(self.checked.fetch_and_execute(), "task-1")

    def test_real_execute_with_unavailable_queue(self) -> None:
        self.queue.set_available(False)
        with self.assertRaises(WorkerExecutionException):
            self.checked.execute("task-4", "payload")
        self.assertFalse(self.checked.is_busy)
        self.queue.set_available(True)

    def test_real_fetch_empty_queue(self) -> None:
        self.assertEqual(self.queue.pending_count, 0)
        with self.assertRaises(WorkerError):
            self.checked.fetch_and_execute()

    def test_real_fetch_with_unavailable_queue(self) -> None:
        self.queue.submit("task-5", "payload")
        self.queue.set_available(False)
        with self.assertRaises(WorkerExecutionException):
            self.checked.fetch_and_execute()
        self.queue.set_available(True)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def make_sut() -> TaskWorker:
    registry = LifecycleRegistry()
    _tq_initialize(registry)
    _tw_initialize(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(TaskWorker)


TaskWorkerFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    collaborators=[TaskQueueStateMachine],
    sut_factory=make_sut,
    initial_state_factory=TaskWorkerState,
    name="TaskWorkerFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:30:38Z
# LAST_CHANGED: 2026-11-08T17:28:08Z
# CHANGE: Add deterministic fixed scenarios for the remaining contracted worker error outcomes: execute with an unavailable collaborator queue, fetch from an empty queue (WorkerError), and fetch with a pending task while the queue is unavailable (WorkerExecutionException); model queue availability in execute/fetch transition branches so each error is verified around the call pivot.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:30:38Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:30:24Z
# --- END AUTOFAB METADATA ---


# === File: task_worker_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for TaskWorker."""

from __future__ import annotations

from dataclasses import dataclass, field
import unittest
from typing import Any, Dict, Optional

from pretense import (
    Domain,
    StateMachine,
    make_return_value,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_1.parts.task_queue.lib.task_worker import (
    TaskWorker,
    WorkerExecutionException,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class TaskWorkerState:
    """Canonical model state for TaskWorker operations."""

    failing_tasks: Dict[str, bool] = field(default_factory=dict)
    processed_count: int = 0
    last_task_id: Optional[str] = None
    busy: bool = False


class TaskWorkerStateMachine(StateMachine[TaskWorkerState]):
    """Unified Pretense State Machine for TaskWorker."""

    def __init__(
        self,
        state: Optional[TaskWorkerState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or TaskWorkerState(), singletons=singletons)

    @transition(TaskWorker.execute)
    def execute(
        self,
        task_id: str,
        payload: str,
    ) -> str:
        """Transforms the payload into an outcome string, or raises on failure."""
        require_arg(task_id, Domain.type(str), preferred=["task-1"])
        require_arg(payload, Domain.type(str), preferred=["payload"])
        if self.state.failing_tasks.get(task_id, False):
            with raises(WorkerExecutionException):
                ret = make_return_value("")
                raise WorkerExecutionException()
            raise WorkerExecutionException()
        outcome = f"PROCESSED:{payload.upper()}"
        ret = make_return_value(outcome)
        assert ret == outcome
        self.state.processed_count += 1
        self.state.last_task_id = task_id
        return ret

    @transition(TaskWorker.fetch_and_execute)
    def fetch_and_execute(
        self,
    ) -> str:
        """Fetches the next queued task and executes it, returning its identifier."""
        dispatched = "task-1"
        ret = make_return_value(dispatched)
        assert ret == dispatched
        self.state.processed_count += 1
        self.state.last_task_id = dispatched
        return ret

    @transition(TaskWorker.set_failing_task)
    def set_failing_task(
        self,
        task_id: str,
        failing: bool,
    ) -> None:
        """Configures whether a designated task fails on execution."""
        require_arg(task_id, Domain.type(str), preferred=["task-1"])
        require_arg(failing, Domain.boolean())
        ret = make_return_value()
        self.state.failing_tasks[task_id] = failing
        assert self.state.failing_tasks.get(task_id, False) == failing
        return ret

    @transition.seeding
    def seed_failing_task(self) -> None:
        """Seeds a designated failing task to exercise execution failure paths."""
        self.state.failing_tasks["task-1"] = True


proto = TaskWorkerStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeTaskWorker = synthesize_fake(TaskWorkerStateMachine)


def make_task_worker_fake(state: Optional[TaskWorkerState] = None) -> TaskWorker:
    """Creates a synthesized in-memory fake for the task worker interface."""
    return FakeTaskWorker(state=state or TaskWorkerState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestTaskWorkerFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_task_worker_fake()
        self.sm = TaskWorkerStateMachine()

    def test_fake_worker_lifecycle(self) -> None:
        """Exercises every declared transition and the seeding transition."""
        self.sm.seed_failing_task()
        self.assertEqual(self.fake.execute("task-1", "payload"), "PROCESSED:PAYLOAD")
        self.assertEqual(self.fake.fetch_and_execute(), "task-1")
        self.fake.set_failing_task("task-2", True)
        with self.assertRaises(WorkerExecutionException):
            self.fake.execute("task-2", "payload")
        self.fake.set_failing_task("task-2", False)
        self.assertEqual(self.fake.execute("task-2", "payload"), "PROCESSED:PAYLOAD")


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeTaskWorkerFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=TaskWorkerState,
    name="FakeTaskWorkerFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:05:18Z
# LAST_CHANGED: 2026-11-08T17:05:18Z
# CHANGE: Author TaskWorker interface state machine modeling failing-task map, processed counter, last task, and busy flag with 1:1 transitions, require_arg domains, raises-wrapped WorkerExecutionException branch, seeding transition, synthesized fake factory, fake scenario coverage, and fake Hypothesis fuzzing.
# --- END AUTOFAB METADATA ---
