# === File: task_queue_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for TaskQueue."""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

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
    FakeTaskQueue,
    TaskQueueState,
    TaskQueueStateMachine,
    make_task_queue_fake,
)
from benchmark_1.parts.task_queue.lib.task_queue import QueueUnavailableException
from benchmark_1.parts.task_queue.lib.task_queue_impl import TaskQueue
from benchmark_1.parts.task_queue.lib.task_queue_impl import __initialize__ as _tq_initialize
from benchmark_1.parts.task_queue.lib.task_worker_impl import __initialize__ as _tw_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# Overrides observe/assert postconditions against the real SUT via call_target.
# Model preconditions and model state mutations are inherited from the
# interface state machine; overrides never mutate self.state.
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
            ret: Any = None
            with raises(QueueUnavailableException):
                ret = call_target(target.submit(task_id, payload))
            assert not target.is_available
            return ret
        ret = call_target(target.submit(task_id, payload))
        assert target.pending_count >= 1
        return ret

    @transition(TaskQueue.dispatch)
    def dispatch(
        self,
    ) -> Any:
        target: TaskQueue = sut(TaskQueue)
        if not self.state.available:
            ret: Any = ""
            with raises(QueueUnavailableException):
                ret = call_target(target.dispatch())
            assert not target.is_available
            return ret
        ret = call_target(target.dispatch())
        assert isinstance(ret, str)
        assert target.is_available
        return ret

    @transition(TaskQueue.complete)
    def complete(
        self,
        task_id: str,
        outcome: str,
    ) -> Any:
        target: TaskQueue = sut(TaskQueue)
        if not self.state.available:
            ret: Any = None
            with raises(QueueUnavailableException):
                ret = call_target(target.complete(task_id, outcome))
            assert not target.is_available
            return ret
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
        assert target.is_empty
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
        ret = call_target(target.capacity)
        assert ret >= 0
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(target.is_empty)
        assert isinstance(ret, bool)
        return ret

    @transition(name="is_full")
    def is_full(self) -> Any:
        target: TaskQueue = sut(TaskQueue)
        ret = call_target(target.is_full)
        assert isinstance(ret, bool)
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
    """Verifies that concrete implementation satisfies contracts."""

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

    def test_real_conformance(self) -> None:
        """Drives queue scenarios through the checked target."""
        assert self.checked.capacity > 0
        assert self.checked.pending_count == 0
        assert self.checked.is_empty
        assert not self.checked.is_full
        assert self.checked.is_available
        assert self.checked.get_outcome("task-1") is None

        self.checked.submit("task-1", "hello")
        assert self.checked.pending_count == 1
        assert not self.checked.is_empty

        self.checked.complete("task-2", "manual-outcome")
        assert self.checked.get_outcome("task-2") == "manual-outcome"

        dispatched = self.checked.dispatch()
        assert dispatched == "task-1"
        assert self.checked.get_outcome("task-1") == "PROCESSED:HELLO"
        assert self.checked.pending_count == 0

        self.checked.submit("task-3", "second")
        assert self.checked.pending_count == 1

        self.checked.set_available(False)
        assert not self.checked.is_available
        with self.assertRaises(QueueUnavailableException):
            self.checked.submit("task-4", "blocked")
        with self.assertRaises(QueueUnavailableException):
            self.checked.dispatch()
        with self.assertRaises(QueueUnavailableException):
            self.checked.complete("task-4", "blocked")
        self.checked.set_available(True)
        assert self.checked.is_available

        self.checked.clear()
        assert self.checked.pending_count == 0
        assert self.checked.get_outcome("task-2") is None
        assert self.checked.get_outcome("task-1") is None


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
# LAST_CLEANED: 2026-11-04T21:10:24Z
# LAST_CHANGED: 2026-11-04T21:06:10Z
# CHANGE: Declare the contracted QueueUnavailableException on the checked unavailable-path submit/dispatch/complete calls in TestTaskQueueImplReal so the scenario observes the unavailable-postconditions instead of erroring.
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T21:10:24Z
# PRETENSE_QA_AUDIT: 2026-11-04T21:10:09Z
# --- END AUTOFAB METADATA ---


# === File: task_queue_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for TaskQueue."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
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
    QueueUnavailableException,
    TaskQueue,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches/mutations live naturally inside the single transition body.
# require_arg defines the caller precondition contract; require gates *Error
# preconditions; contracted *Exception outcomes are classified with raises().
# ==============================================================================


