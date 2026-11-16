# === File: ring_buffer_impl_pretense.py ===
from __future__ import annotations

from typing import Any, List, Optional

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from ring_buffer_deepseek_flash_1.parts.ring_buffer.lib.ring_buffer import (
    BufferEmptyError,
    RingBuffer,
)
from ring_buffer_deepseek_flash_1.parts.ring_buffer.lib.ring_buffer_impl import (
    RingBuffer as RingBufferImpl,
)
from ring_buffer_deepseek_flash_1.parts.ring_buffer.pretense.ring_buffer_pretense import (
    RingBufferStateMachine,
)

# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine binding the concrete RingBuffer SUT."""

    @property
    def default_capacity(self) -> int:
        """Specializes the open capacity parameter to the concrete buffer default."""
        return 10

    def inner_capacity(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        return target.capacity

    def inner_size(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        return target.size

    def inner_is_empty(self) -> bool:
        target: RingBuffer = sut(RingBuffer)
        return target.is_empty

    def inner_is_full(self) -> bool:
        target: RingBuffer = sut(RingBuffer)
        return target.is_full

    def inner_push(self, item: Any) -> Optional[Any]:
        target: RingBuffer = sut(RingBuffer)
        old_size = target.size
        evicted = target.push(item)
        if old_size >= target.capacity:
            assert target.size == target.capacity
            assert target.is_full
            assert target.snapshot_items()[-1] == item
        else:
            assert evicted is None
            assert target.size == old_size + 1
            assert target.snapshot_items()[-1] == item
        return evicted

    def inner_pop(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        old_size = target.size
        ret = target.pop()
        assert target.size == old_size - 1
        assert not target.is_full
        return ret

    def inner_clear(self) -> None:
        target: RingBuffer = sut(RingBuffer)
        target.clear()
        assert target.size == 0
        assert target.is_empty
        assert target.snapshot_items() == []
        return None

    def inner_snapshot_items(self) -> List[Any]:
        target: RingBuffer = sut(RingBuffer)
        old_size = target.size
        old_capacity = target.capacity
        ret = target.snapshot_items()
        assert target.size == old_size
        assert target.capacity == old_capacity
        return ret


impl_proto = RingBufferImplPseudoStateMachine()


# ==============================================================================
# 6. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================


def make_sut() -> RingBuffer:
    """Constructs a fresh lifecycle scope with the concrete RingBuffer singleton."""
    registry = LifecycleRegistry()
    registry.register_singleton(RingBufferImpl)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(RingBufferImpl)


RingBufferFuzzTest = compile_hypothesis_test_case(
    proto=impl_proto,
    sut_factory=make_sut,
    initial_state_factory=impl_proto.make_initial_state,
    name="RingBufferFuzzTest",
)


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================


class TestRingBufferImplReal(LifecycleTestCase):
    """Verifies concrete RingBuffer behavior for coverage-requested boundary scenarios."""

    def setUp(self) -> None:
        super().setUp()
        self.real = self.sut
        self.sm = RingBufferImplPseudoStateMachine(singletons={RingBuffer: self.real})
        self.checked = self.sm.as_checked(RingBuffer, self.real)

    def test_push_overwrite_eviction_at_capacity(self) -> None:
        """Saturates the buffer then overflows once to exercise overwrite eviction."""
        self.checked.push(1)
        self.checked.push(2)
        self.checked.push(3)
        self.checked.push(4)
        self.checked.push(5)
        self.checked.push(6)
        self.checked.push(7)
        self.checked.push(8)
        self.checked.push(9)
        self.checked.push(10)
        self.checked.push(11)

    def test_pop_empty_buffer_violation(self) -> None:
        """Verifies the contracted empty-buffer removal error on the real SUT."""
        self.checked.violating(BufferEmptyError).pop()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T20:27:59Z
# LAST_CHANGED: 2026-11-14T20:27:35Z
# CHANGE: Addressed pretense_coverage feedback with fixed real-SUT scenarios in TestRingBufferImplReal: (1) push overwrite eviction now saturates the buffer to capacity 10 and overflows once, exercising the eviction postcondition and returning the evicted oldest item; (2) terminal self.checked.violating(BufferEmptyError).pop() exercises the empty-buffer removal precondition error. Wiring uses LifecycleTestCase setUp with super().setUp(), sut alias, pseudo-SM singletons, and as_checked RingBuffer adapter.
# PRETENSE_COVERAGE_AUDIT: 2026-11-14T20:27:59Z
# PRETENSE_QA_AUDIT: 2026-11-14T20:27:46Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional
import unittest

from pretense import (
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

from ring_buffer_deepseek_flash_1.parts.ring_buffer.lib.ring_buffer import (
    BufferEmptyError,
    RingBuffer,
)

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class RingBufferState:
    """Canonical model state for the bounded circular ring buffer."""

    capacity: int = 2
    items: list[Any] = field(default_factory=list)


class RingBufferStateMachine(StateMachine[RingBufferState]):
    """Unified Pretense state machine for the RingBuffer interface."""

    def __init__(
        self,
        state: Optional[RingBufferState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    @property
    def default_capacity(self) -> int:
        """Open capacity parameter used by the model and specialized by implementations."""
        return 2

    def make_initial_state(self) -> RingBufferState:
        """Constructs the default model state from the overridable capacity parameter."""
        return RingBufferState(capacity=self.default_capacity)

    def inner_capacity(self) -> int:
        return self.state.capacity

    def inner_size(self) -> int:
        return len(self.state.items)

    def inner_is_empty(self) -> bool:
        return len(self.state.items) == 0

    def inner_is_full(self) -> bool:
        return len(self.state.items) >= self.state.capacity

    def inner_push(self, item: Any) -> Optional[Any]:
        if len(self.state.items) >= self.state.capacity:
            return self.state.items[0]
        return None

    def inner_pop(self) -> Any:
        return self.state.items[0]

    def inner_clear(self) -> None:
        return None

    def inner_snapshot_items(self) -> List[Any]:
        return list(self.state.items)

    @transition(name="capacity")
    def capacity(self) -> int:
        ret = self.inner_capacity()
        assert ret == self.state.capacity
        return ret

    @transition(name="size")
    def size(self) -> int:
        ret = self.inner_size()
        assert ret == len(self.state.items)
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        ret = self.inner_is_empty()
        assert ret == (len(self.state.items) == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        ret = self.inner_is_full()
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret

    @transition(RingBuffer.push)
    def push(self, item: Any) -> Optional[Any]:
        require_arg(item, int)
        was_full = len(self.state.items) >= self.state.capacity
        ret = self.inner_push(item)
        if was_full:
            evicted = self.state.items.pop(0)
            self.state.items.append(item)
            assert ret == evicted
            assert len(self.state.items) == self.state.capacity
        else:
            self.state.items.append(item)
            assert ret is None
            assert len(self.state.items) <= self.state.capacity
        return ret

    @transition(RingBuffer.pop)
    def pop(self) -> Any:
        require(bool(self.state.items))
        ret = self.inner_pop()
        expected = self.state.items.pop(0)
        assert ret == expected
        assert len(self.state.items) >= 0
        return ret

    @transition(RingBuffer.clear)
    def clear(self) -> None:
        self.inner_clear()
        self.state.items.clear()
        assert len(self.state.items) == 0

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(self) -> List[Any]:
        old_size = len(self.state.items)
        ret = self.inner_snapshot_items()
        assert list(ret) == list(self.state.items)
        assert len(self.state.items) == old_size
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the buffer model with a valid bounded capacity."""
        self.state.capacity = self.default_capacity


proto = RingBufferStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeRingBuffer = synthesize_fake(RingBufferStateMachine)


def make_ring_buffer_fake(state: Optional[RingBufferState] = None) -> RingBuffer:
    """Synthesizes a fake RingBuffer bound to the model state machine."""
    return FakeRingBuffer(state=state or proto.make_initial_state())


FakeRingBufferFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeRingBufferFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestRingBufferFake(unittest.TestCase):
    """Fixed fake scenarios for factory wiring and non-destructive snapshot queries."""

    def setUp(self) -> None:
        self.fake = make_ring_buffer_fake()
        self.sm = RingBufferStateMachine(singletons={RingBuffer: self.fake})

    def test_snapshot_after_eviction(self) -> None:
        """Exercises the synthetic fake factory and the test-only FIFO snapshot accessor."""
        self.sm.seed_initial()
        self.assertEqual(self.fake.capacity, 2)
        self.assertEqual(self.fake.push(1), None)
        self.assertEqual(self.fake.push(2), None)
        self.assertEqual(self.fake.push(3), 1)
        self.assertEqual(self.fake.snapshot_items(), [2, 3])
        self.assertTrue(self.fake.is_full)
        self.assertFalse(self.fake.is_empty)
        self.assertEqual(self.fake.size, 2)
        self.assertEqual(self.fake.pop(), 2)
        self.assertEqual(self.fake.snapshot_items(), [3])
        self.fake.clear()
        self.assertTrue(self.fake.is_empty)
        self.assertEqual(self.fake.snapshot_items(), [])

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T20:25:11Z
# LAST_CHANGED: 2026-11-14T20:25:11Z
# CHANGE: Implemented RingBuffer interface Pretense state machine: capacity/size/is_empty/is_full property transitions, push (append + overwrite-eviction branch), pop gated on non-empty model state, clear, test-only FIFO snapshot, overridable default capacity hook, seeding transition, synthesized fake with factory, compiled FakeRingBufferFuzzTest, and fixed fake scenario covering factory wiring and FIFO snapshot semantics.
# --- END AUTOFAB METADATA ---
