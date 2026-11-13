# === File: task_queue_impl_pretense.py ===
from __future__ import annotations

from typing import Optional
import unittest

from pretense import sut
from support.lib.lifecycle import LifecycleTestCase, system

from task_queue_deepseek_flash_1.parts.task_queue.lib import task_queue
from task_queue_deepseek_flash_1.parts.task_queue.lib import task_queue_impl
from task_queue_deepseek_flash_1.parts.task_queue.lib import task_worker
from task_queue_deepseek_flash_1.parts.task_queue.lib import task_worker_impl
from task_queue_deepseek_flash_1.parts.task_queue.pretense import task_queue_pretense
from task_queue_deepseek_flash_1.parts.task_queue.pretense.task_queue_pretense import (
    TaskQueueStateMachine,
)


# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class TaskQueueImplPseudoStateMachine(TaskQueueStateMachine):
    """Implementation pseudo-state machine binding the bounded task queue SUT."""

    def inner_pending_count(self) -> int:
        target: task_queue_impl.TaskQueue = sut(task_queue_impl.TaskQueue)
        ret = target.pending_count
        assert ret >= 0
        return ret

    def inner_submit(self, task_id: str, payload: str) -> None:
        target: task_queue_impl.TaskQueue = sut(task_queue_impl.TaskQueue)
        before = target.pending_count
        target.submit(task_id, payload)
        assert target.pending_count == before + 1
        assert target.is_empty is False
        assert target.is_full == (target.pending_count == target.capacity)

    def inner_dispatch(self) -> str:
        target: task_queue_impl.TaskQueue = sut(task_queue_impl.TaskQueue)
        before = target.pending_count
        ret = target.dispatch()
        assert target.pending_count == before - 1
        return ret

    def inner_complete(self, task_id: str, outcome: str) -> None:
        target: task_queue_impl.TaskQueue = sut(task_queue_impl.TaskQueue)
        target.complete(task_id, outcome)
        assert target.get_outcome(task_id) == outcome

    def inner_get_outcome(self, task_id: str) -> Optional[str]:
        target: task_queue_impl.TaskQueue = sut(task_queue_impl.TaskQueue)
        return target.get_outcome(task_id)

    def inner_clear(self) -> None:
        target: task_queue_impl.TaskQueue = sut(task_queue_impl.TaskQueue)
        target.clear()
        assert target.pending_count == 0
        assert target.is_empty is True

    def inner_set_available(self, available: bool) -> None:
        target: task_queue_impl.TaskQueue = sut(task_queue_impl.TaskQueue)
        target.set_available(available)
        assert target.is_available is available


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestTaskQueueImplReal(LifecycleTestCase):
    """Verifies that the concrete bounded task queue satisfies its contracts."""

    target = task_queue_impl.TaskQueue

    def setUp(self) -> None:
        super().setUp()
        self.real = self.sut
        self.capacity = self.real.capacity
        if self.registry.find_descriptor(task_worker.TaskWorker) is None:
            self.worker = task_worker_impl.TaskWorker()
            self.registry.register_instance(
                self.worker,
                keys=[task_worker_impl.TaskWorker, task_worker.TaskWorker],
                tier=system,
            )
        else:
            self.worker = self.get_singleton(task_worker.TaskWorker)
        if self.registry.find_descriptor(task_queue.TaskQueue) is None:
            self.registry.register_instance(
                self.real,
                keys=[task_queue.TaskQueue],
                tier=system,
            )
        self.sm = TaskQueueImplPseudoStateMachine(
            singletons={
                task_queue_impl.TaskQueue: self.real,
                task_worker_impl.TaskWorker: self.worker,
            }
        )
        self.checked = self.sm.as_checked(task_queue_impl.TaskQueue, self.real)

    def test_submit_appends_tasks(self) -> None:
        self.checked.submit("task_1", "payload_1")
        self.checked.submit("task_2", "payload_2")
        assert self.checked.pending_count == 2

    def test_dispatch_returns_oldest_task(self) -> None:
        self.checked.submit("task_1", "payload_1")
        self.checked.submit("task_2", "payload_2")
        assert self.checked.dispatch() == "task_1"
        assert self.checked.pending_count == 1

    def test_complete_records_outcome(self) -> None:
        self.checked.complete("task_1", "done_1")
        assert self.checked.get_outcome("task_1") == "done_1"

    def test_get_outcome_of_uncompleted_task(self) -> None:
        assert self.checked.get_outcome("task_1") is None

    def test_clear_purges_tasks_and_outcomes(self) -> None:
        self.checked.submit("task_1", "payload_1")
        self.checked.complete("task_1", "done_1")
        self.checked.clear()
        assert self.checked.pending_count == 0
        assert self.checked.get_outcome("task_1") is None

    def test_set_available_toggles_availability(self) -> None:
        self.checked.set_available(False)
        self.checked.set_available(True)

    def test_dispatch_empty_queue_raises(self) -> None:
        self.checked.violating(task_queue.QueueEmptyError).dispatch()

    def test_submit_unavailable_queue_raises(self) -> None:
        self.checked.set_available(False)
        self.checked.violating(task_queue.QueueUnavailableException).submit("task_1", "payload_1")

    def test_dispatch_unavailable_queue_raises(self) -> None:
        self.checked.submit("task_1", "payload_1")
        self.checked.set_available(False)
        self.checked.violating(task_queue.QueueUnavailableException).dispatch()

    def test_complete_unavailable_queue_raises(self) -> None:
        self.checked.set_available(False)
        self.checked.violating(task_queue.QueueUnavailableException).complete("task_1", "done_1")

    def test_submit_full_queue_raises(self) -> None:
        for index in range(self.capacity):
            self.checked.submit(f"task_{index}", f"payload_{index}")
        self.checked.violating(task_queue_impl.QueueFullError).submit("task_extra", "payload_extra")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:17:39Z
