# === File: ring_buffer_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Optional

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from ring_buffer_deepseek_flash_3.parts.ring_buffer.lib import ring_buffer_impl
from ring_buffer_deepseek_flash_3.parts.ring_buffer.lib.ring_buffer import (
    BufferEmptyError,
    RingBuffer,
)
from ring_buffer_deepseek_flash_3.parts.ring_buffer.lib.ring_buffer_impl import (
    RingBuffer as RingBufferImpl,
)
from ring_buffer_deepseek_flash_3.parts.ring_buffer.pretense.ring_buffer_pretense import (
    DEFAULT_CAPACITY,
    RingBufferStateMachine,
)

# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine binding the concrete ring buffer singleton.

    Zero state dataclasses and zero require_arg statements: model state, domains,
    and preconditions are inherited from RingBufferStateMachine.
    """

    def inner_capacity(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        ret = target.capacity
        assert ret == self.state.capacity
        return ret

    def inner_size(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        ret = target.size
        assert ret == len(self.state.items)
        return ret

    def inner_is_empty(self) -> bool:
        target: RingBuffer = sut(RingBuffer)
        ret = target.is_empty
        assert ret == (len(self.state.items) == 0)
        return ret

    def inner_is_full(self) -> bool:
        target: RingBuffer = sut(RingBuffer)
        ret = target.is_full
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret

    def inner_push(self, item: Any) -> Optional[Any]:
        target: RingBuffer = sut(RingBuffer)
        old_size = target.size
        assert old_size == len(self.state.items)
        ret = target.push(item)
        if old_size == self.state.capacity:
            assert ret == self.state.items[0]
            assert target.size == old_size
            assert target.is_full
        else:
            assert ret is None
            assert target.size == old_size + 1
        return ret

    def inner_pop(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        assert target.size == len(self.state.items)
        ret = target.pop()
        assert target.size == len(self.state.items) - 1
        assert ret == self.state.items[0]
        return ret

    def inner_clear(self) -> None:
        target: RingBuffer = sut(RingBuffer)
        target.clear()
        assert target.size == 0
        assert target.is_empty
        assert target.snapshot_items() == []
        return None

    def inner_snapshot_items(self) -> list[Any]:
        target: RingBuffer = sut(RingBuffer)
        ret = target.snapshot_items()
        assert ret == list(self.state.items)
        return ret


proto = RingBufferImplPseudoStateMachine()


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestRingBufferImplReal(LifecycleTestCase):
    """Verifies that the concrete ring buffer implementation satisfies its contracts."""

    def setUp(self) -> None:
        super().setUp()
        self.real = self.get_singleton(RingBufferImpl)
        self.sm = RingBufferImplPseudoStateMachine(
            singletons={RingBuffer: self.real, RingBufferImpl: self.real}
        )
        self.checked = self.sm.as_checked(RingBuffer, self.real)

    def test_push_pop_fifo(self) -> None:
        """Exercises FIFO ordering across push, pop, size, and snapshot queries."""
        assert self.checked.is_empty
        assert self.checked.size == 0
        assert self.checked.capacity == DEFAULT_CAPACITY
        assert not self.checked.is_full
        assert self.checked.snapshot_items() == []
        assert self.checked.push(0) is None
        assert self.checked.push(1) is None
        assert self.checked.size == 2
        assert not self.checked.is_empty
        assert not self.checked.is_full
        assert self.checked.snapshot_items() == [0, 1]
        assert self.checked.pop() == 0
        assert self.checked.snapshot_items() == [1]
        assert self.checked.pop() == 1
        assert self.checked.size == 0
        assert self.checked.is_empty
        assert self.checked.snapshot_items() == []

    def test_push_overwrite_eviction(self) -> None:
        """Exercises overwrite eviction once the buffer reaches capacity."""
        assert self.checked.push(0) is None
        assert self.checked.push(1) is None
        assert self.checked.push(2) is None
        assert self.checked.push(3) is None
        assert self.checked.push(4) is None
        assert self.checked.push(5) is None
        assert self.checked.push(6) is None
        assert self.checked.push(7) is None
        assert self.checked.push(8) is None
        assert self.checked.push(9) is None
        assert self.checked.size == DEFAULT_CAPACITY
        assert self.checked.is_full
        assert self.checked.snapshot_items() == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        assert self.checked.push(10) == 0
        assert self.checked.size == DEFAULT_CAPACITY
        assert self.checked.snapshot_items() == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        assert self.checked.push(11) == 1
        assert self.checked.snapshot_items() == [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

    def test_clear_resets_buffer(self) -> None:
        """Exercises clear removing every stored item and resetting size."""
        assert self.checked.push(5) is None
        assert self.checked.push(6) is None
        assert self.checked.size == 2
        self.checked.clear()
        assert self.checked.size == 0
        assert self.checked.is_empty
        assert not self.checked.is_full
        assert self.checked.snapshot_items() == []
        assert self.checked.capacity == DEFAULT_CAPACITY

    def test_pop_on_empty_violates_contract(self) -> None:
        """Exercises the contracted empty-buffer pop violation."""
        assert self.checked.is_empty
        self.checked.violating(BufferEmptyError).pop()


# ==============================================================================
# 6. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================

def make_sut() -> RingBufferImpl:
    """Builds a freshly initialized concrete ring buffer singleton."""
    registry = LifecycleRegistry()
    registry.register_module(ring_buffer_impl)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(RingBufferImpl)


RingBufferFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="RingBufferFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T23:26:17Z
# LAST_CHANGED: 2026-11-11T23:25:49Z
# CHANGE: Implemented RingBuffer implementation pretense: RingBufferImplPseudoStateMachine inheriting the interface state machine and overriding only inner transitions to drive the concrete RingBuffer singleton via sut(RingBuffer) with SUT/model parity asserts, plus TestRingBufferImplReal scenarios (FIFO push/pop, overwrite eviction at capacity, clear reset, violating(BufferEmptyError).pop()) and compiled real fuzz test via make_sut.
# PRETENSE_COVERAGE_AUDIT: 2026-11-11T23:26:17Z
# PRETENSE_QA_AUDIT: 2026-11-11T23:26:04Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_pretense.py ===
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
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from ring_buffer_deepseek_flash_3.parts.ring_buffer.lib.ring_buffer import RingBuffer

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

# Open model parameter: the concrete capacity specialization lives in the model
# initial state so implementation pseudo-state machines can override it.
DEFAULT_CAPACITY = 10


@dataclass
class RingBufferState:
    """Canonical model state for a bounded circular FIFO buffer."""

    capacity: int = DEFAULT_CAPACITY
    items: list[Any] = field(default_factory=list)


class RingBufferStateMachine(StateMachine[RingBufferState]):
    """Unified Pretense State Machine for the RingBuffer interface."""

    def __init__(
        self,
        state: Optional[RingBufferState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> RingBufferState:
        """Constructs initial model state for an empty buffer of default capacity."""
        return RingBufferState()

    # --------------------------------------------------------------------------
    # Queries (properties modeled with named transitions for Protocol access)
    # --------------------------------------------------------------------------

    @transition(name="capacity")
    def capacity(self) -> int:
        ret = self.inner_capacity()
        assert ret == self.state.capacity
        return ret

    def inner_capacity(self) -> int:
        """Computes the fake capacity return value."""
        return self.state.capacity

    @transition(name="size")
    def size(self) -> int:
        ret = self.inner_size()
        assert ret == len(self.state.items)
        return ret

    def inner_size(self) -> int:
        """Computes the fake size return value."""
        return len(self.state.items)

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        ret = self.inner_is_empty()
        assert ret == (len(self.state.items) == 0)
        return ret

    def inner_is_empty(self) -> bool:
        """Computes the fake emptiness return value."""
        return len(self.state.items) == 0

    @transition(name="is_full")
    def is_full(self) -> bool:
        ret = self.inner_is_full()
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret

    def inner_is_full(self) -> bool:
        """Computes the fake saturation return value."""
        return len(self.state.items) >= self.state.capacity

    # --------------------------------------------------------------------------
    # Operations
    # --------------------------------------------------------------------------

    @transition(RingBuffer.push)
    def push(self, item: Any) -> Optional[Any]:
        require_arg(item, Domain.type(int))
        ret = self.inner_push(item)
        if len(self.state.items) == self.state.capacity:
            evicted = self.state.items[0]
            self.state.items.pop(0)
            self.state.items.append(item)
            assert ret == evicted
            assert len(self.state.items) == self.state.capacity
        else:
            self.state.items.append(item)
            assert ret is None
        assert len(self.state.items) <= self.state.capacity
        return ret

    def inner_push(self, item: Any) -> Optional[Any]:
        """Computes the fake push return value: evicted oldest item or None."""
        if len(self.state.items) == self.state.capacity:
            return self.state.items[0]
        return None

    @transition(RingBuffer.pop)
    def pop(self) -> Any:
        require(len(self.state.items) > 0)
        ret = self.inner_pop()
        assert ret == self.state.items[0]
        self.state.items.pop(0)
        return ret

    def inner_pop(self) -> Any:
        """Computes the fake pop return value: the oldest stored item."""
        return self.state.items[0]

    @transition(RingBuffer.clear)
    def clear(self) -> None:
        self.inner_clear()
        self.state.items.clear()
        assert len(self.state.items) == 0

    def inner_clear(self) -> None:
        """Computes the fake clear return value (always None)."""
        return None

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(self) -> list[Any]:
        ret = self.inner_snapshot_items()
        assert ret == list(self.state.items)
        return ret

    def inner_snapshot_items(self) -> list[Any]:
        """Computes the fake snapshot return value in FIFO arrival order."""
        return list(self.state.items)

    # --------------------------------------------------------------------------
    # Seeding Transition
    # --------------------------------------------------------------------------

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds a blank buffer state for fake fuzzing."""
        self.state.items.clear()


