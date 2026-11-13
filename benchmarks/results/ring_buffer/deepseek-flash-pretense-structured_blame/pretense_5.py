# === File: ring_buffer_impl_pretense.py ===
from __future__ import annotations

from typing import Any, List, Optional

from pretense import sut
from support.lib.lifecycle import LifecycleTestCase

from ring_buffer_deepseek_flash_1.parts.ring_buffer.lib import ring_buffer
from ring_buffer_deepseek_flash_1.parts.ring_buffer.lib import ring_buffer_impl
from ring_buffer_deepseek_flash_1.parts.ring_buffer.pretense.ring_buffer_pretense import RingBufferStateMachine

# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Component)
# ==============================================================================


class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine binding the concrete ring buffer SUT."""

    def inner_capacity(self) -> int:
        target: ring_buffer_impl.RingBuffer = sut(ring_buffer_impl.RingBuffer)
        ret = target.capacity
        assert ret == self.state.capacity
        return ret

    def inner_size(self) -> int:
        target: ring_buffer_impl.RingBuffer = sut(ring_buffer_impl.RingBuffer)
        ret = target.size
        assert ret == len(self.state.items)
        return ret

    def inner_is_empty(self) -> bool:
        target: ring_buffer_impl.RingBuffer = sut(ring_buffer_impl.RingBuffer)
        ret = target.is_empty
        assert ret == (len(self.state.items) == 0)
        return ret

    def inner_is_full(self) -> bool:
        target: ring_buffer_impl.RingBuffer = sut(ring_buffer_impl.RingBuffer)
        ret = target.is_full
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret

    def inner_push(self, item: Any) -> Optional[Any]:
        target: ring_buffer_impl.RingBuffer = sut(ring_buffer_impl.RingBuffer)
        size_before = target.size
        if size_before == target.capacity:
            evicted = target.snapshot_items()[0]
            ret = target.push(item)
            assert ret == evicted
            assert target.size == target.capacity
            assert target.snapshot_items()[-1] == item
        else:
            ret = target.push(item)
            assert ret is None
            assert target.size == size_before + 1
        return ret

    def inner_pop(self) -> Any:
        target: ring_buffer_impl.RingBuffer = sut(ring_buffer_impl.RingBuffer)
        was_empty = target.is_empty
        oldest = None if was_empty else target.snapshot_items()[0]
        size_before = target.size
        ret = target.pop()
        assert ret == oldest
        assert target.size == size_before - 1
        return ret

    def inner_clear(self) -> None:
        target: ring_buffer_impl.RingBuffer = sut(ring_buffer_impl.RingBuffer)
        target.clear()
        assert target.size == 0
        assert target.is_empty is True
        return None

    def inner_snapshot_items(self) -> List[Any]:
        target: ring_buffer_impl.RingBuffer = sut(ring_buffer_impl.RingBuffer)
        items = target.snapshot_items()
        assert items == list(self.state.items)
        return items


# ==============================================================================
# 2. Real Implementation Tests (Implementation Component)
# ==============================================================================


class TestRingBufferImplReal(LifecycleTestCase):
    """Verifies that the concrete ring buffer implementation satisfies all contracts."""

    target = ring_buffer_impl.RingBuffer

    def setUp(self) -> None:
        super().setUp()
        self.real = self.sut
        self.sm = RingBufferImplPseudoStateMachine(
            singletons={ring_buffer_impl.RingBuffer: self.real}
        )
        self.checked = self.sm.as_checked(ring_buffer_impl.RingBuffer, self.real)

    def test_capacity_and_state_queries(self) -> None:
        """Exercises the capacity, size, emptiness, fullness, and snapshot queries."""
        assert self.checked.capacity == 10
        assert self.checked.size == 0
        assert self.checked.is_empty is True
        assert self.checked.is_full is False
        assert self.checked.snapshot_items() == []

    def test_push_pop_fifo(self) -> None:
        """Exercises the available-capacity push, FIFO pop, and non-mutating snapshot."""
        assert self.checked.push(1) is None
        assert self.checked.push(2) is None
        assert self.checked.push(3) is None
        assert self.checked.size == 3
        assert self.checked.is_empty is False
        assert self.checked.is_full is False
        assert self.checked.snapshot_items() == [1, 2, 3]
        assert self.checked.pop() == 1
        assert self.checked.pop() == 2
        assert self.checked.size == 1
        assert self.checked.snapshot_items() == [3]

    def test_overwrite_eviction(self) -> None:
        """Exercises the saturation overwrite-eviction branch of push."""
        assert self.checked.push(1) is None
        assert self.checked.push(2) is None
        assert self.checked.push(3) is None
        assert self.checked.push(4) is None
        assert self.checked.push(5) is None
        assert self.checked.push(6) is None
        assert self.checked.push(7) is None
        assert self.checked.push(8) is None
        assert self.checked.push(9) is None
        assert self.checked.push(10) is None
        assert self.checked.is_full is True
        assert self.checked.push(11) == 1
        assert self.checked.size == 10
        assert self.checked.snapshot_items() == [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

    def test_clear_resets(self) -> None:
        """Exercises the clear transition resetting size to zero."""
        assert self.checked.push(1) is None
        assert self.checked.push(2) is None
        self.checked.clear()
        assert self.checked.size == 0
        assert self.checked.is_empty is True
        assert self.checked.snapshot_items() == []

    def test_pop_empty_violation(self) -> None:
        """Exercises the contracted BufferEmptyError precondition of pop."""
        self.checked.violating(ring_buffer.BufferEmptyError).pop()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T20:59:14Z
# LAST_CHANGED: 2026-11-12T20:58:47Z
# CHANGE: Fix pretense_qa unbound-target feedback: declare target = ring_buffer_impl.RingBuffer on TestRingBufferImplReal so LifecycleTestCase.setUp resolves self.sut instead of leaving it None, and register/bind the concrete implementation class in singletons and as_checked; inner transitions now look up sut(ring_buffer_impl.RingBuffer) under the same concrete key.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T20:59:14Z
# PRETENSE_QA_AUDIT: 2026-11-12T20:59:00Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional
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

from ring_buffer_deepseek_flash_1.parts.ring_buffer.lib import ring_buffer

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Component)
# ==============================================================================


@dataclass
class RingBufferState:
    """Abstract model state for a bounded circular FIFO buffer with overwrite eviction."""

    capacity: int = 10
    items: List[Any] = field(default_factory=list)


class RingBufferStateMachine(StateMachine[RingBufferState]):
    """Pretense state machine modeling the bounded circular ring buffer 1:1."""

    def __init__(
        self,
        state: Optional[RingBufferState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    @property
    def default_capacity(self) -> int:
        """Open parameter: default buffer capacity used for blank initial states."""
        return 10

    def make_initial_state(self) -> RingBufferState:
        """Constructs a blank initial model state using the open default capacity."""
        return RingBufferState(capacity=self.default_capacity)

    # -- capacity -----------------------------------------------------------------

    @transition(name="capacity")
    def capacity(self) -> int:
        ret = self.inner_capacity()
        assert ret == self.state.capacity
        return ret

    def inner_capacity(self) -> int:
        """Computes the fake capacity return value from abstract model state."""
        return self.state.capacity

    # -- size ---------------------------------------------------------------------

    @transition(name="size")
    def size(self) -> int:
        ret = self.inner_size()
        assert ret == len(self.state.items)
        return ret

    def inner_size(self) -> int:
        """Computes the fake size return value from abstract model state."""
        return len(self.state.items)

    # -- is_empty -----------------------------------------------------------------

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        ret = self.inner_is_empty()
        assert ret == (len(self.state.items) == 0)
        return ret

    def inner_is_empty(self) -> bool:
        """Computes the fake emptiness return value from abstract model state."""
        return len(self.state.items) == 0

    # -- is_full ------------------------------------------------------------------

    @transition(name="is_full")
    def is_full(self) -> bool:
        ret = self.inner_is_full()
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret

    def inner_is_full(self) -> bool:
        """Computes the fake fullness return value from abstract model state."""
        return len(self.state.items) >= self.state.capacity

    # -- push ---------------------------------------------------------------------

    @transition("push")
    def push(self, item: Any) -> Optional[Any]:
        require_arg(item, Domain.type(int), preferred=[1, 2, 3])
        was_full = len(self.state.items) == self.state.capacity
        ret = self.inner_push(item)
        if was_full:
            assert ret == self.state.items[0]
            self.state.items.pop(0)
        else:
            assert ret is None
        self.state.items.append(item)
        assert len(self.state.items) <= self.state.capacity
        return ret

    def inner_push(self, item: Any) -> Optional[Any]:
        """Computes the fake eviction return value from abstract model state."""
        if len(self.state.items) == self.state.capacity:
            return self.state.items[0]
        return None

    # -- pop ----------------------------------------------------------------------

    @transition("pop")
    def pop(self) -> Any:
        require(bool(self.state.items), ring_buffer.BufferEmptyError)
        ret = self.inner_pop()
        assert ret == self.state.items[0]
        self.state.items.pop(0)
        assert len(self.state.items) < self.state.capacity
        return ret

    def inner_pop(self) -> Any:
        """Computes the fake oldest-item return value from abstract model state."""
        return self.state.items[0]

    # -- clear --------------------------------------------------------------------

    @transition("clear")
    def clear(self) -> None:
        ret = self.inner_clear()
        self.state.items.clear()
        assert len(self.state.items) == 0
        return ret

    def inner_clear(self) -> None:
        """Clears the faked buffer (fake return value is None)."""
        return None

    # -- snapshot_items -----------------------------------------------------------

    @transition("snapshot_items")
    def snapshot_items(self) -> List[Any]:
        size_before = len(self.state.items)
        ret = self.inner_snapshot_items()
        assert ret == list(self.state.items)
        assert len(self.state.items) == size_before
        return ret

    def inner_snapshot_items(self) -> List[Any]:
        """Computes the fake FIFO snapshot from abstract model state."""
        return list(self.state.items)

    # -- seeding ------------------------------------------------------------------

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the blank initial model state from the open default capacity."""
        self.state.capacity = self.default_capacity
        self.state.items.clear()


