# === File: task_queue_impl_pretense.py ===
from __future__ import annotations

from typing import Optional
import unittest

from pretense import sut
from support.lib.lifecycle import LifecycleTestCase

from task_queue_deepseek_flash_1.parts.task_queue.lib import task_queue_impl
from task_queue_deepseek_flash_1.parts.task_queue.lib import task_worker_impl
from task_queue_deepseek_flash_1.parts.task_queue.lib.task_queue import (
    QueueEmptyError,
    QueueUnavailableException,
    TaskQueue,
)
from task_queue_deepseek_flash_1.parts.task_queue.lib.task_queue_impl import (
    QueueFullError,
    TaskQueue as TaskQueueImpl,
)
from task_queue_deepseek_flash_1.parts.task_queue.lib.task_worker_impl import (
    TaskWorker as TaskWorkerImpl,
)
from task_queue_deepseek_flash_1.parts.task_queue.pretense.task_queue_pretense import (
    TaskQueueState,
    TaskQueueStateMachine,
    make_task_queue_fake,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class TaskQueueImplPseudoStateMachine(TaskQueueStateMachine):
    """Pseudo-state machine driving the concrete bounded task queue SUT."""

    def __init__(
        self,
        state: Optional[TaskQueueState] = None,
        singletons: Optional[dict[type[object], object]] = None,
    ) -> None:
        super().__init__(state=state, singletons=singletons)
        self.bind("available", lambda: getattr(sut(TaskQueue), "is_available"))

    def inner_pending_count(self) -> int:
        impl: TaskQueueImpl = sut(TaskQueueImpl)
        ret = impl.pending_count
        assert ret == len(self.state.pending)
        assert ret <= impl.capacity
        return ret

    def inner_submit(self, task_id: str, payload: str) -> None:
        impl: TaskQueueImpl = sut(TaskQueueImpl)
        before = impl.pending_count
        capacity = impl.capacity
        assert before <= capacity
        assert impl.is_empty == (before == 0)
        assert impl.is_full == (before >= capacity)
        impl.submit(task_id, payload)
        assert impl.pending_count == before + 1
        assert impl.pending_count <= capacity
        assert not impl.is_empty
        assert impl.is_full == (impl.pending_count >= capacity)
        return None

    def inner_dispatch(self) -> str:
        impl: TaskQueueImpl = sut(TaskQueueImpl)
        before = impl.pending_count
        assert impl.is_empty == (before == 0)
        assert before <= impl.capacity
        ret = impl.dispatch()
        assert impl.pending_count == before - 1
        assert impl.is_empty == (impl.pending_count == 0)
        return ret

    def inner_complete(self, task_id: str, outcome: str) -> None:
        target: TaskQueue = sut(TaskQueue)
        target.complete(task_id, outcome)
        assert target.get_outcome(task_id) == outcome
        return None

    def inner_get_outcome(self, task_id: str) -> Optional[str]:
        target: TaskQueue = sut(TaskQueue)
        ret = target.get_outcome(task_id)
        assert ret is None or isinstance(ret, str)
        return ret

    def inner_clear(self) -> None:
        impl: TaskQueueImpl = sut(TaskQueueImpl)
        impl.clear()
        assert impl.pending_count == 0
        assert impl.is_empty
        assert impl.capacity > 0
        return None

    def inner_set_available(self, available: bool) -> None:
        impl: TaskQueueImpl = sut(TaskQueueImpl)
        impl.set_available(available)
        assert impl.is_available == available
        return None


# ==============================================================================
# 2. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestTaskQueueImplReal(LifecycleTestCase):
    """Verifies that the concrete bounded task queue satisfies its contracts."""

    target = task_queue_impl

    def setUp(self) -> None:
        super().setUp()
        self.real: TaskQueue = self.sut
        self.sm = TaskQueueImplPseudoStateMachine(
            singletons={TaskQueue: self.real, TaskQueueImpl: self.real},
        )
        self.checked = self.sm.as_checked(TaskQueue, self.real)

    def test_submit_dispatch_and_count(self) -> None:
        self.checked.submit("task_1", "payload_1")
        self.checked.submit("task_2", "payload_2")
        assert self.checked.pending_count == 2
        assert self.checked.dispatch() == "task_1"
        assert self.checked.pending_count == 1

    def test_complete_get_outcome_and_clear(self) -> None:
        self.checked.submit("task_1", "payload_1")
        self.checked.complete("task_1", "done")
        assert self.checked.get_outcome("task_1") == "done"
        self.checked.clear()
        assert self.checked.get_outcome("task_1") is None
        assert self.checked.pending_count == 0

    def test_dispatch_empty_queue_violation(self) -> None:
        self.checked.violating(QueueEmptyError).dispatch()

    def test_submit_on_unavailable_queue(self) -> None:
        self.checked.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.checked.submit("task_1", "payload_1")

    def test_dispatch_on_unavailable_queue(self) -> None:
        self.checked.submit("task_1", "payload_1")
        self.checked.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.checked.dispatch()

    def test_complete_on_unavailable_queue(self) -> None:
        self.checked.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.checked.complete("task_1", "done")

    def test_submit_on_full_queue_violation(self) -> None:
        self.checked.submit("task_1", "payload_1")
        self.checked.submit("task_2", "payload_2")
        self.checked.submit("task_3", "payload_3")
        self.checked.submit("task_4", "payload_4")
        self.checked.submit("task_5", "payload_5")
        self.checked.submit("task_6", "payload_6")
        self.checked.submit("task_7", "payload_7")
        self.checked.submit("task_8", "payload_8")
        self.checked.submit("task_9", "payload_9")
        self.checked.submit("task_10", "payload_10")
        self.checked.violating(QueueFullError).submit("task_11", "payload_11")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:31:50Z
# LAST_CHANGED: 2026-11-13T00:31:18Z
# CHANGE: Resolve [from:pretense_qa] task_queue.dispatch.empty_queue: drop the preemptive non-empty assertion in inner_dispatch that masked QueueEmptyError with AssertionError; observe is_empty via a non-preemptive consistency check so the SUT's QueueEmptyError propagates in the violating scenario.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:31:50Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:31:38Z
# --- END AUTOFAB METADATA ---


# === File: task_queue_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import unittest

from pretense import (
    Domain,
    Env,
    StateMachine,
    require,
    require_arg,
    require_env,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from task_queue_deepseek_flash_1.parts.task_queue.lib.task_queue import (
    QueueEmptyError,
    QueueUnavailableException,
    TaskQueue,
)


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class TaskQueueState:
    """Model state for a first-in first-out task queue."""
    pending: list[str] = field(default_factory=list)
    payloads: dict[str, str] = field(default_factory=dict)
    outcomes: dict[str, str] = field(default_factory=dict)
    available: Env[bool] = True


class TaskQueueStateMachine(StateMachine[TaskQueueState]):
    """Pretense state machine modeling the TaskQueue interface contract."""

    def __init__(
        self,
        state: Optional[TaskQueueState] = None,
        singletons: Optional[dict[type[object], object]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> TaskQueueState:
        """Constructs the blank initial model state for a new task queue."""
        return TaskQueueState()

    @transition(name="pending_count")
    def pending_count(self) -> int:
        """Reports the current number of pending tasks."""
        ret = self.inner_pending_count()
        assert ret == len(self.state.pending)
        return ret

    def inner_pending_count(self) -> int:
        """Computes the fake pending task count from model state."""
        return len(self.state.pending)

    @transition(TaskQueue.submit)
    def submit(self, task_id: str, payload: str) -> None:
        """Appends a new task to the queue awaiting execution."""
        require_arg(task_id, Domain.text(min_size=1), preferred=["task_1"])
        require_arg(payload, Domain.text(min_size=1), preferred=["payload_1"])
        require_env(self.state.available, QueueUnavailableException)
        self.inner_submit(task_id, payload)
        self.state.pending.append(task_id)
        self.state.payloads[task_id] = payload
        assert self.state.pending[-1] == task_id

    def inner_submit(self, task_id: str, payload: str) -> None:
        """Computes the fake return value for submit."""
        return None

    @transition(TaskQueue.dispatch)
    def dispatch(self) -> str:
        """Dispatches the oldest pending task and returns its identifier."""
        require_env(self.state.available, QueueUnavailableException)
        require(len(self.state.pending) > 0, QueueEmptyError)
        ret = self.inner_dispatch()
        popped = self.state.pending.pop(0)
        assert ret == popped
        return ret

    def inner_dispatch(self) -> str:
        """Computes the fake dispatched task identifier from model state."""
        return self.state.pending[0]

    @transition(TaskQueue.complete)
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome string for a task."""
        require_arg(task_id, Domain.text(min_size=1), preferred=["task_1"])
        require_arg(outcome, Domain.text(min_size=1), preferred=["done"])
        require_env(self.state.available, QueueUnavailableException)
        self.inner_complete(task_id, outcome)
        self.state.outcomes[task_id] = outcome
        assert self.state.outcomes[task_id] == outcome

    def inner_complete(self, task_id: str, outcome: str) -> None:
        """Computes the fake return value for complete."""
        return None

    @transition(TaskQueue.get_outcome)
    def get_outcome(self, task_id: str) -> Optional[str]:
        """Retrieves the recorded outcome for a task."""
        require_arg(task_id, Domain.text(min_size=1), preferred=["task_1"])
        ret = self.inner_get_outcome(task_id)
        assert ret is None or isinstance(ret, str)
        return ret

    def inner_get_outcome(self, task_id: str) -> Optional[str]:
        """Computes the fake recorded outcome from model state."""
        return self.state.outcomes.get(task_id)

    @transition(TaskQueue.clear)
    def clear(self) -> None:
        """Purges all pending tasks and recorded outcomes from the queue."""
        self.inner_clear()
        self.state.pending.clear()
        self.state.payloads.clear()
        self.state.outcomes.clear()
        assert len(self.state.pending) == 0
        assert len(self.state.outcomes) == 0

    def inner_clear(self) -> None:
        """Computes the fake return value for clear."""
        return None

    @transition(TaskQueue.set_available)
    def set_available(self, available: bool) -> None:
        """Test-only hook toggling task queue availability."""
        require_arg(available, Domain.sampled_from([True, False]), preferred=[True, False])
        self.inner_set_available(available)
        self.state.available = available
        assert self.state.available == available

    def inner_set_available(self, available: bool) -> None:
        """Computes the fake return value for set_available."""
        return None


proto = TaskQueueStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeTaskQueue = synthesize_fake(TaskQueueStateMachine)


def make_task_queue_fake(state: Optional[TaskQueueState] = None) -> TaskQueue:
    """Synthesizes a fake TaskQueue instance sharing the given model state."""
    return FakeTaskQueue(state=state or TaskQueueState())


FakeTaskQueueFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeTaskQueueFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

class TestTaskQueueFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all declared transitions."""

    def setUp(self) -> None:
        self.queue = make_task_queue_fake()

    def test_pending_count(self) -> None:
        """Exercises pending_count on an empty fake queue."""
        assert self.queue.pending_count == 0

    def test_submit(self) -> None:
        """Exercises submit and confirms the pending count grows."""
        self.queue.submit("task_1", "payload_1")
        assert self.queue.pending_count == 1

    def test_dispatch(self) -> None:
        """Exercises dispatch of the oldest pending task."""
        self.queue.submit("task_1", "payload_1")
        self.queue.submit("task_2", "payload_2")
        assert self.queue.dispatch() == "task_1"
        assert self.queue.pending_count == 1

    def test_complete_and_get_outcome(self) -> None:
        """Exercises outcome recording and retrieval."""
        self.queue.submit("task_1", "payload_1")
        self.queue.complete("task_1", "done")
        assert self.queue.get_outcome("task_1") == "done"

    def test_clear(self) -> None:
        """Exercises clearing pending tasks and outcomes."""
        self.queue.submit("task_1", "payload_1")
        self.queue.complete("task_1", "done")
        self.queue.clear()
        assert self.queue.pending_count == 0
        assert self.queue.get_outcome("task_1") is None

    def test_set_available(self) -> None:
        """Exercises the availability toggle hook."""
        self.queue.set_available(False)
        self.queue.set_available(True)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:26:52Z
# LAST_CHANGED: 2026-11-13T00:26:52Z
# CHANGE: Model TaskQueue (pending FIFO, outcomes, availability Env) with 1:1 transitions, synthesized fake, fixed fake scenarios, and Hypothesis fake fuzzing.
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl_pretense.py ===
from __future__ import annotations

from typing import Optional
import unittest

from pretense import sut
from support.lib.lifecycle import LifecycleTestCase, get_singleton

from task_queue_deepseek_flash_1.parts.task_queue.lib import task_queue_impl
from task_queue_deepseek_flash_1.parts.task_queue.lib import task_worker_impl
from task_queue_deepseek_flash_1.parts.task_queue.lib.task_queue import TaskQueue
from task_queue_deepseek_flash_1.parts.task_queue.lib.task_queue_impl import (
    TaskQueue as TaskQueueImpl,
)
from task_queue_deepseek_flash_1.parts.task_queue.lib.task_worker import (
    TaskWorker,
    WorkerError,
    WorkerExecutionException,
)
from task_queue_deepseek_flash_1.parts.task_queue.lib.task_worker_impl import (
    TaskWorker as TaskWorkerImpl,
)
from task_queue_deepseek_flash_1.parts.task_queue.pretense.task_worker_pretense import (
    TaskWorkerState,
    TaskWorkerStateMachine,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class TaskWorkerImplPseudoStateMachine(TaskWorkerStateMachine):
    """Pseudo-state machine driving the concrete task worker SUT."""

    def __init__(
        self,
        state: Optional[TaskWorkerState] = None,
        singletons: Optional[dict[type[object], object]] = None,
    ) -> None:
        super().__init__(state=state, singletons=singletons)
        self.bind("available", lambda: getattr(sut(TaskQueue), "is_available"))
        self.bind("queue_empty", lambda: sut(TaskQueue).pending_count == 0)

    def make_initial_state(self) -> TaskWorkerState:
        """Constructs the concrete worker model state backed by live queue state."""
        return TaskWorkerState(queue_empty=False)

    def inner_execute(self, task_id: str, payload: str) -> str:
        impl: TaskWorkerImpl = sut(TaskWorkerImpl)
        queue: TaskQueue = sut(TaskQueue)
        impl.reset()
        assert impl.processed_count == 0
        assert impl.last_task_id is None
        assert not impl.is_busy
        ret = impl.execute(task_id, payload)
        assert ret == f"PROCESSED:{payload.upper()}"
        assert impl.processed_count == 1
        assert impl.last_task_id == task_id
        assert not impl.is_busy
        assert queue.get_outcome(task_id) == ret
        return ret

    def inner_fetch_and_execute(self) -> str:
        impl: TaskWorkerImpl = sut(TaskWorkerImpl)
        queue: TaskQueue = sut(TaskQueue)
        before = queue.pending_count
        ret = impl.fetch_and_execute()
        assert queue.pending_count == before - 1
        assert impl.processed_count == 1
        assert impl.last_task_id == ret
        assert not impl.is_busy
        return ret

    def inner_set_failing_task(self, task_id: str, failing: bool) -> None:
        impl: TaskWorkerImpl = sut(TaskWorkerImpl)
        impl.set_failing_task(task_id, failing)
        assert not impl.is_busy
        return None


# ==============================================================================
# 2. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestTaskWorkerImplReal(LifecycleTestCase):
    """Verifies that the concrete task worker satisfies its contracts."""

    target = task_worker_impl

    def setUp(self) -> None:
        super().setUp()
        self.real: TaskWorker = self.sut
        self.queue: TaskQueue = get_singleton(TaskQueue)
        self.sm = TaskWorkerImplPseudoStateMachine(
            singletons={
                TaskWorker: self.real,
                TaskQueue: self.queue,
                TaskWorkerImpl: self.real,
            },
        )
        self.checked = self.sm.as_checked(TaskWorker, self.real)

    def test_execute_success(self) -> None:
        self.checked.set_failing_task("task_2", False)
        self.checked.execute("task_1", "payload_1")
        assert self.queue.get_outcome("task_1") == "PROCESSED:PAYLOAD_1"

    def test_fetch_and_execute_success(self) -> None:
        self.queue.submit("task_1", "payload_1")
        assert self.checked.fetch_and_execute() == "task_1"

    def test_execute_failing_task(self) -> None:
        self.checked.set_failing_task("task_1", True)
        with self.assertRaises(WorkerExecutionException):
            self.checked.execute("task_1", "payload_1")

    def test_fetch_and_execute_worker_error(self) -> None:
        self.checked.violating(WorkerError).fetch_and_execute()

    def test_execute_unavailable_queue(self) -> None:
        self.queue.set_available(False)
        with self.assertRaises(WorkerExecutionException):
            self.checked.execute("task_1", "payload_1")

    def test_fetch_and_execute_unavailable_queue(self) -> None:
        self.queue.submit("task_1", "payload_1")
        self.queue.set_available(False)
        with self.assertRaises(WorkerExecutionException):
            self.checked.fetch_and_execute()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:30:54Z
# LAST_CHANGED: 2026-11-13T00:30:13Z
# CHANGE: Resolve [from:pretense_coverage] task_worker.execute.success_notification: drive reset at the execute boundary and assert processed_count, last_task_id, and is_busy telemetry after execute/fetch, registering the impl class key in singletons.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:30:54Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:30:37Z
# --- END AUTOFAB METADATA ---


# === File: task_worker_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import unittest

from pretense import (
    Domain,
    Env,
    StateMachine,
    require,
    require_arg,
    require_env,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from task_queue_deepseek_flash_1.parts.task_queue.lib.task_queue import TaskQueue
from task_queue_deepseek_flash_1.parts.task_queue.lib.task_worker import (
    TaskWorker,
    WorkerError,
    WorkerExecutionException,
)
from task_queue_deepseek_flash_1.parts.task_queue.pretense.task_queue_pretense import (
    make_task_queue_fake,
)


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class TaskWorkerState:
    """Model state for an autonomous task execution worker."""
    pending: list[str] = field(default_factory=list)
    failing: set[str] = field(default_factory=set)
    reports: dict[str, str] = field(default_factory=dict)
    processed: int = 0
    last_task: Optional[str] = None
    available: Env[bool] = True
    queue_empty: Env[bool] = True


class TaskWorkerStateMachine(StateMachine[TaskWorkerState]):
    """Pretense state machine modeling the TaskWorker interface contract."""

    def __init__(
        self,
        state: Optional[TaskWorkerState] = None,
        singletons: Optional[dict[type[object], object]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> TaskWorkerState:
        """Constructs the blank initial model state for a new task worker."""
        return TaskWorkerState()

    @transition(TaskWorker.execute)
    def execute(self, task_id: str, payload: str) -> str:
        """Executes a workload payload and reports completion to the queue."""
        require_arg(task_id, Domain.text(min_size=1), preferred=["task_1"])
        require_arg(payload, Domain.text(min_size=1), preferred=["payload_1"])
        require_env(
            self.state.available and task_id not in self.state.failing,
            WorkerExecutionException,
        )
        ret = self.inner_execute(task_id, payload)
        self.state.reports[task_id] = ret
        self.state.processed += 1
        self.state.last_task = task_id
        assert isinstance(ret, str)
        return ret

    def inner_execute(self, task_id: str, payload: str) -> str:
        """Computes the fake execution outcome from model state."""
        return f"outcome:{task_id}:{payload}"

    @transition(TaskWorker.fetch_and_execute)
    def fetch_and_execute(self) -> str:
        """Fetches the next pending task from the collaborator queue."""
        require(not self.state.queue_empty, WorkerError)
        require_env(self.state.available, WorkerExecutionException)
        ret = self.inner_fetch_and_execute()
        self.state.processed += 1
        self.state.last_task = ret
        assert isinstance(ret, str)
        return ret

    def inner_fetch_and_execute(self) -> str:
        """Computes the fake dispatched task identifier from model state."""
        return self.state.pending[0]

    @transition(TaskWorker.set_failing_task)
    def set_failing_task(self, task_id: str, failing: bool) -> None:
        """Test-only hook configuring designated tasks to fail on execution."""
        require_arg(task_id, Domain.text(min_size=1), preferred=["task_1"])
        require_arg(failing, Domain.sampled_from([True, False]), preferred=[True, False])
        self.inner_set_failing_task(task_id, failing)
        if failing:
            self.state.failing.add(task_id)
        else:
            self.state.failing.discard(task_id)
        assert (task_id in self.state.failing) == failing

    def inner_set_failing_task(self, task_id: str, failing: bool) -> None:
        """Computes the fake return value for set_failing_task."""
        return None

    @transition.seeding
    def seed_pending(self, task_id: str) -> None:
        """Seeds the worker model with one pending collaborator task."""
        self.state.pending.append(task_id)
        self.state.queue_empty = False
        assert task_id in self.state.pending


proto = TaskWorkerStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeTaskWorker = synthesize_fake(TaskWorkerStateMachine)


def make_task_worker_fake(
    state: Optional[TaskWorkerState] = None,
    queue: Optional[TaskQueue] = None,
) -> TaskWorker:
    """Synthesizes a fake TaskWorker wired to a fake collaborator task queue."""
    fake_queue = queue or make_task_queue_fake()
    return FakeTaskWorker(
        state=state or TaskWorkerState(),
        singletons={TaskQueue: fake_queue},
    )


FakeTaskWorkerFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeTaskWorkerFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

class TestTaskWorkerFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all declared transitions."""

    def setUp(self) -> None:
        self.queue = make_task_queue_fake()
        self.queue.submit("task_1", "payload_1")
        initial = TaskWorkerState()
        self.sm = TaskWorkerStateMachine(state=initial, singletons={TaskQueue: self.queue})
        self.worker = make_task_worker_fake(state=initial, queue=self.queue)
        self.sm.seed_pending("task_1")

    def test_seed_pending(self) -> None:
        """Exercises the seeding transition for a pending collaborator task."""
        self.sm.seed_pending("task_2")

    def test_execute(self) -> None:
        """Exercises execute against the fake worker."""
        self.worker.execute("task_1", "payload_1")

    def test_fetch_and_execute(self) -> None:
        """Exercises fetching a pending task from the fake collaborator queue."""
        assert self.worker.fetch_and_execute() == "task_1"

    def test_set_failing_task(self) -> None:
        """Exercises the failing task configuration hook."""
        self.worker.set_failing_task("task_1", True)
        self.worker.set_failing_task("task_1", False)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:27:05Z
# LAST_CHANGED: 2026-11-13T00:27:05Z
# CHANGE: Model TaskWorker (execute, fetch_and_execute, failing-task hook) with Env-backed availability/queue-emptiness, synthesized fake, seeding transition, fixed fake scenarios, and Hypothesis fake fuzzing.
# --- END AUTOFAB METADATA ---
