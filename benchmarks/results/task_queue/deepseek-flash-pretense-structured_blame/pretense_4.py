# === File: task_queue_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Optional

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleTestCase,
    get_default_registry,
    get_singleton,
    enter_phase,
    system,
)

from task_queue_deepseek_flash_1.parts.task_queue.lib.task_queue import (
    QueueEmptyError,
    QueueUnavailableException,
    TaskQueue,
)
from task_queue_deepseek_flash_1.parts.task_queue.lib.task_queue_impl import (
    QueueFullError,
    TaskQueue as TaskQueueImpl,
)
from task_queue_deepseek_flash_1.parts.task_queue.lib.task_worker import TaskWorker
from task_queue_deepseek_flash_1.parts.task_queue.lib.task_worker_impl import (
    TaskWorker as TaskWorkerImpl,
)
from task_queue_deepseek_flash_1.parts.task_queue.pretense import (
    task_queue_pretense as queue_pretense,
    task_worker_pretense as worker_pretense,
)

# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class TaskQueueImplPseudoStateMachine(queue_pretense.TaskQueueStateMachine):
    """Implementation pseudo-state machine binding the concrete bounded TaskQueue."""

    def __init__(
        self,
        state: Optional[queue_pretense.TaskQueueState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state, singletons=singletons)
        self.bind("available", lambda: sut(TaskQueueImpl).is_available)

    def inner_pending_count(self) -> int:
        target: TaskQueueImpl = sut(TaskQueueImpl)
        return target.pending_count

    def inner_submit(self, task_id: str, payload: str) -> None:
        target: TaskQueueImpl = sut(TaskQueueImpl)
        before = target.pending_count
        target.submit(task_id, payload)
        assert target.pending_count == before + 1
        assert target.is_full == (target.pending_count >= target.capacity)

    def inner_dispatch(self) -> str:
        target: TaskQueueImpl = sut(TaskQueueImpl)
        before = target.pending_count
        task_id = target.dispatch()
        assert target.pending_count == before - 1
        assert target.is_empty == (target.pending_count == 0)
        return task_id

    def inner_complete(self, task_id: str, outcome: str) -> None:
        target: TaskQueueImpl = sut(TaskQueueImpl)
        target.complete(task_id, outcome)
        assert target.get_outcome(task_id) == outcome

    def inner_get_outcome(self, task_id: str) -> Optional[str]:
        target: TaskQueueImpl = sut(TaskQueueImpl)
        return target.get_outcome(task_id)

    def inner_clear(self) -> None:
        target: TaskQueueImpl = sut(TaskQueueImpl)
        target.clear()
        assert target.pending_count == 0
        assert target.is_empty

    def inner_set_available(self, available: bool) -> None:
        target: TaskQueueImpl = sut(TaskQueueImpl)
        target.set_available(available)
        assert target.is_available == available


# ==============================================================================
# 2. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================

proto = TaskQueueImplPseudoStateMachine()


def make_sut() -> TaskQueueImpl:
    """Builds the concrete bounded queue with its faked worker collaborator registered."""
    registry = get_default_registry()
    registry.register_instance(
        worker_pretense.make_task_worker_fake(),
        keys=[TaskWorker],
        tier=system,
    )
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(TaskQueueImpl)


TaskQueueFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="TaskQueueFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Real Implementation (Implementation Components)
# ==============================================================================


class TestTaskQueueImplReal(LifecycleTestCase):
    """Deterministic queue scenarios exercising the concrete SUT and its worker collaborator."""

    target = TaskQueueImpl

    def setUp(self) -> None:
        super().setUp()
        self.worker = self.get_singleton(TaskWorkerImpl)
        self.registry.register_instance(
            self.worker,
            keys=[TaskWorker],
            tier=system,
        )
        self.queue_state = queue_pretense.TaskQueueState()
        self.sm = TaskQueueImplPseudoStateMachine(
            singletons={
                TaskQueue: self.sut,
                TaskQueueImpl: self.sut,
                queue_pretense.TaskQueueState: self.queue_state,
            }
        )
        self.checked = self.sm.as_checked(TaskQueue, self.sut)

    def test_submit_append_task(self) -> None:
        self.checked.submit("task-1", "alpha")
        assert self.sut.pending_count == 1
        assert self.sut.is_full is False

    def test_submit_unavailable_queue(self) -> None:
        self.sut.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.checked.submit("task-1", "alpha")

    def test_submit_capacity_overflow(self) -> None:
        for index in range(10):
            self.checked.submit(f"task-{index}", "alpha")
        self.checked.violating(QueueFullError).submit("task-overflow", "alpha")

    def test_dispatch_delegation(self) -> None:
        self.checked.submit("task-1", "alpha")
        assert self.checked.dispatch() == "task-1"
        assert self.sut.pending_count == 0

    def test_dispatch_unavailable_queue(self) -> None:
        self.checked.submit("task-1", "alpha")
        self.sut.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.checked.dispatch()

    def test_dispatch_empty_queue(self) -> None:
        self.checked.violating(QueueEmptyError).dispatch()

    def test_complete_unavailable_queue(self) -> None:
        self.sut.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.checked.complete("task-1", "PROCESSED:ALPHA")

    def test_clear_outcome_purge(self) -> None:
        self.checked.complete("task-1", "PROCESSED:ALPHA")
        self.checked.clear()
        assert self.checked.get_outcome("task-1") is None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T20:57:48Z
# LAST_CHANGED: 2026-11-13T20:57:12Z
# CHANGE: Fix unavailable dispatch scenario per pretense_qa: seed the queue with one pending task before toggling availability so the empty-queue require gate no longer precedes the availability precondition; the scenario now observes QueueUnavailableException (model_pending=1) instead of QueueEmptyError.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T20:57:48Z
# PRETENSE_QA_AUDIT: 2026-11-13T20:57:26Z
# --- END AUTOFAB METADATA ---


# === File: task_queue_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import unittest

from pretense import (
    Domain,
    Env,
    StateMachine,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
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
    """Canonical model state tracking pending tasks, outcomes, and availability."""

    pending: list[tuple[str, str]] = field(default_factory=list)
    outcomes: dict[str, str] = field(default_factory=dict)
    available: Env[bool] = True
    capacity: int = 10


class TaskQueueStateMachine(StateMachine[TaskQueueState]):
    """Unified Pretense State Machine for TaskQueue."""

    def __init__(
        self,
        state: Optional[TaskQueueState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    @property
    def default_capacity(self) -> int:
        """Open capacity parameter; pseudo-state machines may specialize this hook."""
        return 10

    def make_initial_state(self) -> TaskQueueState:
        """Constructs initial model state with an overridable bounded capacity."""
        return TaskQueueState(capacity=self.default_capacity)

    @transition(name="pending_count")
    def pending_count(self) -> int:
        ret = self.inner_pending_count()
        assert ret == len(self.state.pending)
        return ret

    def inner_pending_count(self) -> int:
        return len(self.state.pending)

    @transition(TaskQueue.submit)
    def submit(self, task_id: str, payload: str) -> None:
        require_env(self.state.available, QueueUnavailableException, task_id, payload)
        require(len(self.state.pending) < self.state.capacity)
        require_arg(task_id, Domain.text(min_size=1), preferred=["task-1"])
        require_arg(payload, Domain.text(min_size=1), preferred=["alpha"])
        self.inner_submit(task_id, payload)
        self.state.pending.append((task_id, payload))
        assert len(self.state.pending) <= self.state.capacity

    def inner_submit(self, task_id: str, payload: str) -> None:
        return None

    @transition(TaskQueue.dispatch)
    def dispatch(self) -> str:
        require_env(self.state.available, QueueUnavailableException)
        require(bool(self.state.pending), QueueEmptyError)
        ret = self.inner_dispatch()
        task_id, _payload = self.state.pending.pop(0)
        assert ret == task_id
        return ret

    def inner_dispatch(self) -> str:
        return self.state.pending[0][0]

    @transition(TaskQueue.complete)
    def complete(self, task_id: str, outcome: str) -> None:
        require_env(self.state.available, QueueUnavailableException, task_id, outcome)
        require_arg(task_id, Domain.text(min_size=1), preferred=["task-1"])
        require_arg(outcome, Domain.text(min_size=1), preferred=["PROCESSED:ALPHA"])
        self.inner_complete(task_id, outcome)
        self.state.outcomes[task_id] = outcome
        assert self.state.outcomes[task_id] == outcome

    def inner_complete(self, task_id: str, outcome: str) -> None:
        return None

    @transition(TaskQueue.get_outcome)
    def get_outcome(self, task_id: str) -> Optional[str]:
        require_arg(task_id, Domain.text(min_size=1), preferred=["task-1"])
        ret = self.inner_get_outcome(task_id)
        assert ret == self.state.outcomes.get(task_id)
        return ret

    def inner_get_outcome(self, task_id: str) -> Optional[str]:
        return self.state.outcomes.get(task_id)

    @transition(TaskQueue.clear)
    def clear(self) -> None:
        self.inner_clear()
        self.state.pending.clear()
        self.state.outcomes.clear()
        assert len(self.state.pending) == 0
        assert len(self.state.outcomes) == 0

    def inner_clear(self) -> None:
        return None

    @transition(TaskQueue.set_available)
    def set_available(self, available: bool) -> None:
        require_arg(available, Domain.sampled_from([True, False]), preferred=[True])
        self.inner_set_available(available)
        self.state.available = available

    def inner_set_available(self, available: bool) -> None:
        return None

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds a blank queue into the available, empty initial state."""
        self.state.available = True
        self.state.pending.clear()
        self.state.outcomes.clear()


proto = TaskQueueStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeTaskQueue = synthesize_fake(TaskQueueStateMachine)


def make_task_queue_fake(state: Optional[TaskQueueState] = None) -> TaskQueue:
    """Synthesizes a fake TaskQueue sharing the supplied model state."""
    return FakeTaskQueue(state=state or proto.make_initial_state())


FakeTaskQueueFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeTaskQueueFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestTaskQueueFake(unittest.TestCase):
    """Fixed fake tests covering every transition and the seeding transition."""

    def setUp(self) -> None:
        state = proto.make_initial_state()
        self.fake = make_task_queue_fake(state)
        self.sm = TaskQueueStateMachine(state=state, singletons={TaskQueue: self.fake})

    def test_seed_initial(self) -> None:
        self.sm.seed_initial()
        assert self.fake.pending_count == 0

    def test_pending_count(self) -> None:
        assert self.fake.pending_count == 0
        self.fake.submit("task-1", "alpha")
        assert self.fake.pending_count == 1

    def test_submit(self) -> None:
        self.fake.submit("task-1", "alpha")
        self.fake.submit("task-2", "beta")
        assert self.fake.pending_count == 2

    def test_dispatch(self) -> None:
        self.fake.submit("task-1", "alpha")
        assert self.fake.dispatch() == "task-1"
        assert self.fake.pending_count == 0

    def test_complete_and_get_outcome(self) -> None:
        self.fake.complete("task-1", "PROCESSED:ALPHA")
        assert self.fake.get_outcome("task-1") == "PROCESSED:ALPHA"
        assert self.fake.get_outcome("task-2") is None

    def test_clear(self) -> None:
        self.fake.submit("task-1", "alpha")
        self.fake.complete("task-1", "PROCESSED:ALPHA")
        self.fake.clear()
        assert self.fake.pending_count == 0
        assert self.fake.get_outcome("task-1") is None

    def test_set_available(self) -> None:
        self.fake.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.fake.submit("task-1", "alpha")
        self.fake.set_available(True)
        self.fake.submit("task-1", "alpha")
        assert self.fake.pending_count == 1

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T20:44:34Z
# LAST_CHANGED: 2026-11-13T20:44:34Z
# CHANGE: Model FIFO task queue interface: TaskQueueState (pending/outcomes/Env availability/bounded capacity), 1:1 transitions for pending_count, submit, dispatch, complete, get_outcome, clear, set_available plus seed_initial, synthesized FakeTaskQueue, fake fuzz test, and fixed fake tests covering every transition and seeding transition.
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Optional

from pretense import sut, sut_state
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleTestCase,
    get_default_registry,
    get_singleton,
    enter_phase,
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
from task_queue_deepseek_flash_1.parts.task_queue.pretense import (
    task_queue_pretense as queue_pretense,
    task_worker_pretense as worker_pretense,
)

# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class TaskWorkerImplPseudoStateMachine(worker_pretense.TaskWorkerStateMachine):
    """Implementation pseudo-state machine binding the concrete TaskWorker."""

    def __init__(
        self,
        state: Optional[worker_pretense.TaskWorkerState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state, singletons=singletons)
        self.bind(
            "queue_available",
            lambda: sut_state(queue_pretense.TaskQueueState).available,
        )

    def inner_execute(self, task_id: str, payload: str) -> str:
        target: TaskWorkerImpl = sut(TaskWorkerImpl)
        outcome = target.execute(task_id, payload)
        assert outcome == f"PROCESSED:{payload.upper()}"
        assert target.last_task_id == task_id
        assert target.is_busy is False
        assert target.processed_count >= 1
        return outcome

    def inner_fetch_and_execute(self) -> str:
        target: TaskWorkerImpl = sut(TaskWorkerImpl)
        task_id = target.fetch_and_execute()
        assert target.last_task_id == task_id
        assert target.is_busy is False
        return task_id

    def inner_set_failing_task(self, task_id: str, failing: bool) -> None:
        target: TaskWorkerImpl = sut(TaskWorkerImpl)
        target.set_failing_task(task_id, failing)


# ==============================================================================
# 2. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================

proto = TaskWorkerImplPseudoStateMachine()


def make_sut() -> TaskWorkerImpl:
    """Builds and registers the concrete worker under test with its queue collaborator."""
    registry = get_default_registry()
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(TaskWorkerImpl)


TaskWorkerFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    collaborators=[queue_pretense.TaskQueueStateMachine],
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="TaskWorkerFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Real Implementation (Implementation Components)
# ==============================================================================


class TestTaskWorkerImplReal(LifecycleTestCase):
    """Deterministic worker scenarios exercising the concrete SUT and its queue collaborator."""

    target = TaskWorkerImpl

    def setUp(self) -> None:
        super().setUp()
        self.queue = self.get_singleton(TaskQueueImpl)
        self.queue_state = queue_pretense.TaskQueueState()
        self.sm = TaskWorkerImplPseudoStateMachine(
            singletons={
                TaskWorker: self.sut,
                TaskWorkerImpl: self.sut,
                TaskQueueImpl: self.queue,
                queue_pretense.TaskQueueState: self.queue_state,
            }
        )
        self.checked = self.sm.as_checked(TaskWorker, self.sut)

    def test_execute_success_notification(self) -> None:
        self.checked.execute("task-1", "alpha")

    def test_execute_telemetry_reset(self) -> None:
        self.checked.execute("task-1", "alpha")
        self.sut.reset()
        assert self.sut.processed_count == 0
        assert self.sut.last_task_id is None
        assert self.sut.is_busy is False

    def test_execute_designated_failing_task(self) -> None:
        self.checked.set_failing_task("task-1", True)
        with self.assertRaises(WorkerExecutionException):
            self.checked.execute("task-1", "alpha")

    def test_execute_failing_task_deregistration(self) -> None:
        self.checked.set_failing_task("task-1", True)
        self.checked.set_failing_task("task-1", False)
        self.checked.execute("task-1", "alpha")
        assert self.sut.processed_count == 1

    def test_execute_unavailable_queue(self) -> None:
        self.queue.set_available(False)
        self.queue_state.available = False
        with self.assertRaises(WorkerExecutionException):
            self.checked.execute("task-1", "alpha")

    def test_fetch_and_execute_dispatched_task(self) -> None:
        fake_queue = queue_pretense.make_task_queue_fake(self.queue_state)
        self.registry.register_instance(fake_queue, keys=[TaskQueue], tier=system)
        fake_queue.submit("task-1", "alpha")
        assert self.checked.fetch_and_execute() == "task-1"
        assert self.sut.last_task_id == "task-1"
        assert self.sut.processed_count == 1

    def test_fetch_and_execute_empty_queue(self) -> None:
        self.queue_state.pending.append(("ghost-task", "ghost-payload"))
        self.checked.violating(WorkerError).fetch_and_execute()

    def test_fetch_unavailable_queue(self) -> None:
        self.queue_state.pending.append(("ghost-task", "ghost-payload"))
        self.queue.set_available(False)
        self.queue_state.available = False
        with self.assertRaises(WorkerExecutionException):
            self.checked.fetch_and_execute()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T20:55:35Z
# LAST_CHANGED: 2026-11-13T20:55:02Z
# CHANGE: Resolve pop-only collaborator dispatch facet: rewrite test_fetch_and_execute_dispatched_task to register a synthesized interface fake queue (whose dispatch only pops and returns the task id) under the TaskQueue protocol key, then seed it and drive checked.fetch_and_execute. This exercises the worker executing the dispatched task itself (single execution, processed_count == 1) rather than the real queue's dispatch delegating execution back to the worker.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T20:55:35Z
# PRETENSE_QA_AUDIT: 2026-11-13T20:55:23Z
# --- END AUTOFAB METADATA ---


# === File: task_worker_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import unittest

from pretense import (
    Domain,
    Env,
    StateMachine,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from task_queue_deepseek_flash_1.parts.task_queue.lib.task_queue import TaskQueue
from task_queue_deepseek_flash_1.parts.task_queue.lib.task_worker import (
    WorkerError,
    WorkerExecutionException,
    TaskWorker,
)
from task_queue_deepseek_flash_1.parts.task_queue.pretense.task_queue_pretense import (
    TaskQueueState,
    TaskQueueStateMachine,
    make_task_queue_fake,
)

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class TaskWorkerState:
    """Canonical model state tracking worker telemetry and queue availability."""

    processed_count: int = 0
    last_task_id: Optional[str] = None
    busy: bool = False
    failing_tasks: set[str] = field(default_factory=set)
    queue_available: Env[bool] = True


class TaskWorkerStateMachine(StateMachine[TaskWorkerState]):
    """Unified Pretense State Machine for TaskWorker."""

    def __init__(
        self,
        state: Optional[TaskWorkerState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> TaskWorkerState:
        """Constructs the blank initial worker telemetry state."""
        return TaskWorkerState()

    @transition(TaskWorker.execute)
    def execute(self, task_id: str, payload: str) -> str:
        require_env(
            self.state.queue_available and task_id not in self.state.failing_tasks,
            WorkerExecutionException,
            task_id,
            payload,
        )
        require_arg(task_id, Domain.text(min_size=1), preferred=["task-1"])
        require_arg(payload, Domain.text(min_size=1), preferred=["alpha"])
        ret = self.inner_execute(task_id, payload)
        self.state.last_task_id = task_id
        self.state.processed_count += 1
        self.state.busy = False
        assert ret == f"PROCESSED:{payload.upper()}"
        return ret

    def inner_execute(self, task_id: str, payload: str) -> str:
        return f"PROCESSED:{payload.upper()}"

    @transition(TaskWorker.fetch_and_execute)
    def fetch_and_execute(self) -> str:
        require_env(self.state.queue_available, WorkerExecutionException)
        require(bool(sut_state(TaskQueueState).pending), WorkerError)
        expected = sut_state(TaskQueueState).pending[0][0]
        ret = self.inner_fetch_and_execute()
        self.state.last_task_id = ret
        self.state.processed_count += 1
        self.state.busy = False
        assert ret == expected
        return ret

    def inner_fetch_and_execute(self) -> str:
        return sut_state(TaskQueueState).pending[0][0]

    @transition(TaskWorker.set_failing_task)
    def set_failing_task(self, task_id: str, failing: bool) -> None:
        require_arg(task_id, Domain.text(min_size=1), preferred=["task-1"])
        require_arg(failing, Domain.sampled_from([True, False]), preferred=[True])
        self.inner_set_failing_task(task_id, failing)
        if failing:
            self.state.failing_tasks.add(task_id)
        else:
            self.state.failing_tasks.discard(task_id)

    def inner_set_failing_task(self, task_id: str, failing: bool) -> None:
        return None

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds a blank worker and a single pending collaborator queue task."""
        self.state.processed_count = 0
        self.state.last_task_id = None
        self.state.busy = False
        self.state.failing_tasks.clear()
        self.state.queue_available = True
        sut_state(TaskQueueState).pending.clear()
        sut_state(TaskQueueState).pending.append(("seed-task", "seed-payload"))
        sut_state(TaskQueueState).outcomes.clear()


proto = TaskWorkerStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeTaskWorker = synthesize_fake(TaskWorkerStateMachine)


def make_task_worker_fake(
    state: Optional[TaskWorkerState] = None,
    queue_state: Optional[TaskQueueState] = None,
) -> TaskWorker:
    """Synthesizes a fake TaskWorker wired to a fake collaborator TaskQueue."""
    collaborator_state = queue_state or TaskQueueState()
    fake_queue = make_task_queue_fake(collaborator_state)
    return FakeTaskWorker(
        state=state or proto.make_initial_state(),
        singletons={
            TaskQueue: fake_queue,
            TaskQueueState: collaborator_state,
        },
    )


FakeTaskWorkerFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    collaborators=[TaskQueueStateMachine],
    initial_state_factory=proto.make_initial_state,
    name="FakeTaskWorkerFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestTaskWorkerFake(unittest.TestCase):
    """Fixed fake tests covering every transition and the seeding transition."""

    def setUp(self) -> None:
        state = proto.make_initial_state()
        queue_state = TaskQueueState()
        self.fake_queue = make_task_queue_fake(queue_state)
        self.singletons: dict[type[Any], Any] = {
            TaskQueue: self.fake_queue,
            TaskQueueState: queue_state,
        }
        self.fake = FakeTaskWorker(state=state, singletons=self.singletons)
        self.sm = TaskWorkerStateMachine(state=state, singletons=self.singletons)

    def test_seed_initial(self) -> None:
        self.fake.seed_initial()
        assert self.fake.processed_count == 0

    def test_execute(self) -> None:
        fake = make_task_worker_fake()
        assert fake.execute("task-1", "alpha") == "PROCESSED:ALPHA"

    def test_fetch_and_execute(self) -> None:
        self.fake_queue.submit("task-1", "alpha")
        assert self.fake.fetch_and_execute() == "task-1"
        assert self.fake.processed_count == 1
        assert self.fake.last_task_id == "task-1"

    def test_set_failing_task(self) -> None:
        self.fake.set_failing_task("task-1", True)
        with self.assertRaises(WorkerExecutionException):
            self.fake.execute("task-1", "alpha")
        self.fake.set_failing_task("task-1", False)
        assert self.fake.execute("task-1", "alpha") == "PROCESSED:ALPHA"

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T20:44:42Z
# LAST_CHANGED: 2026-11-13T20:44:42Z
# CHANGE: Model task worker interface: TaskWorkerState (telemetry, failing task set, Env queue availability), 1:1 transitions for execute, fetch_and_execute, set_failing_task plus seed_initial, collaborator queue state via sut_state with WorkerError/WorkerExecutionException operational gates, synthesized FakeTaskWorker, fake fuzz test, and fixed fake tests.
# --- END AUTOFAB METADATA ---