proto = RingBufferStateMachine()


# ==============================================================================
# 2. Synthetic Fake (Interface Component)
# ==============================================================================

FakeRingBuffer = synthesize_fake(RingBufferStateMachine)


def make_ring_buffer_fake(state: Optional[RingBufferState] = None) -> ring_buffer.RingBuffer:
    """Synthesizes a fake ring buffer instance for the given model state."""
    return FakeRingBuffer(state=state or proto.make_initial_state())


# Fake Fuzzing (Exercises the synthesized fake against modeled contracts):
FakeRingBufferFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeRingBufferFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Component)
# ==============================================================================


class TestRingBufferFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all 1:1 transitions."""

    def setUp(self) -> None:
        self.fake = make_ring_buffer_fake()
        self.sm = RingBufferStateMachine(singletons={ring_buffer.RingBuffer: self.fake})

    def test_capacity_and_state_queries(self) -> None:
        """Exercises the seeding and read-only transitions on a blank fake."""
        self.sm.seed_initial()
        assert self.fake.capacity == 10
        assert self.fake.size == 0
        assert self.fake.is_empty is True
        assert self.fake.is_full is False
        assert self.fake.snapshot_items() == []

    def test_push_pop_and_clear(self) -> None:
        """Exercises the available-capacity push, pop, and clear transitions."""
        assert self.fake.push(1) is None
        assert self.fake.push(2) is None
        assert self.fake.size == 2
        assert self.fake.is_empty is False
        assert self.fake.is_full is False
        assert self.fake.snapshot_items() == [1, 2]
        assert self.fake.pop() == 1
        assert self.fake.snapshot_items() == [2]
        self.fake.clear()
        assert self.fake.size == 0
        assert self.fake.is_empty is True

    def test_overwrite_eviction(self) -> None:
        """Exercises the saturation overwrite-eviction branch of push."""
        assert self.fake.push(1) is None
        assert self.fake.push(2) is None
        assert self.fake.push(3) is None
        assert self.fake.push(4) is None
        assert self.fake.push(5) is None
        assert self.fake.push(6) is None
        assert self.fake.push(7) is None
        assert self.fake.push(8) is None
        assert self.fake.push(9) is None
        assert self.fake.push(10) is None
        assert self.fake.is_full is True
        assert self.fake.push(11) == 1
        assert self.fake.size == 10
        assert self.fake.snapshot_items() == [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T20:54:50Z
# LAST_CHANGED: 2026-11-12T20:54:50Z
# CHANGE: Author RingBuffer interface pretense: RingBufferState dataclass and RingBufferStateMachine with 1:1 transitions (capacity/size/is_empty/is_full/push with overwrite eviction/pop with BufferEmptyError precondition/clear/snapshot_items), seeding transition, synthesize_fake fake + factory, fixed fake scenario tests covering all transitions, and compiled Hypothesis fake fuzz test.
# --- END AUTOFAB METADATA ---
