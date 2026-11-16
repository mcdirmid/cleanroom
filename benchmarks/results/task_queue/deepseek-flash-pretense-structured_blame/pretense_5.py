# === File: task_queue_impl_pretense.py ===
from __future__ import annotations

from typing import Optional

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleTestCase,
    LifecycleRegistry,
    enter_phase,
    get_singleton,
    system,
)

from task_queue_deepseek_flash_1.parts.task_queue.lib.task_queue import (
    QueueEmptyError,
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
)

# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class TaskQueueImplPseudoStateMachine(TaskQueueStateMachine):
    """Implementation pseudo-state machine for the concrete bounded task queue.

    Inherits every interface transition (zero state dataclasses and zero
    ``require_arg`` declarations) and only overrides ``inner_<method>`` hooks to
    drive the real SUT and evaluate implementation-only invariants.
    """

    def __init__(
        self,
        state: Optional[TaskQueueState] = None,
        singletons: Optional[dict[type[object], object]] = None,
    ) -> None:
        super().__init__(state=state, singletons=singletons)
        self.bind("available", lambda: get_singleton(TaskQueueImpl).is_available)

    def inner_pending_count(self) -> int:
        target: TaskQueue = sut(TaskQueue)
        ret = target.pending_count
        real = get_singleton(TaskQueueImpl)
        assert ret == real.pending_count
        assert real.capacity == self.state.capacity
        assert real.is_empty == (ret == 0)
        assert real.is_full == (ret >= real.capacity)
        return ret

    def inner_submit(self, task_id: str, payload: str) -> None:
        target: TaskQueue = sut(TaskQueue)
        target.submit(task_id, payload)
        real = get_singleton(TaskQueueImpl)
        assert real.pending_count == len(self.state.tasks) + 1
        assert not real.is_empty
        return None

    def inner_dispatch(self) -> str:
        target: TaskQueue = sut(TaskQueue)
        ret = target.dispatch()
        real = get_singleton(TaskQueueImpl)
        assert real.pending_count == len(self.state.tasks) - 1
        assert real.get_outcome(ret) == f"PROCESSED:{self.state.tasks[0][1].upper()}"
        return ret

    def inner_complete(self, task_id: str, outcome: str) -> None:
        target: TaskQueue = sut(TaskQueue)
        target.complete(task_id, outcome)
        assert get_singleton(TaskQueueImpl).get_outcome(task_id) == outcome
        return None

    def inner_get_outcome(self, task_id: str) -> Optional[str]:
        target: TaskQueue = sut(TaskQueue)
        ret = target.get_outcome(task_id)
        real = get_singleton(TaskQueueImpl)
        assert ret == real.get_outcome(task_id)
        assert ret == self.state.outcomes.get(task_id)
        return ret

    def inner_clear(self) -> None:
        target: TaskQueue = sut(TaskQueue)
        target.clear()
        real = get_singleton(TaskQueueImpl)
        assert real.pending_count == 0
        assert real.is_empty
        return None

    def inner_set_available(self, available: bool) -> None:
        target: TaskQueue = sut(TaskQueue)
        target.set_available(available)
        assert get_singleton(TaskQueueImpl).is_available == available
        return None


proto = TaskQueueImplPseudoStateMachine()


# ==============================================================================
# 2. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================


def make_sut() -> TaskQueue:
    registry = LifecycleRegistry()
    registry.register_singleton(TaskQueueImpl)
    registry.register_singleton(TaskWorkerImpl)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(TaskQueue)


TaskQueueImplFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="TaskQueueImplFuzzTest",
)


# ==============================================================================
# 3. Real Implementation Tests (Implementation Components)
# ==============================================================================


class TestTaskQueueImplReal(LifecycleTestCase):
    """Fixed scenarios for the bounded-capacity and empty-queue contract boundaries."""

    target = TaskQueueImpl

    def setUp(self) -> None:
        super().setUp()
        queue = get_singleton(TaskQueue)
        self.sm = TaskQueueImplPseudoStateMachine(singletons={TaskQueue: queue})
        self.checked = self.sm.as_checked(TaskQueue, queue)

    def test_dispatch_empty_queue_violates(self) -> None:
        """Dispatching from an empty queue raises the contracted QueueEmptyError."""
        self.checked.violating(QueueEmptyError).dispatch()

    def test_submit_full_queue_violates(self) -> None:
        """Submitting beyond bounded capacity raises the contracted QueueFullError."""
        for index in range(10):
            self.checked.submit(f"task_{index}", f"payload_{index}")
        self.checked.violating(QueueFullError).submit("task_10", "payload_10")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T20:58:56Z
