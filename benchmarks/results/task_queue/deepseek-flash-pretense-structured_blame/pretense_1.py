# === File: task_queue_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for TaskQueue."""

from __future__ import annotations

from typing import Any
import unittest

from pretense import (
    call_target,
    sut,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_6.parts.task_queue.pretense.task_queue_pretense import (
    TaskQueueState,
    TaskQueueStateMachine,
)
from benchmark_6.parts.task_queue.lib.task_queue import (
    QueueEmptyError,
    QueueUnavailableException,
)
from benchmark_6.parts.task_queue.lib.task_queue_impl import QueueFullError, TaskQueue
from benchmark_6.parts.task_queue.lib.task_queue_impl import __initialize__ as _tq_initialize
from benchmark_6.parts.task_queue.lib.task_worker_impl import __initialize__ as _tw_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class TaskQueueImplPseudoStateMachine(TaskQueueStateMachine):
    """Implementation pseudo-state machine for the bounded TaskQueue."""

    @transition(TaskQueue.submit)
    def submit(
        self,
        task_id: str,
        payload: str,
    ) -> Any:
        target: TaskQueue = sut(TaskQueue)
        previous = target.pending_count
        ret = call_target(target.submit(task_id, payload))
        assert target.pending_count == previous + 1
        assert target.is_full == (target.pending_count >= target.capacity)
        return ret

    @transition(TaskQueue.dispatch)
    def dispatch(
        self,
    ) -> Any:
        target: TaskQueue = sut(TaskQueue)
        previous = target.pending_count
        ret = call_target(target.dispatch())
        assert target.pending_count == previous - 1
        assert target.is_empty == (target.pending_count == 0)
        assert isinstance(ret, str)
        return ret

    @transition(TaskQueue.complete)
    def complete(
        self,
        task_id: str,
        outcome: str,
    ) -> Any:
        target: TaskQueue = sut(TaskQueue)
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
        assert ret == target.get_outcome(task_id)
        return ret

    @transition(TaskQueue.clear)
    def clear(
        self,
    ) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(target.clear())
        assert target.pending_count == 0
        assert target.is_empty
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
        ret = call_target(target.capacity)
        assert ret >= 0
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
        assert 0 <= ret <= target.capacity
        return ret


proto = TaskQueueImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestTaskQueueImplReal(unittest.TestCase):
    """Verifies that the concrete bounded queue satisfies the modeled contracts."""

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

    def test_submit_and_dispatch_follow_fifo_order(self) -> None:
        self.checked.submit("task-a", "payload-a")
        self.checked.submit("task-b", "payload-b")
        assert self.checked.pending_count == 2
        assert not self.checked.is_empty
        assert self.checked.dispatch() == "task-a"
        assert self.checked.pending_count == 1
        assert self.checked.dispatch() == "task-b"
        assert self.checked.pending_count == 0
        assert self.checked.is_empty

    def test_complete_records_task_outcome(self) -> None:
        self.checked.submit("task-a", "payload-a")
        self.checked.complete("task-a", "done")
        assert self.checked.get_outcome("task-a") == "done"
        assert self.checked.get_outcome("task-b") is None

    def test_clear_purges_tasks_and_outcomes(self) -> None:
        self.checked.submit("task-a", "payload-a")
        self.checked.complete("task-a", "done")
        self.checked.clear()
        assert self.checked.pending_count == 0
        assert self.checked.is_empty
        assert self.checked.get_outcome("task-a") is None

    def test_capacity_bounds_pending_tasks(self) -> None:
        assert self.checked.capacity == 10
        for index in range(10):
            self.checked.submit(f"task-{index}", "payload")
        assert self.checked.pending_count == 10
        assert self.checked.is_full
        with self.assertRaises(QueueFullError):
            self.checked.submit("task-overflow", "payload")
        assert self.checked.pending_count == 10
        self.checked.dispatch()
        assert not self.checked.is_full

    def test_dispatch_on_emptied_queue_raises(self) -> None:
        self.checked.submit("task-a", "payload-a")
        assert self.checked.pending_count == 1
        assert self.checked.dispatch() == "task-a"
        assert self.checked.pending_count == 0
        assert self.checked.is_empty
        with self.assertRaises(QueueEmptyError):
            self.real.dispatch()
        assert self.checked.pending_count == 0

    def test_unavailable_queue_raises(self) -> None:
        self.checked.set_available(False)
        assert not self.checked.is_available
        with self.assertRaises(QueueUnavailableException):
            self.checked.submit("task-a", "payload-a")
        with self.assertRaises(QueueUnavailableException):
            self.checked.complete("task-a", "done")
        self.checked.set_available(True)
        assert self.checked.is_available
        self.checked.submit("task-a", "payload-a")
        self.checked.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.checked.dispatch()


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
# LAST_CLEANED: 2026-11-08T17:03:43Z
# LAST_CHANGED: 2026-11-08T17:03:10Z
# CHANGE: Resolve coverage feedback: drop the artificial capacity gate on the submit override so the real bounded-queue capacity check runs, and add deterministic terminal contract-violation scenarios - fill the queue to capacity then submit an overflow and verify the capacity rejection, then dispatch to confirm recovery; empty the queue and verify dispatching an emptied queue raises the empty-queue rejection; both scenarios also confirm pending counts stay consistent.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:03:43Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:03:21Z
# --- END AUTOFAB METADATA ---


# === File: task_queue_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for TaskQueue."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import unittest

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
from benchmark_6.parts.task_queue.lib.task_queue import (
    QueueUnavailableException,
    TaskQueue,
)


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions (with raises(ExpectedException):
# make_return_value()) live naturally inside the single transition body.
# require_arg defines the caller precondition contract.
# ==============================================================================


@dataclass
class TaskQueueState:
    """Canonical model state for TaskQueue operations."""

    pending: List[str] = field(default_factory=list)
    outcomes: Dict[str, str] = field(default_factory=dict)
    available: bool = True


class TaskQueueStateMachine(StateMachine[TaskQueueState]):
    """Unified Pretense State Machine modeling TaskQueue operations 1:1."""

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
        require_arg(task_id, Domain.type(str), preferred=["task-a"])
        require_arg(payload, Domain.type(str), preferred=["payload-a"])
        if not self.state.available:
            with raises(QueueUnavailableException):
                make_return_value()
            return None
        ret = make_return_value()
        self.state.pending.append(task_id)
        assert self.state.pending[-1] == task_id
        return ret

    @transition(TaskQueue.dispatch)
    def dispatch(
        self,
    ) -> str:
        require(len(self.state.pending) > 0)
        if not self.state.available:
            with raises(QueueUnavailableException):
                make_return_value()
            return ""
        count = len(self.state.pending)
        oldest = self.state.pending[0]
        ret = make_return_value(oldest)
        self.state.pending.pop(0)
        assert len(self.state.pending) == count - 1
        return ret

    @transition(TaskQueue.complete)
    def complete(
        self,
        task_id: str,
        outcome: str,
    ) -> None:
        require_arg(task_id, Domain.type(str), preferred=["task-a"])
        require_arg(outcome, Domain.type(str), preferred=["done"])
        if not self.state.available:
            with raises(QueueUnavailableException):
                make_return_value()
            return None
        ret = make_return_value()
        self.state.outcomes[task_id] = outcome
        assert self.state.outcomes.get(task_id) == outcome
        return ret

    @transition(TaskQueue.get_outcome)
    def get_outcome(
        self,
        task_id: str,
    ) -> Optional[str]:
        require_arg(task_id, Domain.type(str), preferred=["task-a"])
        ret = make_return_value(self.state.outcomes.get(task_id))
        return ret

    @transition(TaskQueue.clear)
    def clear(
        self,
    ) -> None:
        ret = make_return_value()
        self.state.pending.clear()
        self.state.outcomes.clear()
        assert len(self.state.pending) == 0
        assert len(self.state.outcomes) == 0
        return ret

    @transition(TaskQueue.set_available)
    def set_available(
        self,
        available: bool,
    ) -> None:
        require_arg(available, Domain.type(bool), preferred=[True, False])
        ret = make_return_value()
        self.state.available = available
        assert self.state.available == available
        return ret

    @transition(name="pending_count")
    def pending_count(self) -> int:
        ret = make_return_value(len(self.state.pending))
        return ret


proto = TaskQueueStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeTaskQueue = synthesize_fake(TaskQueueStateMachine)


def make_task_queue_fake(state: Optional[TaskQueueState] = None) -> TaskQueue:
    """Synthesizes a fake TaskQueue double sharing the given model state."""
    return FakeTaskQueue(state=state or TaskQueueState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================


class TestTaskQueueFake(unittest.TestCase):
    """Verifies the synthesized TaskQueue fake honors the modeled contracts."""

    def setUp(self) -> None:
        self.fake = make_task_queue_fake()

    def test_submit_and_dispatch_preserve_fifo_order(self) -> None:
        self.fake.submit("task-a", "payload-a")
        self.fake.submit("task-b", "payload-b")
        assert self.fake.pending_count == 2
        assert self.fake.dispatch() == "task-a"
        assert self.fake.pending_count == 1
        assert self.fake.dispatch() == "task-b"
        assert self.fake.pending_count == 0

    def test_complete_records_task_outcome(self) -> None:
        assert self.fake.get_outcome("task-a") is None
        self.fake.complete("task-a", "done")
        assert self.fake.get_outcome("task-a") == "done"

    def test_clear_purges_tasks_and_outcomes(self) -> None:
        self.fake.submit("task-a", "payload-a")
        self.fake.complete("task-a", "done")
        self.fake.clear()
        assert self.fake.pending_count == 0
        assert self.fake.get_outcome("task-a") is None

    def test_unavailable_queue_raises(self) -> None:
        self.fake.submit("task-a", "payload-a")
        self.fake.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.fake.submit("task-b", "payload-b")
        with self.assertRaises(QueueUnavailableException):
            self.fake.dispatch()
        with self.assertRaises(QueueUnavailableException):
            self.fake.complete("task-a", "done")
        self.fake.set_available(True)
        assert self.fake.pending_count == 1
        assert self.fake.dispatch() == "task-a"


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeTaskQueueFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=TaskQueueState,
    name="FakeTaskQueueFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T16:54:53Z
# LAST_CHANGED: 2026-11-08T16:54:53Z
# CHANGE: Implement TaskQueue interface pretense: canonical TaskQueueState (pending/outcomes/available), 1:1 transitions for submit/dispatch/complete/get_outcome/clear/set_available/pending_count with require/require_arg caller contracts and raises() postcondition exceptions, synthesized FakeTaskQueue with make_task_queue_fake, fixed TestTaskQueueFake scenarios covering every transition, and FakeTaskQueueFuzzTest.
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for TaskWorker."""

from __future__ import annotations

from typing import Any, Optional
import unittest

from pretense import (
    PretenseError,
    raises,
    call_target,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_6.parts.task_queue.pretense.task_worker_pretense import (
    TaskWorkerState,
    TaskWorkerStateMachine,
    make_task_worker_fake,
)
from benchmark_6.parts.task_queue.pretense.task_queue_pretense import (
    TaskQueueState,
    TaskQueueStateMachine,
)
from benchmark_6.parts.task_queue.lib.task_queue import (
    TaskQueue as TaskQueueInterface,
)
from benchmark_6.parts.task_queue.lib.task_worker import (
    WorkerError,
    WorkerExecutionException,
)
from benchmark_6.parts.task_queue.lib.task_worker_impl import TaskWorker
from benchmark_6.parts.task_queue.lib.task_queue_impl import __initialize__ as _tq_initialize
from benchmark_6.parts.task_queue.lib.task_worker_impl import __initialize__ as _tw_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

def _composed_queue_state() -> Optional[TaskQueueState]:
    """Returns the composed collaborator queue model, or None when not composed."""
    try:
        return sut_state(TaskQueueState)
    except PretenseError:
        return None


class TaskWorkerImplPseudoStateMachine(TaskWorkerStateMachine):
    """Implementation pseudo-state machine for the concrete TaskWorker."""

    @transition(TaskWorker.reset)
    def reset(
        self,
    ) -> Any:
        target: TaskWorker = sut(TaskWorker)
        ret = call_target(target.reset())
        assert target.processed_count == 0
        assert target.last_task_id is None
        assert not target.is_busy
        return ret

    @transition(TaskWorker.execute)
    def execute(
        self,
        task_id: str,
        payload: str,
    ) -> Any:
        target: TaskWorker = sut(TaskWorker)
        queue_state = _composed_queue_state()
        if queue_state is not None and not queue_state.available:
            with raises(WorkerExecutionException):
                call_target(target.execute(task_id, payload))
            return ""
        previous = target.processed_count
        ret = call_target(target.execute(task_id, payload))
        assert target.processed_count == previous + 1
        assert target.last_task_id == task_id
        assert not target.is_busy
        assert ret == f"PROCESSED:{payload.upper()}"
        return ret

    @transition(TaskWorker.fetch_and_execute)
    def fetch_and_execute(
        self,
    ) -> Any:
        target: TaskWorker = sut(TaskWorker)
        queue_state = _composed_queue_state()
        if queue_state is not None and not queue_state.available:
            with raises(WorkerExecutionException):
                call_target(target.fetch_and_execute())
            return ""
        if queue_state is not None and len(queue_state.pending) == 0:
            with raises(WorkerError):
                call_target(target.fetch_and_execute())
            return ""
        previous = target.processed_count
        ret = call_target(target.fetch_and_execute())
        assert target.processed_count == previous + 1
        assert target.last_task_id == ret
        assert not target.is_busy
        return ret

    @transition(TaskWorker.set_failing_task)
    def set_failing_task(
        self,
        task_id: str,
        failing: bool,
    ) -> Any:
        target: TaskWorker = sut(TaskWorker)
        ret = call_target(target.set_failing_task(task_id, failing))
        assert not target.is_busy
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
    """Verifies that the concrete worker satisfies the modeled contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _tq_initialize(self.registry)
        _tw_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(TaskWorker)
        self.queue = get_singleton(TaskQueueInterface)
        self.sm = TaskWorkerImplPseudoStateMachine(singletons={TaskWorker: self.real})
        self.checked = self.sm.as_checked(TaskWorker, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_execute_transforms_payload_and_updates_telemetry(self) -> None:
        assert self.checked.execute("task-a", "payload-a") == "PROCESSED:PAYLOAD-A"
        assert self.checked.processed_count == 1
        assert self.checked.last_task_id == "task-a"
        assert not self.checked.is_busy

    def test_execute_failing_task_raises(self) -> None:
        self.checked.set_failing_task("task-b", True)
        with self.assertRaises(WorkerExecutionException):
            self.checked.execute("task-b", "payload-b")
        assert self.checked.processed_count == 0
        assert not self.checked.is_busy
        self.checked.set_failing_task("task-b", False)
        assert self.checked.execute("task-b", "payload-b") == "PROCESSED:PAYLOAD-B"

    def test_fetch_and_execute_dispatches_pending_task(self) -> None:
        self.queue.submit("task-a", "payload-a")
        assert self.checked.fetch_and_execute() == "task-a"
        assert self.checked.processed_count == 1
        assert self.checked.last_task_id == "task-a"
        assert not self.checked.is_busy

    def test_execute_raises_when_queue_unavailable(self) -> None:
        self.queue.set_available(False)
        with self.assertRaises(WorkerExecutionException):
            self.checked.execute("task-a", "payload-a")
        assert self.checked.processed_count == 0
        assert not self.checked.is_busy
        self.queue.set_available(True)
        assert self.checked.execute("task-a", "payload-a") == "PROCESSED:PAYLOAD-A"

    def test_fetch_and_execute_raises_when_queue_unavailable(self) -> None:
        self.queue.set_available(False)
        with self.assertRaises(WorkerExecutionException):
            self.checked.fetch_and_execute()
        assert self.checked.processed_count == 0
        assert not self.checked.is_busy
        self.queue.set_available(True)

    def test_fetch_and_execute_on_empty_queue_raises(self) -> None:
        with self.assertRaises(WorkerError):
            self.checked.fetch_and_execute()
        assert self.checked.processed_count == 0
        assert not self.checked.is_busy

    def test_reset_clears_telemetry(self) -> None:
        self.checked.execute("task-a", "payload-a")
        assert self.checked.processed_count == 1
        self.checked.reset()
        assert self.checked.processed_count == 0
        assert self.checked.last_task_id is None
        assert not self.checked.is_busy


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
    sut_factory=make_sut,
    initial_state_factory=TaskWorkerState,
    collaborators=[TaskQueueStateMachine],
    name="TaskWorkerFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:24:22Z
# LAST_CHANGED: 2026-11-08T17:23:49Z
# CHANGE: Resolve feedback: the delegated execute and fetch transitions again model the contracted rejections, but only while a composed collaborator queue model is active - resolved through the collaborator state consultation, which yields the composed model when present and None otherwise. In the composed fuzz composition the transitions verify the unavailable-queue execution exception and the zero-pending rejection instead of letting them escape as unhandled verification errors; when no collaborator model is active (the real-engine scenarios) the same transitions fall back to unconditional delegation, and the real-engine scenarios assert those same rejections around the delegation while the success paths keep the telemetry postconditions. Composition setup remains concrete queue plus worker with only the target bound for checked execution.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:24:22Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:24:00Z
# --- END AUTOFAB METADATA ---


# === File: task_worker_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for TaskWorker."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
import unittest

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
from benchmark_6.parts.task_queue.lib.task_worker import (
    TaskWorker,
    WorkerExecutionException,
)


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions (with raises(ExpectedException):
# make_return_value()) live naturally inside the single transition body.
# require_arg defines the caller precondition contract.
# ==============================================================================


@dataclass
class TaskWorkerState:
    """Canonical model state for TaskWorker operations."""

    failing_tasks: Set[str] = field(default_factory=set)
    outcomes: Dict[str, str] = field(default_factory=dict)
    fetched: List[str] = field(default_factory=list)
    last_task_id: Optional[str] = None


class TaskWorkerStateMachine(StateMachine[TaskWorkerState]):
    """Unified Pretense State Machine modeling TaskWorker operations 1:1."""

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
        require_arg(task_id, Domain.type(str), preferred=["task-a"])
        require_arg(payload, Domain.type(str), preferred=["payload-a"])
        if task_id in self.state.failing_tasks:
            with raises(WorkerExecutionException):
                make_return_value()
            return ""
        outcome = f"PROCESSED:{payload.upper()}"
        ret = make_return_value(outcome)
        self.state.outcomes[task_id] = outcome
        self.state.last_task_id = task_id
        assert self.state.last_task_id == task_id
        return ret

    @transition(TaskWorker.fetch_and_execute)
    def fetch_and_execute(
        self,
    ) -> str:
        task_id = f"fetched-{len(self.state.fetched)}"
        ret = make_return_value(task_id)
        self.state.fetched.append(task_id)
        self.state.last_task_id = task_id
        assert self.state.fetched[-1] == task_id
        return ret

    @transition(TaskWorker.set_failing_task)
    def set_failing_task(
        self,
        task_id: str,
        failing: bool,
    ) -> None:
        require_arg(task_id, Domain.type(str), preferred=["task-a"])
        require_arg(failing, Domain.type(bool), preferred=[True, False])
        ret = make_return_value()
        if failing:
            self.state.failing_tasks.add(task_id)
        else:
            self.state.failing_tasks.discard(task_id)
        assert (task_id in self.state.failing_tasks) == failing
        return ret


proto = TaskWorkerStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeTaskWorker = synthesize_fake(TaskWorkerStateMachine)


def make_task_worker_fake(state: Optional[TaskWorkerState] = None) -> TaskWorker:
    """Synthesizes a fake TaskWorker double sharing the given model state."""
    return FakeTaskWorker(state=state or TaskWorkerState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================


class TestTaskWorkerFake(unittest.TestCase):
    """Verifies the synthesized TaskWorker fake honors the modeled contracts."""

    def setUp(self) -> None:
        self.fake = make_task_worker_fake()

    def test_execute_reports_processed_outcome(self) -> None:
        assert self.fake.execute("task-a", "payload-a") == "PROCESSED:PAYLOAD-A"

    def test_execute_failing_task_raises(self) -> None:
        self.fake.set_failing_task("task-b", True)
        with self.assertRaises(WorkerExecutionException):
            self.fake.execute("task-b", "payload-b")
        self.fake.set_failing_task("task-b", False)
        assert self.fake.execute("task-b", "payload-b") == "PROCESSED:PAYLOAD-B"

    def test_fetch_and_execute_returns_dispatched_identifier(self) -> None:
        assert self.fake.fetch_and_execute() == "fetched-0"
        assert self.fake.fetch_and_execute() == "fetched-1"


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeTaskWorkerFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=TaskWorkerState,
    name="FakeTaskWorkerFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T16:55:00Z
# LAST_CHANGED: 2026-11-08T16:55:00Z
# CHANGE: Implement TaskWorker interface pretense: TaskWorkerState (failing_tasks/outcomes/fetched/last_task_id), 1:1 transitions for execute/fetch_and_execute/set_failing_task with require_arg domains and raises(WorkerExecutionException) postcondition for designated failing tasks, synthesized FakeTaskWorker with make_task_worker_fake, fixed TestTaskWorkerFake scenarios covering every transition, and FakeTaskWorkerFuzzTest.
# --- END AUTOFAB METADATA ---