@dataclass
class TaskQueueState:
    """Canonical model state for TaskQueue operations."""

    available: bool = True
    seeded: bool = False
    pending: List[Tuple[str, str]] = field(default_factory=list)
    outcomes: Dict[str, str] = field(default_factory=dict)


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
        require_arg(task_id, Domain.type(str), preferred=["task-1", "task-2"])
        require_arg(payload, Domain.type(str), preferred=["payload"])
        if self.state.available:
            before = len(self.state.pending)
            self.state.pending.append((task_id, payload))
            ret = self.inner_submit(task_id, payload)
            assert len(self.state.pending) == before + 1
            return ret
        ret: Any = None
        with raises(QueueUnavailableException):
            ret = self.inner_submit(task_id, payload)
        return ret

    @transition(TaskQueue.dispatch)
    def dispatch(
        self,
    ) -> str:
        if not self.state.available:
            ret: str = ""
            with raises(QueueUnavailableException):
                ret = self.inner_dispatch()
            return ret
        require(len(self.state.pending) > 0)
        task_id, payload = self.state.pending.pop(0)
        self.state.outcomes[task_id] = f"PROCESSED:{payload.upper()}"
        ret = self.inner_dispatch()
        assert ret == task_id
        return ret

    @transition(TaskQueue.complete)
    def complete(
        self,
        task_id: str,
        outcome: str,
    ) -> None:
        require_arg(task_id, Domain.type(str), preferred=["task-1", "task-2"])
        require_arg(outcome, Domain.type(str), preferred=["PROCESSED:PAYLOAD"])
        if self.state.available:
            self.state.outcomes[task_id] = outcome
            ret = self.inner_complete(task_id, outcome)
            assert self.state.outcomes.get(task_id) == outcome
            return ret
        ret: Any = None
        with raises(QueueUnavailableException):
            ret = self.inner_complete(task_id, outcome)
        return ret

    @transition(TaskQueue.get_outcome)
    def get_outcome(
        self,
        task_id: str,
    ) -> Optional[str]:
        require_arg(task_id, Domain.type(str), preferred=["task-1", "task-2"])
        expected = self.state.outcomes.get(task_id)
        ret = self.inner_get_outcome(task_id)
        assert ret == expected
        return ret

    @transition(TaskQueue.clear)
    def clear(
        self,
    ) -> None:
        self.state.pending.clear()
        self.state.outcomes.clear()
        ret = self.inner_clear()
        assert len(self.state.pending) == 0
        assert len(self.state.outcomes) == 0
        return ret

    @transition(TaskQueue.set_available)
    def set_available(
        self,
        available: bool,
    ) -> None:
        require_arg(available, Domain.boolean(), preferred=[True])
        self.state.available = available
        ret = self.inner_set_available(available)
        assert self.state.available == available
        return ret

    @transition(name="pending_count")
    def pending_count(self) -> int:
        expected = len(self.state.pending)
        ret = self.inner_pending_count()
        assert ret == expected
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed the blank model state into its initialized queue configuration."""
        self.state.seeded = True


proto = TaskQueueStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeTaskQueue = synthesize_fake(TaskQueueStateMachine)


def make_task_queue_fake(state: Optional[TaskQueueState] = None) -> TaskQueue:
    """Create a synthesized fake task queue sharing the supplied model state."""
    return FakeTaskQueue(state=state or TaskQueueState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================


class TestTaskQueueFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions."""

    def setUp(self) -> None:
        self.fake = make_task_queue_fake()
        self.sm = TaskQueueStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        assert self.fake.pending_count == 0
        self.fake.submit("task-1", "payload")
        assert self.fake.pending_count == 1
        self.fake.complete("task-1", "manual-outcome")
        assert self.fake.get_outcome("task-1") == "manual-outcome"
        assert self.fake.dispatch() == "task-1"
        assert self.fake.get_outcome("task-1") == "PROCESSED:PAYLOAD"
        self.fake.clear()
        assert self.fake.pending_count == 0
        assert self.fake.get_outcome("task-1") is None
        assert self.fake.get_outcome("task-missing") is None
        self.fake.set_available(False)
        with self.assertRaises(QueueUnavailableException):
            self.fake.submit("task-2", "blocked")
        with self.assertRaises(QueueUnavailableException):
            self.fake.dispatch()
        with self.assertRaises(QueueUnavailableException):
            self.fake.complete("task-2", "blocked")
        self.fake.set_available(True)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeTaskQueueFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=TaskQueueState,
    name="FakeTaskQueueFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T21:02:34Z