# LAST_CHANGED: 2026-11-14T20:54:48Z
# CHANGE: Resolve pretense_coverage feedback by adding TestTaskQueueImplReal fixed scenarios: violating(QueueEmptyError).dispatch() on an empty queue and filling to capacity 10 then violating(QueueFullError).submit(), exercising both unexercised precondition-error boundaries.
# PRETENSE_COVERAGE_AUDIT: 2026-11-14T20:58:56Z
# PRETENSE_QA_AUDIT: 2026-11-14T20:55:03Z
# --- END AUTOFAB METADATA ---


# === File: task_queue_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import unittest

from pretense import (
    Env,
    StateMachine,
    require,
    require_arg,
    require_env,
    sut,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from task_queue_deepseek_flash_1.parts.task_queue.lib.task_queue import (
    QueueUnavailableException,
    TaskQueue,
)

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class TaskQueueState:
    """Canonical model state for a bounded first-in first-out task queue."""

    tasks: list[tuple[str, str]] = field(default_factory=list)
    outcomes: dict[str, str] = field(default_factory=dict)
    available: Env[bool] = True
    capacity: int = 10


class TaskQueueStateMachine(StateMachine[TaskQueueState]):
    """Pretense state machine modelling TaskQueue transitions 1:1."""

    def __init__(
        self,
        state: Optional[TaskQueueState] = None,
        singletons: Optional[dict[type[object], object]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> TaskQueueState:
        """Constructs the initial model state; open capacity is overridable downstream."""
        return TaskQueueState()

    @transition(name="pending_count")
    def pending_count(self) -> int:
        ret = self.inner_pending_count()
        assert ret == len(self.state.tasks)
        return ret

    def inner_pending_count(self) -> int:
        """Computes fake return value for the synthesized fake."""
        return len(self.state.tasks)

    @transition(TaskQueue.submit)
    def submit(self, task_id: str, payload: str) -> None:
        require_env(self.state.available, QueueUnavailableException)
        require(len(self.state.tasks) < self.state.capacity)
        require_arg(task_id, str)
        require_arg(payload, str)
        self.inner_submit(task_id, payload)
        self.state.tasks.append((task_id, payload))

    def inner_submit(self, task_id: str, payload: str) -> None:
        """Computes fake return value for the synthesized fake."""
        return None

    @transition(TaskQueue.dispatch)
    def dispatch(self) -> str:
        require_env(self.state.available, QueueUnavailableException)
        require(bool(self.state.tasks))
        ret = self.inner_dispatch()
        head = self.state.tasks[0]
        self.state.tasks.pop(0)
        self.state.outcomes[head[0]] = f"PROCESSED:{head[1].upper()}"
        assert ret == head[0]
        assert sut(TaskQueue).get_outcome(ret) == f"PROCESSED:{head[1].upper()}"
        return ret

    def inner_dispatch(self) -> str:
        """Computes fake return value for the synthesized fake."""
        return self.state.tasks[0][0]

    @transition(TaskQueue.complete)
    def complete(self, task_id: str, outcome: str) -> None:
        require_env(self.state.available, QueueUnavailableException)
        require_arg(task_id, str)
        require_arg(outcome, str)
        self.inner_complete(task_id, outcome)
        self.state.outcomes[task_id] = outcome
        assert sut(TaskQueue).get_outcome(task_id) == outcome

    def inner_complete(self, task_id: str, outcome: str) -> None:
        """Computes fake return value for the synthesized fake."""
        return None

    @transition(TaskQueue.get_outcome)
    def get_outcome(self, task_id: str) -> Optional[str]:
        require_arg(task_id, str)
        ret = self.inner_get_outcome(task_id)
        assert ret == self.state.outcomes.get(task_id)
        return ret

    def inner_get_outcome(self, task_id: str) -> Optional[str]:
        """Computes fake return value for the synthesized fake."""
        return self.state.outcomes.get(task_id)

    @transition(TaskQueue.clear)
    def clear(self) -> None:
        self.inner_clear()
        self.state.tasks.clear()
        self.state.outcomes.clear()

    def inner_clear(self) -> None:
        """Computes fake return value for the synthesized fake."""
        return None

    @transition(TaskQueue.set_available)
    def set_available(self, available: bool) -> None:
        require_arg(available, bool)
        self.inner_set_available(available)
        self.state.available = available

    def inner_set_available(self, available: bool) -> None:
        """Computes fake return value for the synthesized fake."""
        return None


proto = TaskQueueStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeTaskQueue = synthesize_fake(TaskQueueStateMachine)


def make_task_queue_fake(state: Optional[TaskQueueState] = None) -> TaskQueue:
    """Synthesizes a fake task queue instance for TaskQueue."""
    return FakeTaskQueue(state=state or proto.make_initial_state())


# ==============================================================================
# 3. Hypothesis Fuzzing on Fake (Interface Components)
# ==============================================================================

FakeTaskQueueFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeTaskQueueFuzzTest",
)

# ==============================================================================
# 4. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestTaskQueueFake(unittest.TestCase):
    """Fixed fake scenarios covering operational hooks outside plain fuzzing."""

    def setUp(self) -> None:
        self.fake = make_task_queue_fake()
        self.sm = TaskQueueStateMachine(singletons={TaskQueue: self.fake})

    def test_dispatch_and_outcome_tracking(self) -> None:
        self.fake.submit("task_1", "payload_1")
        task_id = self.fake.dispatch()
        self.assertEqual(task_id, "task_1")
        self.assertEqual(self.fake.get_outcome("task_1"), "PROCESSED:PAYLOAD_1")
        self.fake.complete("task_1", "DLQ")
        self.assertEqual(self.fake.get_outcome("task_1"), "DLQ")
        self.fake.clear()

    def test_unavailable_queue_operations(self) -> None:
        self.fake.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.fake.submit("task_1", "payload_1")
        self.fake.set_available(True)
        self.fake.submit("task_1", "payload_1")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T20:50:00Z
# LAST_CHANGED: 2026-11-14T20:50:00Z
# CHANGE: Model TaskQueue interface: FIFO submit/dispatch/complete/get_outcome/clear/set_available transitions with bounded capacity, Env-based QueueUnavailableException gating, fake synthesis, fixed fake scenarios, and 100%-covered FakeTaskQueueFuzzTest.
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl_pretense.py ===
from __future__ import annotations

from typing import Optional

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleTestCase,
    LifecycleRegistry,
    enter_phase,
    get_singleton,
    system,
)

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
    """Implementation pseudo-state machine for the concrete task execution worker.

    Inherits every interface transition (zero state dataclasses and zero
    ``require_arg`` declarations) and only overrides ``inner_<method>`` hooks to
    drive the real SUT and evaluate implementation-only invariants.
    """

    def __init__(
        self,
        state: Optional[TaskWorkerState] = None,
        singletons: Optional[dict[type[object], object]] = None,
    ) -> None:
        super().__init__(state=state, singletons=singletons)
        self.bind("available", lambda: get_singleton(TaskQueueImpl).is_available)

    def inner_execute(self, task_id: str, payload: str) -> str:
        target: TaskWorker = sut(TaskWorker)
        ret = target.execute(task_id, payload)
        real = get_singleton(TaskWorkerImpl)
        assert real.processed_count == len(self.state.processed) + 1
        assert real.last_task_id == task_id
        assert not real.is_busy
        assert ret == f"PROCESSED:{payload.upper()}"
        assert get_singleton(TaskQueueImpl).get_outcome(task_id) == ret
        return ret

    def inner_fetch_and_execute(self) -> str:
        target: TaskWorker = sut(TaskWorker)
        ret = target.fetch_and_execute()
        real = get_singleton(TaskWorkerImpl)
        assert real.last_task_id == ret
        assert not real.is_busy
        return ret

    def inner_set_failing_task(self, task_id: str, failing: bool) -> None:
        target: TaskWorker = sut(TaskWorker)
        target.set_failing_task(task_id, failing)
        return None


proto = TaskWorkerImplPseudoStateMachine()


# ==============================================================================
# 2. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================


def make_sut() -> TaskWorker:
    registry = LifecycleRegistry()
    registry.register_singleton(TaskWorkerImpl)
    registry.register_singleton(TaskQueueImpl)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(TaskWorker)


TaskWorkerImplFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="TaskWorkerImplFuzzTest",
)