# LAST_CHANGED: 2026-11-12T21:17:20Z
# CHANGE: Hardened task queue implementation tests to bind a concrete TaskWorker collaborator (resolved or registered under both keys) and to register the queue SUT under the interface key, so dispatch delegates to the same singleton the SUT resolves instead of a mock with non-persistent state.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T21:17:39Z
# PRETENSE_QA_AUDIT: 2026-11-12T21:17:26Z
# --- END AUTOFAB METADATA ---


# === File: task_queue_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import unittest

from pretense import (
    Domain,
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

from task_queue_deepseek_flash_1.parts.task_queue.lib import task_queue


SEED_TASK_ID = "seed_task_1"
SEED_PAYLOAD = "seed_payload_1"
SEED_OUTCOME_TASK_ID = "seed_task_2"
SEED_OUTCOME = "seed_outcome_1"


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions - Interface Component)
# ==============================================================================

@dataclass
class TaskQueueState:
    """Model state for the FIFO task queue."""

    available: bool = True
    pending_count: int = 0
    pending: list[tuple[str, str]] = field(default_factory=list)
    outcomes: dict[str, str] = field(default_factory=dict)


class TaskQueueStateMachine(StateMachine[TaskQueueState]):
    """Unified Pretense state machine for the task queue interface."""

    def __init__(
        self,
        state: Optional[TaskQueueState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> TaskQueueState:
        """Constructs the initial (blank) model state for a task queue."""
        return TaskQueueState()

    @transition(name="pending_count")
    def pending_count(self) -> int:
        """Reports the number of pending tasks held by the queue."""
        ret = self.inner_pending_count()
        assert ret == len(self.state.pending)
        assert ret == self.state.pending_count
        return ret

    def inner_pending_count(self) -> int:
        return self.state.pending_count

    @transition(task_queue.TaskQueue.submit)
    def submit(self, task_id: str, payload: str) -> None:
        """Appends a task to the queue tail when the queue is available."""
        require_env(self.state.available, task_queue.QueueUnavailableException, task_id, payload)
        require_arg(task_id, Domain.type(str), preferred=["task_1", "task_2"])
        require_arg(payload, Domain.type(str), preferred=["payload_1", "payload_2"])
        self.inner_submit(task_id, payload)
        self.state.pending.append((task_id, payload))
        self.state.pending_count += 1
        assert self.state.pending[-1] == (task_id, payload)

    def inner_submit(self, task_id: str, payload: str) -> None:
        return None

    @transition(task_queue.TaskQueue.dispatch)
    def dispatch(self) -> str:
        """Pops the oldest pending task and returns its identifier."""
        require_env(self.state.available, task_queue.QueueUnavailableException)
        require(len(self.state.pending) > 0, error=task_queue.QueueEmptyError)
        ret = self.inner_dispatch()
        task_id, _payload = self.state.pending.pop(0)
        self.state.pending_count -= 1
        assert ret == task_id
        return ret

    def inner_dispatch(self) -> str:
        return self.state.pending[0][0]

    @transition(task_queue.TaskQueue.complete)
    def complete(self, task_id: str, outcome: str) -> None:
        """Records the completion outcome for a task identifier."""
        require_env(self.state.available, task_queue.QueueUnavailableException, task_id, outcome)
        require_arg(task_id, Domain.type(str), preferred=["task_1", "task_2"])
        require_arg(outcome, Domain.type(str), preferred=["done_1", "done_2"])
        self.inner_complete(task_id, outcome)
        self.state.outcomes[task_id] = outcome
        assert self.state.outcomes.get(task_id) == outcome

    def inner_complete(self, task_id: str, outcome: str) -> None:
        return None

    @transition(task_queue.TaskQueue.get_outcome)
    def get_outcome(self, task_id: str) -> Optional[str]:
        """Retrieves the recorded outcome for a task identifier, if any."""
        require_arg(task_id, Domain.type(str), preferred=["task_1", "task_2"])
        ret = self.inner_get_outcome(task_id)
        assert ret == self.state.outcomes.get(task_id)
        return ret

    def inner_get_outcome(self, task_id: str) -> Optional[str]:
        return self.state.outcomes.get(task_id)

    @transition(task_queue.TaskQueue.clear)
    def clear(self) -> None:
        """Purges all pending tasks and recorded outcomes."""
        self.inner_clear()
        self.state.pending = []
        self.state.outcomes = {}
        self.state.pending_count = 0
        assert len(self.state.pending) == 0
        assert len(self.state.outcomes) == 0

    def inner_clear(self) -> None:
        return None

    @transition(task_queue.TaskQueue.set_available)
    def set_available(self, available: bool) -> None:
        """Toggles the operational availability of the queue."""
        require_arg(available, Domain.type(bool), preferred=[True, False])
        self.inner_set_available(available)
        self.state.available = available
        assert self.state.available == available

    def inner_set_available(self, available: bool) -> None:
        return None

    @transition.seeding
    def seed_pending_task(self) -> None:
        """Seeds one pending task so queue operations can start from a blank state."""
        self.state.pending.append((SEED_TASK_ID, SEED_PAYLOAD))
        self.state.pending_count += 1

    @transition.seeding
    def seed_recorded_outcome(self) -> None:
        """Seeds one recorded outcome so outcome lookups can start from a blank state."""
        self.state.outcomes[SEED_OUTCOME_TASK_ID] = SEED_OUTCOME


proto = TaskQueueStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeTaskQueue = synthesize_fake(TaskQueueStateMachine)


def make_task_queue_fake(state: Optional[TaskQueueState] = None) -> task_queue.TaskQueue:
    """Synthesizes a fake task queue backed by the model state."""
    return FakeTaskQueue(state=state or proto.make_initial_state())


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

class TestTaskQueueFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding."""

    def setUp(self) -> None:
        self.fake = make_task_queue_fake()
        self.sm = TaskQueueStateMachine(singletons={task_queue.TaskQueue: self.fake})

    def test_model_transitions(self) -> None:
        self.sm.seed_pending_task()
        self.sm.seed_recorded_outcome()
        assert self.sm.pending_count() == 1
        self.sm.submit("task_1", "payload_1")
        assert self.sm.pending_count() == 2
        assert self.sm.dispatch() == SEED_TASK_ID
        self.sm.complete("task_1", "done_1")
        assert self.sm.get_outcome("task_1") == "done_1"
        self.sm.clear()
        assert self.sm.pending_count() == 0
        self.sm.set_available(False)
        self.sm.set_available(True)

    def test_fake_transitions(self) -> None:
        self.fake.submit("task_1", "payload_1")
        assert self.fake.pending_count == 1
        assert self.fake.dispatch() == "task_1"
        self.fake.complete("task_1", "done_1")
        assert self.fake.get_outcome("task_1") == "done_1"
        self.fake.clear()
        assert self.fake.pending_count == 0
        self.fake.set_available(True)


# Fake Fuzzing (Exercises synthesized fake against state machine contracts):
FakeTaskQueueFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeTaskQueueFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:08:05Z
# LAST_CHANGED: 2026-11-12T21:08:05Z
# CHANGE: Modeled the FIFO TaskQueue interface as a Pretense state machine: 1:1 transitions for submit/dispatch/complete/get_outcome/clear/set_available plus the pending_count property, require/require_env guard policy, seeding transitions, synthesized verified fake, fixed fake tests, and fake property fuzzing.
# --- END AUTOFAB METADATA ---


# === File: task_worker_impl_pretense.py ===
from __future__ import annotations

import unittest

from pretense import sut
from support.lib.lifecycle import LifecycleTestCase, system

from task_queue_deepseek_flash_1.parts.task_queue.lib import task_queue
from task_queue_deepseek_flash_1.parts.task_queue.lib import task_queue_impl
from task_queue_deepseek_flash_1.parts.task_queue.lib import task_worker
from task_queue_deepseek_flash_1.parts.task_queue.lib import task_worker_impl
from task_queue_deepseek_flash_1.parts.task_queue.pretense import task_worker_pretense
from task_queue_deepseek_flash_1.parts.task_queue.pretense.task_worker_pretense import (
    SEED_PAYLOAD,
    SEED_TASK_ID,
    TaskWorkerStateMachine,
)


# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class TaskWorkerImplPseudoStateMachine(TaskWorkerStateMachine):
    """Implementation pseudo-state machine binding the task worker SUT."""

    def inner_execute(self, task_id: str, payload: str) -> str:
        target: task_worker_impl.TaskWorker = sut(task_worker_impl.TaskWorker)
        ret = target.execute(task_id, payload)
        assert ret == f"PROCESSED:{payload.upper()}"
        assert target.processed_count == self.state.processed + 1
        assert target.last_task_id == task_id
        assert target.is_busy is False
        return ret

    def inner_fetch_and_execute(self) -> str:
        target: task_worker_impl.TaskWorker = sut(task_worker_impl.TaskWorker)
        ret = target.fetch_and_execute()
        assert target.last_task_id == ret
        assert target.is_busy is False
        return ret

    def inner_set_failing_task(self, task_id: str, failing: bool) -> None:
        target: task_worker_impl.TaskWorker = sut(task_worker_impl.TaskWorker)
        target.set_failing_task(task_id, failing)


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestTaskWorkerImplReal(LifecycleTestCase):
    """Verifies that the concrete task worker satisfies its contracts."""

    target = task_worker_impl.TaskWorker

    def setUp(self) -> None:
        super().setUp()
        self.real = self.sut
        self.real.reset()
        if self.registry.find_descriptor(task_queue.TaskQueue) is None:
            self.queue = task_queue_impl.TaskQueue()
            self.registry.register_instance(
                self.queue,
                keys=[task_queue_impl.TaskQueue, task_queue.TaskQueue],
                tier=system,
            )
        else:
            self.queue = self.get_singleton(task_queue.TaskQueue)
        self.sm = TaskWorkerImplPseudoStateMachine(
            singletons={
                task_queue.TaskQueue: self.queue,
                task_worker_impl.TaskWorker: self.real,
            }
        )
        self.sm.seed_pending_task()
        self.queue.submit(SEED_TASK_ID, SEED_PAYLOAD)
        self.checked = self.sm.as_checked(task_worker_impl.TaskWorker, self.real)

    def test_execute_returns_outcome(self) -> None:
        assert self.checked.execute("task_1", "payload_1") == "PROCESSED:PAYLOAD_1"

    def test_set_failing_task_can_reset(self) -> None:
        self.checked.set_failing_task("task_1", True)
        self.checked.set_failing_task("task_1", False)

    def test_execute_failing_task_raises(self) -> None:
        self.checked.set_failing_task("task_9", True)
        self.checked.violating(task_worker.WorkerExecutionException).execute("task_9", "payload_9")

    def test_execute_unavailable_queue_raises(self) -> None:
        self.queue.set_available(False)
        self.checked.violating(task_worker.WorkerExecutionException).execute("task_1", "payload_1")

    def test_fetch_and_execute_dispatches_pending_task(self) -> None:
        assert self.checked.fetch_and_execute() == SEED_TASK_ID

    def test_fetch_and_execute_empty_queue_raises(self) -> None:
        assert self.checked.fetch_and_execute() == SEED_TASK_ID
        self.checked.violating(task_worker.WorkerError).fetch_and_execute()

    def test_fetch_and_execute_unavailable_queue_raises(self) -> None:
        self.queue.set_available(False)
        self.checked.violating(task_worker.WorkerExecutionException).fetch_and_execute()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:17:41Z
# LAST_CHANGED: 2026-11-12T21:17:14Z
# CHANGE: Resolved pretense_qa blame by wiring the worker SUT to a concrete TaskQueue collaborator instance (resolved or registered under both interface and implementation keys) instead of a mock whose state did not reach the SUT. Unavailable-queue fixtures now make queue.complete/dispatch raise QueueUnavailableException, so execute/fetch_and_execute surface WorkerExecutionException, and the drained real queue makes the second fetch surface WorkerError instead of NoMatchingTransitionError.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T21:17:41Z
# PRETENSE_QA_AUDIT: 2026-11-12T21:17:28Z
# --- END AUTOFAB METADATA ---


# === File: task_worker_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import unittest

from pretense import (
    Domain,
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

from task_queue_deepseek_flash_1.parts.task_queue.lib import task_worker


SEED_TASK_ID = "seed_task_1"
SEED_PAYLOAD = "seed_payload_1"


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions - Interface Component)
# ==============================================================================

@dataclass
class TaskWorkerState:
    """Model state for the task execution worker and its collaborator queue."""

    available: bool = True
    failing: set[str] = field(default_factory=set)
    pending: list[tuple[str, str]] = field(default_factory=list)
    outcomes: dict[str, str] = field(default_factory=dict)
    processed: int = 0
    last_task_id: Optional[str] = None


class TaskWorkerStateMachine(StateMachine[TaskWorkerState]):
    """Unified Pretense state machine for the task worker interface."""

    def __init__(
        self,
        state: Optional[TaskWorkerState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> TaskWorkerState:
        """Constructs the initial (blank) model state for a task worker."""
        return TaskWorkerState()

    @transition(task_worker.TaskWorker.execute)
    def execute(self, task_id: str, payload: str) -> str:
        """Executes a workload payload and records its completion outcome."""
        require_env(self.state.available, task_worker.WorkerExecutionException, task_id, payload)
        require_env(
            task_id not in self.state.failing,
            task_worker.WorkerExecutionException,
            task_id,
            payload,
        )
        require_arg(task_id, Domain.type(str), preferred=["task_1", "task_2"])
        require_arg(payload, Domain.type(str), preferred=["payload_1", "payload_2"])
        ret = self.inner_execute(task_id, payload)
        outcome = f"PROCESSED:{payload.upper()}"
        assert ret == outcome
        self.state.processed += 1
        self.state.last_task_id = task_id
        self.state.outcomes[task_id] = outcome
        return ret

    def inner_execute(self, task_id: str, payload: str) -> str:
        return f"PROCESSED:{payload.upper()}"

    @transition(task_worker.TaskWorker.fetch_and_execute)
    def fetch_and_execute(self) -> str:
        """Dispatches and executes the next pending task from the collaborator queue."""
        require_env(self.state.available, task_worker.WorkerExecutionException)
        require(len(self.state.pending) > 0, error=task_worker.WorkerError)
        ret = self.inner_fetch_and_execute()
        task_id, payload = self.state.pending.pop(0)
        outcome = f"PROCESSED:{payload.upper()}"
        assert ret == task_id
        self.state.processed += 1
        self.state.last_task_id = task_id
        self.state.outcomes[task_id] = outcome
        return ret

    def inner_fetch_and_execute(self) -> str:
        return self.state.pending[0][0]

    @transition(task_worker.TaskWorker.set_failing_task)
    def set_failing_task(self, task_id: str, failing: bool) -> None:
        """Configures whether the designated task fails during execution."""
        require_arg(task_id, Domain.type(str), preferred=["task_1", "task_2"])
        require_arg(failing, Domain.type(bool), preferred=[True, False])
        self.inner_set_failing_task(task_id, failing)
        if failing:
            self.state.failing.add(task_id)
        else:
            self.state.failing.discard(task_id)
        assert (task_id in self.state.failing) == failing

    def inner_set_failing_task(self, task_id: str, failing: bool) -> None:
        return None

    @transition.seeding
    def seed_pending_task(self) -> None:
        """Seeds one pending collaborator task so execution can start from a blank state."""
        self.state.pending.append((SEED_TASK_ID, SEED_PAYLOAD))


proto = TaskWorkerStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeTaskWorker = synthesize_fake(TaskWorkerStateMachine)


def make_task_worker_fake(state: Optional[TaskWorkerState] = None) -> task_worker.TaskWorker:
    """Synthesizes a fake task worker backed by the model state."""
    return FakeTaskWorker(state=state or proto.make_initial_state())


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

class TestTaskWorkerFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding."""

    def setUp(self) -> None:
        self.fake = make_task_worker_fake()
        self.sm = TaskWorkerStateMachine(singletons={task_worker.TaskWorker: self.fake})

    def test_model_transitions(self) -> None:
        self.sm.seed_pending_task()
        assert self.sm.execute("task_1", "payload_1") == "PROCESSED:PAYLOAD_1"
        self.sm.set_failing_task("task_2", True)
        self.sm.set_failing_task("task_2", False)
        assert self.sm.fetch_and_execute() == SEED_TASK_ID

    def test_fake_transitions(self) -> None:
        self.fake.set_failing_task("task_2", True)
        self.fake.set_failing_task("task_2", False)
        assert self.fake.execute("task_1", "payload_1") == "PROCESSED:PAYLOAD_1"


# Fake Fuzzing (Exercises synthesized fake against state machine contracts):
FakeTaskWorkerFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeTaskWorkerFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:08:11Z
# LAST_CHANGED: 2026-11-12T21:08:11Z
# CHANGE: Modeled the TaskWorker interface as a Pretense state machine: 1:1 transitions for execute/fetch_and_execute/set_failing_task, require_env operational-fault guards versus WorkerError precondition guards, collaborator queue state, seeding transition, synthesized verified fake, fixed fake tests, and fake property fuzzing.
# --- END AUTOFAB METADATA ---