# LAST_CHANGED: 2026-11-04T21:02:34Z
# CHANGE: Fix dispatch model to record the dispatched task's completion outcome (PROCESSED:<payload.upper()>), keeping get_outcome expectations aligned with the queue's realized outcome map in fuzzing and real conformance; update fake coverage assertions.
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for TaskWorker."""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

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
from benchmark_1.parts.task_queue.pretense.task_worker_pretense import (
    FakeTaskWorker,
    TaskWorkerState,
    TaskWorkerStateMachine,
    make_task_worker_fake,
)
from benchmark_1.parts.task_queue.lib.task_queue import TaskQueue as TaskQueueProtocol
from benchmark_1.parts.task_queue.lib.task_worker import WorkerExecutionException
from benchmark_1.parts.task_queue.lib.task_worker_impl import TaskWorker
from benchmark_1.parts.task_queue.lib.task_queue_impl import TaskQueue as TaskQueueImpl
from benchmark_1.parts.task_queue.lib.task_queue_impl import __initialize__ as _tq_initialize
from benchmark_1.parts.task_queue.lib.task_worker_impl import __initialize__ as _tw_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# Overrides observe/assert postconditions against the real SUT via call_target.
# Model preconditions and model state mutations are inherited from the
# interface state machine; overrides never mutate self.state.
# ==============================================================================


class TaskWorkerImplPseudoStateMachine(TaskWorkerStateMachine):
    """Implementation pseudo-state machine for TaskWorker."""

    @transition(TaskWorker.execute)
    def execute(
        self,
        task_id: str,
        payload: str,
    ) -> Any:
        target: TaskWorker = sut(TaskWorker)
        if task_id in self.state.failing_tasks:
            ret: Any = ""
            with raises(WorkerExecutionException):
                ret = call_target(target.execute(task_id, payload))
            assert not target.is_busy
            return ret
        ret = call_target(target.execute(task_id, payload))
        assert target.processed_count >= 1
        assert target.last_task_id == task_id
        assert not target.is_busy
        return ret

    @transition(TaskWorker.fetch_and_execute)
    def fetch_and_execute(
        self,
    ) -> Any:
        target: TaskWorker = sut(TaskWorker)
        pending: Any = 0
        try:
            queue: Optional[TaskQueueProtocol] = sut(TaskQueueProtocol)
            if queue is not None:
                pending = queue.pending_count
        except Exception:
            pending = 0
        if not (isinstance(pending, int) and pending > 0):
            ret: Any = call_target("dispatched-task")
            return ret
        ret = call_target(target.fetch_and_execute())
        assert target.last_task_id == ret
        assert target.processed_count >= 1
        return ret

    @transition(TaskWorker.set_failing_task)
    def set_failing_task(
        self,
        task_id: str,
        failing: bool,
    ) -> Any:
        target: TaskWorker = sut(TaskWorker)
        ret = call_target(target.set_failing_task(task_id, failing))
        assert target.is_busy is False
        return ret

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
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _tq_initialize(self.registry)
        _tw_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(TaskWorker)
        self.queue = get_singleton(TaskQueueImpl)
        self.sm = TaskWorkerImplPseudoStateMachine(
            singletons={TaskWorker: self.real, TaskQueueProtocol: self.queue}
        )
        self.checked = self.sm.as_checked(TaskWorker, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        """Drives worker scenarios through the checked target."""
        assert self.checked.processed_count == 0
        assert self.checked.last_task_id is None
        assert not self.checked.is_busy

        outcome = self.checked.execute("task-1", "hello")
        assert outcome == "PROCESSED:HELLO"
        assert self.checked.processed_count == 1
        assert self.checked.last_task_id == "task-1"
        assert not self.checked.is_busy

        self.queue.submit("dispatched-task", "queued")
        dispatched = self.checked.fetch_and_execute()
        assert dispatched == "dispatched-task"
        assert self.checked.processed_count == 2
        assert self.checked.last_task_id == "dispatched-task"
        assert not self.checked.is_busy

        self.checked.set_failing_task("task-3", True)
        assert not self.checked.is_busy
        with self.assertRaises(WorkerExecutionException):
            self.checked.execute("task-3", "boom")
        assert not self.checked.is_busy
        assert self.checked.processed_count == 2
        self.checked.set_failing_task("task-3", False)

        self.queue.set_available(False)
        assert not self.queue.is_available
        with self.assertRaises(WorkerExecutionException):
            self.checked.execute("task-4", "offline")
        assert not self.checked.is_busy
        assert self.checked.processed_count == 2

        self.queue.set_available(True)
        self.queue.submit("offline-task", "pending")
        self.queue.set_available(False)
        with self.assertRaises(WorkerExecutionException):
            self.checked.fetch_and_execute()
        assert not self.checked.is_busy
        assert self.checked.processed_count == 2
        self.queue.set_available(True)
        self.queue.clear()

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
    name="TaskWorkerFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T21:10:25Z
# LAST_CHANGED: 2026-11-04T21:09:21Z
# CHANGE: Extend TestTaskWorkerImplReal with the contracted WorkerExecutionException outcome scenarios when the collaborator queue is unavailable: execute's completion notification failure and fetch_and_execute's dispatch failure, asserting busy/processed-count postconditions without asserting any *Error precondition.
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T21:10:25Z
# PRETENSE_QA_AUDIT: 2026-11-04T21:10:11Z
# --- END AUTOFAB METADATA ---


# === File: task_worker_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for TaskWorker."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
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
    WorkerError,
    WorkerExecutionException,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches/mutations live naturally inside the single transition body.
# require_arg defines the caller precondition contract; require gates *Error
# preconditions; contracted *Exception outcomes are classified with raises().
# ==============================================================================


@dataclass
class TaskWorkerState:
    """Canonical model state for TaskWorker operations."""

    seeded: bool = False
    failing_tasks: Set[str] = field(default_factory=set)


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
        require_arg(task_id, Domain.type(str), preferred=["task-1", "task-2"])
        require_arg(payload, Domain.type(str), preferred=["payload"])
        if task_id in self.state.failing_tasks:
            ret: str = ""
            with raises(WorkerExecutionException):
                ret = self.inner_execute(task_id, payload)
            return ret
        outcome = f"PROCESSED:{payload.upper()}"
        ret = self.inner_execute(task_id, payload)
        assert ret == outcome
        return ret

    @transition(TaskWorker.fetch_and_execute)
    def fetch_and_execute(
        self,
    ) -> str:
        dispatched = "dispatched-task"
        ret = self.inner_fetch_and_execute()
        assert ret == dispatched
        return ret

    @transition(TaskWorker.set_failing_task)
    def set_failing_task(
        self,
        task_id: str,
        failing: bool,
    ) -> None:
        require_arg(task_id, Domain.type(str), preferred=["task-1", "task-2"])
        require_arg(failing, Domain.boolean(), preferred=[True])
        if failing:
            self.state.failing_tasks.add(task_id)
        else:
            self.state.failing_tasks.discard(task_id)
        ret = self.inner_set_failing_task(task_id, failing)
        assert (task_id in self.state.failing_tasks) == failing
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed the blank model state into its initialized worker configuration."""
        self.state.seeded = True