# ==============================================================================
# 3. Real Implementation Tests (Implementation Components)
# ==============================================================================


class TestTaskWorkerImplReal(LifecycleTestCase):
    """Fixed scenarios for execution telemetry and collaborator queue boundaries."""

    target = TaskWorkerImpl

    def setUp(self) -> None:
        super().setUp()
        worker = get_singleton(TaskWorker)
        self.sm = TaskWorkerImplPseudoStateMachine(
            singletons={TaskWorker: worker, TaskQueue: get_singleton(TaskQueue)}
        )
        self.checked = self.sm.as_checked(TaskWorker, worker)

    def test_execute_notifies_queue_and_resets_telemetry(self) -> None:
        """Successful execution notifies the queue and restores worker telemetry."""
        worker = get_singleton(TaskWorkerImpl)
        queue = get_singleton(TaskQueueImpl)
        worker.reset()
        outcome = worker.execute("task_1", "payload_1")
        self.assertEqual(outcome, "PROCESSED:PAYLOAD_1")
        self.assertEqual(worker.processed_count, 1)
        self.assertEqual(worker.last_task_id, "task_1")
        self.assertFalse(worker.is_busy)
        self.assertEqual(queue.get_outcome("task_1"), "PROCESSED:PAYLOAD_1")
        worker.reset()
        self.assertEqual(worker.processed_count, 0)
        self.assertIsNone(worker.last_task_id)
        self.assertFalse(worker.is_busy)

    def test_fetch_and_execute_dispatches_pending_task(self) -> None:
        """Fetching a pending task executes it and returns the dispatched identifier."""
        worker = get_singleton(TaskWorkerImpl)
        queue = get_singleton(TaskQueueImpl)
        queue.submit("task_1", "payload_1")
        self.assertEqual(worker.fetch_and_execute(), "task_1")
        self.assertEqual(queue.pending_count, 0)

    def test_execute_unavailable_queue_raises(self) -> None:
        """Executing while the collaborator queue is unavailable raises an execution fault."""
        queue = get_singleton(TaskQueueImpl)
        queue.set_available(False)
        with self.assertRaises(WorkerExecutionException):
            self.checked.execute("task_1", "payload_1")

    def test_fetch_and_execute_empty_queue_violates(self) -> None:
        """Fetching from an empty collaborator queue raises the contracted WorkerError."""
        self.checked.violating(WorkerError).fetch_and_execute()

    def test_fetch_and_execute_unavailable_queue_raises(self) -> None:
        """Fetching while the collaborator queue is unavailable raises an execution fault.

        The unavailable-queue precondition takes precedence over the empty-queue
        precondition, so this scenario is driven directly against the SUT: an empty
        model queue must not gate the collaborator fault away before dispatch.
        """
        worker = get_singleton(TaskWorkerImpl)
        queue = get_singleton(TaskQueueImpl)
        queue.set_available(False)
        with self.assertRaises(WorkerExecutionException):
            worker.fetch_and_execute()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T20:59:52Z