proto = RingBufferStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeRingBuffer = synthesize_fake(RingBufferStateMachine)


def make_ring_buffer_fake(state: Optional[RingBufferState] = None) -> RingBuffer:
    """Synthesizes a fake RingBuffer sharing the model state machine."""
    initial = state if state is not None else proto.make_initial_state()
    return FakeRingBuffer(state=initial)


# Fake Fuzzing (Exercises synthesized fake against state machine contracts):
FakeRingBufferFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeRingBufferFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

class TestRingBufferFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_ring_buffer_fake()
        self.sm = RingBufferStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        assert self.fake.capacity == DEFAULT_CAPACITY
        assert self.fake.size == 0
        assert self.fake.is_empty
        assert not self.fake.is_full
        assert self.fake.push(0) is None
        assert self.fake.push(1) is None
        assert self.fake.size == 2
        assert not self.fake.is_empty
        assert self.fake.snapshot_items() == [0, 1]
        assert self.fake.pop() == 0
        assert self.fake.snapshot_items() == [1]
        self.fake.clear()
        assert self.fake.size == 0
        assert self.fake.is_empty

    def test_eviction_coverage(self) -> None:
        """Exercises the overwrite-eviction branch of push on the fake."""
        assert self.fake.push(0) is None
        assert self.fake.push(1) is None
        assert self.fake.push(2) is None
        assert self.fake.push(3) is None
        assert self.fake.push(4) is None
        assert self.fake.push(5) is None
        assert self.fake.push(6) is None
        assert self.fake.push(7) is None
        assert self.fake.push(8) is None
        assert self.fake.push(9) is None
        assert self.fake.size == DEFAULT_CAPACITY
        assert self.fake.is_full
        assert self.fake.push(10) == 0
        assert self.fake.size == DEFAULT_CAPACITY
        assert self.fake.snapshot_items() == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T23:25:42Z
# LAST_CHANGED: 2026-11-11T23:25:42Z
# CHANGE: Implemented RingBuffer interface pretense: RingBufferState model (capacity + FIFO items), 1:1 transitions for capacity/size/is_empty/is_full/push/pop/clear/snapshot_items with inner transition delegation and postcondition asserts, seed_initial seeding transition, synthesized FakeRingBuffer + factory, fake fuzz compilation, and TestRingBufferFake covering every transition including overwrite eviction.
# --- END AUTOFAB METADATA ---