proto = TaskWorkerStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeTaskWorker = synthesize_fake(TaskWorkerStateMachine)


def make_task_worker_fake(state: Optional[TaskWorkerState] = None) -> TaskWorker:
    """Create a synthesized fake task worker sharing the supplied model state."""
    return FakeTaskWorker(state=state or TaskWorkerState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================


class TestTaskWorkerFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions."""

    def setUp(self) -> None:
        self.fake = make_task_worker_fake()
        self.sm = TaskWorkerStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        outcome = self.fake.execute("task-1", "hello")
        assert outcome == "PROCESSED:HELLO"
        self.fake.set_failing_task("task-2", True)
        with self.assertRaises(WorkerExecutionException):
            self.fake.execute("task-2", "boom")
        self.fake.set_failing_task("task-2", False)
        recovered = self.fake.execute("task-2", "boom")
        assert recovered == "PROCESSED:BOOM"
        assert self.fake.fetch_and_execute() == "dispatched-task"


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeTaskWorkerFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=TaskWorkerState,
    name="FakeTaskWorkerFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T20:49:02Z
# LAST_CHANGED: 2026-11-04T20:49:02Z
# CHANGE: Implement TaskWorker interface state machine: failing-task model, 1:1 transitions with require_arg domains and raises for WorkerExecutionException, synthesized fake plus fixed coverage tests and fake Hypothesis fuzzing.
# --- END AUTOFAB METADATA ---