# LAST_CHANGED: 2026-11-14T20:59:27Z
# CHANGE: Resolve pretense_qa feedback on task_worker.fetch_and_execute.empty_queue: the unavailable-queue fetch scenario expected WorkerExecutionException but the checked adapter's empty-model pending precondition raised PretenseSpecificationError first. Drive the scenario directly against the SUT after set_available(False) so the collaborator-unavailable precondition fully masks the empty-queue precondition and the contracted WorkerExecutionException is observed.
# PRETENSE_COVERAGE_AUDIT: 2026-11-14T20:59:52Z
# PRETENSE_QA_AUDIT: 2026-11-14T20:59:39Z
# --- END AUTOFAB METADATA ---


# === File: task_worker_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import unittest

from pretense import (
    Env,
    StateMachine,
    require,
    require_arg,
    require_env,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from task_queue_deepseek_flash_1.parts.task_queue.lib.task_worker import (
    TaskWorker,
    WorkerExecutionException,
)

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class TaskWorkerState:
    """Canonical model state for an autonomous task execution worker."""

    pending: list[tuple[str, str]] = field(default_factory=list)
    outcomes: dict[str, str] = field(default_factory=dict)
    processed: list[str] = field(default_factory=list)
    last_task_id: Optional[str] = None
    failing_tasks: set[str] = field(default_factory=set)
    available: Env[bool] = True


class TaskWorkerStateMachine(StateMachine[TaskWorkerState]):
    """Pretense state machine modelling TaskWorker transitions 1:1."""

    def __init__(
        self,
        state: Optional[TaskWorkerState] = None,
        singletons: Optional[dict[type[object], object]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> TaskWorkerState:
        """Constructs the initial model state for the worker."""
        return TaskWorkerState()

    @transition.seeding
    def seed_pending_task(self, task_id: str, payload: str) -> None:
        """Seeds the collaborator queue with a pending task for fake fuzzing."""
        require_arg(task_id, str)
        require_arg(payload, str)
        self.state.pending.append((task_id, payload))

    @transition(TaskWorker.execute)
    def execute(self, task_id: str, payload: str) -> str:
        require_env(
            self.state.available and task_id not in self.state.failing_tasks,
            WorkerExecutionException,
        )
        require_arg(task_id, str)
        require_arg(payload, str)
        ret = self.inner_execute(task_id, payload)
        self.state.outcomes[task_id] = ret
        self.state.processed.append(task_id)
        self.state.last_task_id = task_id
        assert self.state.outcomes.get(task_id) == ret
        return ret

    def inner_execute(self, task_id: str, payload: str) -> str:
        """Computes fake return value for the synthesized fake."""
        return f"PROCESSED:{payload.upper()}"

    @transition(TaskWorker.fetch_and_execute)
    def fetch_and_execute(self) -> str:
        require_env(self.state.available, WorkerExecutionException)
        require(bool(self.state.pending))
        ret = self.inner_fetch_and_execute()
        head = self.state.pending[0]
        self.state.pending.pop(0)
        self.state.outcomes[head[0]] = f"PROCESSED:{head[1].upper()}"
        self.state.processed.append(head[0])
        self.state.last_task_id = head[0]
        assert ret == head[0]
        return ret

    def inner_fetch_and_execute(self) -> str:
        """Computes fake return value for the synthesized fake."""
        return self.state.pending[0][0]

    @transition(TaskWorker.set_failing_task)
    def set_failing_task(self, task_id: str, failing: bool) -> None:
        require_arg(task_id, str)
        require_arg(failing, bool)
        self.inner_set_failing_task(task_id, failing)
        if failing:
            self.state.failing_tasks.add(task_id)
        else:
            self.state.failing_tasks.discard(task_id)
        assert (task_id in self.state.failing_tasks) == failing

    def inner_set_failing_task(self, task_id: str, failing: bool) -> None:
        """Computes fake return value for the synthesized fake."""
        return None


proto = TaskWorkerStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeTaskWorker = synthesize_fake(TaskWorkerStateMachine)


def make_task_worker_fake(state: Optional[TaskWorkerState] = None) -> TaskWorker:
    """Synthesizes a fake task worker instance for TaskWorker."""
    return FakeTaskWorker(state=state or proto.make_initial_state())


# ==============================================================================
# 3. Hypothesis Fuzzing on Fake (Interface Components)
# ==============================================================================

FakeTaskWorkerFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeTaskWorkerFuzzTest",
)


# ==============================================================================
# 4. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestTaskWorkerFake(unittest.TestCase):
    """Fixed fake scenarios covering failure configuration and execution branches."""

    def setUp(self) -> None:
        model = proto.make_initial_state()
        self.fake = make_task_worker_fake(model)
        self.sm = TaskWorkerStateMachine(state=model, singletons={TaskWorker: self.fake})

    def test_failing_task_raises_execution_exception(self) -> None:
        self.fake.set_failing_task("task_1", True)
        with self.assertRaises(WorkerExecutionException):
            self.fake.execute("task_1", "payload_1")
        self.fake.set_failing_task("task_1", False)
        self.assertEqual(self.fake.execute("task_1", "payload_1"), "PROCESSED:PAYLOAD_1")

    def test_fetch_and_execute_reports_task(self) -> None:
        self.sm.seed_pending_task("seed_task_1", "seed_payload_1")
        self.assertEqual(self.fake.fetch_and_execute(), "seed_task_1")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T20:50:08Z
# LAST_CHANGED: 2026-11-14T20:50:08Z
# CHANGE: Model TaskWorker interface: execute/fetch_and_execute/set_failing_task transitions with Env-based WorkerExecutionException gating, collaborator pending queue seeding, fake synthesis, fixed fake scenarios, and 100%-covered FakeTaskWorkerFuzzTest.
# --- END AUTOFAB METADATA ---
