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
from benchmark_4.parts.task_queue.pretense.task_queue_pretense import (
    FakeTaskQueue,
    TaskQueueState,
    TaskQueueStateMachine,
    make_task_queue_fake,
)
from benchmark_4.parts.task_queue.lib.task_queue import QueueUnavailableException
from benchmark_4.parts.task_queue.lib.task_queue_impl import TaskQueue, __initialize__
from benchmark_4.parts.task_queue.lib.task_worker_impl import (
    TaskWorker,
    __initialize__ as initialize_task_worker,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================


class TaskQueueImplPseudoStateMachine(TaskQueueStateMachine):
    """Implementation pseudo-state machine for TaskQueue."""

    @transition(TaskQueue.submit)
    def submit(self, task_id: str, payload: str) -> Any:
        target: TaskQueue = sut(TaskQueue)
        previous = target.pending_count
        ret = call_target(target.submit(task_id, payload))
        assert target.pending_count == previous + 1
        assert target.is_available
        return ret

    @transition(TaskQueue.dispatch)
    def dispatch(self) -> Any:
        target: TaskQueue = sut(TaskQueue)
        previous = target.pending_count
        ret = call_target(target.dispatch())
        assert target.pending_count == previous - 1
        assert isinstance(ret, str)
        return ret

    @transition(TaskQueue.complete)
    def complete(self, task_id: str, outcome: str) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(target.complete(task_id, outcome))
        assert target.get_outcome(task_id) == outcome
        return ret

    @transition(TaskQueue.get_outcome)
    def get_outcome(self, task_id: str) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(target.get_outcome(task_id))
        assert ret == target.get_outcome(task_id)
        return ret

    @transition(TaskQueue.clear)
    def clear(self) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(target.clear())
        assert target.pending_count == 0
        assert target.is_empty
        return ret

    @transition(TaskQueue.set_available)
    def set_available(self, available: bool) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(target.set_available(available))
        assert target.is_available == available
        return ret

    @transition(name="capacity")
    def capacity(self) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(target.capacity)
        assert ret >= 1
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(target.is_empty)
        assert ret == (target.pending_count == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(target.is_full)
        assert ret == (target.pending_count >= target.capacity)
        return ret

    @transition(name="is_available")
    def is_available(self) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(target.is_available)
        assert isinstance(ret, bool)
        return ret

    @transition(name="pending_count")
    def pending_count(self) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(target.pending_count)
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
        __initialize__(self.registry)
        initialize_task_worker(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(TaskQueue)
        self.worker = get_singleton(TaskWorker)
        self.sm = TaskQueueImplPseudoStateMachine(
            singletons={TaskQueue: self.real, TaskWorker: self.worker}
        )
        self.checked = self.sm.as_checked(TaskQueue, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        assert self.checked.pending_count == 0
        assert self.checked.is_empty
        assert self.checked.capacity >= 1
        assert self.checked.is_available
        assert not self.checked.is_full
        self.checked.submit("t1", "payload-1")
        self.checked.submit("t2", "payload-2")
        assert self.checked.pending_count == 2
        assert not self.checked.is_empty
        assert self.checked.dispatch() == "t1"
        assert self.checked.pending_count == 1
        assert self.checked.get_outcome("t1") == "PROCESSED:PAYLOAD-1"
        self.checked.complete("t1", "DONE")
        assert self.checked.get_outcome("t1") == "DONE"
        assert self.checked.get_outcome("t2") is None
        self.checked.clear()
        assert self.checked.pending_count == 0
        assert self.checked.is_empty
        assert self.checked.get_outcome("t2") is None
        self.checked.set_available(False)
        assert not self.checked.is_available
        with self.assertRaises(QueueUnavailableException):
            self.checked.submit("t3", "payload-3")
        self.checked.set_available(True)
        assert self.checked.is_available


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================


def make_sut() -> TaskQueue:
    registry = LifecycleRegistry()
    __initialize__(registry)
    initialize_task_worker(registry)
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
# LAST_CLEANED: 2026-11-04T17:03:06Z
# LAST_CHANGED: 2026-11-04T16:56:25Z
# CHANGE: Implement TaskQueue implementation pseudo-state machine: transition overrides via call_target asserting real SUT postconditions, impl-only property transitions, lifecycle-backed real conformance scenarios, and real Hypothesis fuzz compilation.
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T17:03:06Z
# PRETENSE_QA_AUDIT: 2026-11-04T17:02:54Z
# --- END AUTOFAB METADATA ---


# === File: task_queue_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for TaskQueue."""

from __future__ import annotations

from dataclasses import dataclass, field
import unittest
from typing import Optional

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
from benchmark_4.parts.task_queue.lib.task_queue import (
    QueueUnavailableException,
    TaskQueue,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================


@dataclass
class TaskQueueState:
    """Canonical model state for TaskQueue operations."""

    entries: list[tuple[str, str]] = field(default_factory=list)
    outcomes: dict[str, str] = field(default_factory=dict)
    available: bool = True
    capacity: int = 10


class TaskQueueStateMachine(StateMachine[TaskQueueState]):
    """Unified Pretense State Machine for TaskQueue."""

    def __init__(
        self,
        state: Optional[TaskQueueState] = None,
        singletons: Optional[dict[type[object], object]] = None,
    ) -> None:
        super().__init__(state=state or TaskQueueState(), singletons=singletons)

    @transition(TaskQueue.submit)
    def submit(self, task_id: str, payload: str) -> None:
        require_arg(task_id, Domain.type(str), preferred=["task-1"])
        require_arg(payload, Domain.type(str), preferred=["payload"])
        require(len(self.state.entries) < self.state.capacity)
        ret: None = None
        if not self.state.available:
            with raises(QueueUnavailableException):
                ret = make_return_value(None)
            return ret
        ret = make_return_value(None)
        self.state.entries.append((task_id, payload))
        assert self.state.entries[-1] == (task_id, payload)
        return ret

    @transition(TaskQueue.dispatch)
    def dispatch(self) -> str:
        require(len(self.state.entries) > 0)
        ret: str = ""
        if not self.state.available:
            with raises(QueueUnavailableException):
                ret = make_return_value("")
            return ret
        ret = make_return_value(self.state.entries[0][0])
        self.state.entries.pop(0)
        assert isinstance(ret, str)
        return ret

    @transition(TaskQueue.complete)
    def complete(self, task_id: str, outcome: str) -> None:
        require_arg(task_id, Domain.type(str), preferred=["task-1"])
        require_arg(outcome, Domain.type(str), preferred=["DONE"])
        ret: None = None
        if not self.state.available:
            with raises(QueueUnavailableException):
                ret = make_return_value(None)
            return ret
        ret = make_return_value(None)
        self.state.outcomes[task_id] = outcome
        assert self.state.outcomes.get(task_id) == outcome
        return ret

    @transition(TaskQueue.get_outcome)
    def get_outcome(self, task_id: str) -> Optional[str]:
        require_arg(task_id, Domain.type(str), preferred=["task-1"])
        ret = make_return_value(self.state.outcomes.get(task_id))
        assert ret is None or isinstance(ret, str)
        return ret

    @transition(TaskQueue.clear)
    def clear(self) -> None:
        ret = make_return_value(None)
        self.state.entries.clear()
        self.state.outcomes.clear()
        assert len(self.state.entries) == 0
        assert len(self.state.outcomes) == 0
        return ret

    @transition(TaskQueue.set_available)
    def set_available(self, available: bool) -> None:
        require_arg(available, Domain.boolean())
        ret = make_return_value(None)
        self.state.available = available
        assert self.state.available == available
        return ret

    @transition(name="pending_count")
    def pending_count(self) -> int:
        ret = make_return_value(len(self.state.entries))
        assert isinstance(ret, int)
        return ret

    @transition.seeding
    def seed_available(self) -> None:
        """Seeds the model into an available task queue."""
        self.state.available = True


proto = TaskQueueStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeTaskQueue = synthesize_fake(TaskQueueStateMachine)


def make_task_queue_fake(state: Optional[TaskQueueState] = None) -> TaskQueue:
    """Creates a synthesized TaskQueue fake over the given (or blank) model state."""
    return FakeTaskQueue(state=state or TaskQueueState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================


class TestTaskQueueFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all declared transitions."""

    def setUp(self) -> None:
        self.fake = make_task_queue_fake()
        self.sm = TaskQueueStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises every transition and seeding transition of the fake."""
        self.sm.seed_available()
        assert self.sm.pending_count() == 0
        assert self.fake.pending_count == 0
        self.fake.submit("t1", "payload")
        assert self.fake.pending_count == 1
        assert self.fake.dispatch() == "t1"
        assert self.fake.pending_count == 0
        self.fake.submit("t2", "payload-2")
        self.fake.complete("t2", "DONE")
        assert self.fake.get_outcome("t2") == "DONE"
        self.fake.clear()
        assert self.fake.get_outcome("t2") is None
        self.fake.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.fake.submit("t3", "payload-3")
        self.fake.set_available(True)
        assert self.fake.get_outcome("t3") is None


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeTaskQueueFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=TaskQueueState,
    name="FakeTaskQueueFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T16:56:10Z
# LAST_CHANGED: 2026-11-04T16:56:10Z
# CHANGE: Implement TaskQueue interface Pretense state machine: FIFO model state, 1:1 transitions with domain contracts, unavailable operational exception branches, seeding transition, synthesized fake factory, fixed fake coverage suite, and fake Hypothesis fuzz compilation.
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for TaskWorker."""

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
from benchmark_4.parts.task_queue.pretense.task_queue_pretense import (
    TaskQueueState,
    TaskQueueStateMachine,
    FakeTaskQueue,
    make_task_queue_fake,
)
from benchmark_4.parts.task_queue.pretense.task_worker_pretense import (
    FakeTaskWorker,
    TaskWorkerState,
    TaskWorkerStateMachine,
    make_task_worker_fake,
)
from benchmark_4.parts.task_queue.lib.task_worker import WorkerExecutionException
from benchmark_4.parts.task_queue.lib.task_worker_impl import TaskWorker, __initialize__
from benchmark_4.parts.task_queue.lib.task_queue_impl import (
    TaskQueue,
    __initialize__ as initialize_task_queue,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================


class TaskWorkerImplPseudoStateMachine(TaskWorkerStateMachine):
    """Implementation pseudo-state machine for TaskWorker."""

    @transition(TaskWorker.reset)
    def reset(self) -> Any:
        target: TaskWorker = sut(TaskWorker)
        ret = call_target(target.reset())
        assert target.processed_count == 0
        assert target.last_task_id is None
        assert not target.is_busy
        return ret

    @transition(TaskWorker.execute)
    def execute(self, task_id: str, payload: str) -> Any:
        target: TaskWorker = sut(TaskWorker)
        previous = target.processed_count
        ret = call_target(target.execute(task_id, payload))
        assert target.processed_count == previous + 1
        assert target.last_task_id == task_id
        assert not target.is_busy
        assert ret == f"PROCESSED:{payload.upper()}"
        return ret

    @transition(TaskWorker.fetch_and_execute)
    def fetch_and_execute(self) -> Any:
        target: TaskWorker = sut(TaskWorker)
        ret = call_target(target.fetch_and_execute())
        assert isinstance(ret, str)
        assert target.last_task_id == ret
        return ret

    @transition(TaskWorker.set_failing_task)
    def set_failing_task(self, task_id: str, failing: bool) -> Any:
        target: TaskWorker = sut(TaskWorker)
        ret = call_target(target.set_failing_task(task_id, failing))
        return ret

    @transition(name="processed_count")
    def processed_count(self) -> Any:
        target: TaskWorker = sut(TaskWorker)
        ret = call_target(target.processed_count)
        assert ret >= 0
        return ret

    @transition(name="last_task_id")
    def last_task_id(self) -> Any:
        target: TaskWorker = sut(TaskWorker)
        ret = call_target(target.last_task_id)
        assert ret is None or isinstance(ret, str)
        return ret

    @transition(name="is_busy")
    def is_busy(self) -> Any:
        target: TaskWorker = sut(TaskWorker)
        ret = call_target(target.is_busy)
        assert isinstance(ret, bool)
        return ret


proto = TaskWorkerImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================


class TestTaskWorkerImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies the contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        initialize_task_queue(self.registry)
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.queue = get_singleton(TaskQueue)
        self.real = get_singleton(TaskWorker)
        self.sm = TaskWorkerImplPseudoStateMachine(
            singletons={TaskWorker: self.real, TaskQueue: self.queue}
        )
        self.checked = self.sm.as_checked(TaskWorker, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        assert self.checked.processed_count == 0
        assert self.checked.last_task_id is None
        assert not self.checked.is_busy
        assert self.checked.execute("t1", "payload") == "PROCESSED:PAYLOAD"
        assert self.checked.processed_count == 1
        assert self.checked.last_task_id == "t1"
        assert not self.checked.is_busy
        self.checked.set_failing_task("bad", True)
        with self.assertRaises(WorkerExecutionException):
            self.checked.execute("bad", "payload")
        self.checked.set_failing_task("bad", False)
        assert self.checked.execute("bad", "payload") == "PROCESSED:PAYLOAD"
        self.checked.reset()
        assert self.checked.processed_count == 0
        assert self.checked.last_task_id is None
        assert not self.checked.is_busy
        self.queue.submit("t9", "payload-9")
        self.sm.seed_pending_task()
        assert self.checked.fetch_and_execute() == "t9"
        assert self.checked.last_task_id == "t9"
        assert self.checked.processed_count >= 1
        self.queue.set_available(False)
        with self.assertRaises(WorkerExecutionException):
            self.checked.execute("t10", "payload-10")
        self.queue.set_available(True)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================


def make_sut() -> TaskWorker:
    registry = LifecycleRegistry()
    initialize_task_queue(registry)
    __initialize__(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(TaskWorker)


TaskWorkerFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=TaskWorkerState,
    name="TaskWorkerFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T17:03:08Z
# LAST_CHANGED: 2026-11-04T16:56:30Z
# CHANGE: Implement TaskWorker implementation pseudo-state machine: reset/execute/fetch_and_execute/set_failing_task overrides via call_target with real SUT postcondition assertions, telemetry property transitions, lifecycle-backed real conformance scenarios, and real Hypothesis fuzz compilation.
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T17:03:08Z
# PRETENSE_QA_AUDIT: 2026-11-04T17:02:56Z
# --- END AUTOFAB METADATA ---


# === File: task_worker_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for TaskWorker."""

from __future__ import annotations

from dataclasses import dataclass, field
import unittest
from typing import Optional

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
from benchmark_4.parts.task_queue.lib.task_worker import (
    TaskWorker,
    WorkerExecutionException,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================


@dataclass
class TaskWorkerState:
    """Canonical model state for TaskWorker operations."""

    processed_count: int = 0
    last_task_id: Optional[str] = None
    busy: bool = False
    failing_tasks: set[str] = field(default_factory=set)
    queue_available: bool = True
    queue_pending: int = 0


class TaskWorkerStateMachine(StateMachine[TaskWorkerState]):
    """Unified Pretense State Machine for TaskWorker."""

    def __init__(
        self,
        state: Optional[TaskWorkerState] = None,
        singletons: Optional[dict[type[object], object]] = None,
    ) -> None:
        super().__init__(state=state or TaskWorkerState(), singletons=singletons)

    @transition(TaskWorker.execute)
    def execute(self, task_id: str, payload: str) -> str:
        require_arg(task_id, Domain.type(str), preferred=["task-1"])
        require_arg(payload, Domain.type(str), preferred=["payload"])
        ret: str = ""
        if (not self.state.queue_available) or (task_id in self.state.failing_tasks):
            with raises(WorkerExecutionException):
                ret = make_return_value("")
            return ret
        outcome = f"PROCESSED:{payload.upper()}"
        ret = make_return_value(outcome)
        self.state.processed_count += 1
        self.state.last_task_id = task_id
        self.state.busy = False
        assert ret == outcome
        return ret

    @transition(TaskWorker.fetch_and_execute)
    def fetch_and_execute(self) -> str:
        require(self.state.queue_pending > 0)
        ret: str = ""
        if not self.state.queue_available:
            with raises(WorkerExecutionException):
                ret = make_return_value("")
            return ret
        ret = make_return_value("task")
        self.state.queue_pending -= 1
        self.state.processed_count += 1
        self.state.last_task_id = ret
        assert isinstance(ret, str)
        return ret

    @transition(TaskWorker.set_failing_task)
    def set_failing_task(self, task_id: str, failing: bool) -> None:
        require_arg(task_id, Domain.type(str), preferred=["task-1"])
        require_arg(failing, Domain.boolean())
        ret = make_return_value(None)
        if failing:
            self.state.failing_tasks.add(task_id)
        else:
            self.state.failing_tasks.discard(task_id)
        assert (task_id in self.state.failing_tasks) == failing
        return ret

    @transition.seeding
    def seed_queue_available(self) -> None:
        """Seeds the model into an available collaborator task queue."""
        self.state.queue_available = True

    @transition.seeding
    def seed_pending_task(self) -> None:
        """Seeds the model with one pending collaborator task."""
        self.state.queue_available = True
        self.state.queue_pending += 1


proto = TaskWorkerStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeTaskWorker = synthesize_fake(TaskWorkerStateMachine)


def make_task_worker_fake(state: Optional[TaskWorkerState] = None) -> TaskWorker:
    """Creates a synthesized TaskWorker fake over the given (or blank) model state."""
    return FakeTaskWorker(state=state or TaskWorkerState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================


class TestTaskWorkerFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all declared transitions."""

    def setUp(self) -> None:
        self.fake = make_task_worker_fake()
        self.sm = TaskWorkerStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises every transition and seeding transition of the fake."""
        self.sm.seed_queue_available()
        self.sm.seed_pending_task()
        assert self.sm.fetch_and_execute() == "task"
        self.fake.set_failing_task("bad", True)
        with self.assertRaises(WorkerExecutionException):
            self.fake.execute("bad", "payload")
        self.fake.set_failing_task("bad", False)
        assert self.fake.execute("t1", "payload") == "PROCESSED:PAYLOAD"


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeTaskWorkerFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=TaskWorkerState,
    name="FakeTaskWorkerFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T16:56:15Z
# LAST_CHANGED: 2026-11-04T16:56:15Z
# CHANGE: Implement TaskWorker interface Pretense state machine: model execution telemetry and failing-task state, 1:1 transitions with domain contracts, operational WorkerExecutionException branches, seeding transitions, synthesized fake factory, fixed fake coverage suite, and fake Hypothesis fuzz compilation.
# --- END AUTOFAB METADATA ---
