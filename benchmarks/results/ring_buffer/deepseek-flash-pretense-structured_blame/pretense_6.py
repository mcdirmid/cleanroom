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

from ring_buffer_deepseek_flash_1.parts.ring_buffer.lib import ring_buffer, ring_buffer_impl
from ring_buffer_deepseek_flash_1.parts.ring_buffer.pretense.ring_buffer_pretense import (
    RingBufferStateMachine,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine binding the concrete ring buffer."""

    def inner_capacity(self) -> int:
        target: ring_buffer.RingBuffer = sut(ring_buffer.RingBuffer)
        return target.capacity

    def inner_size(self) -> int:
        target: ring_buffer.RingBuffer = sut(ring_buffer.RingBuffer)
        return target.size

    def inner_is_empty(self) -> bool:
        target: ring_buffer.RingBuffer = sut(ring_buffer.RingBuffer)
        return target.is_empty

    def inner_is_full(self) -> bool:
        target: ring_buffer.RingBuffer = sut(ring_buffer.RingBuffer)
        return target.is_full

    def inner_push(self, item: Any) -> Optional[Any]:
        target: ring_buffer.RingBuffer = sut(ring_buffer.RingBuffer)
        previous_items = target.snapshot_items()
        was_full = target.is_full
        ret = target.push(item)
        if was_full:
            assert ret == previous_items[0]
            assert target.size == target.capacity
        else:
            assert ret is None
            assert target.size == len(previous_items) + 1
        return ret

    def inner_pop(self) -> Any:
        target: ring_buffer.RingBuffer = sut(ring_buffer.RingBuffer)
        previous_items = target.snapshot_items()
        ret = target.pop()
        assert ret == previous_items[0]
        assert target.size == len(previous_items) - 1
        return ret

    def inner_clear(self) -> None:
        target: ring_buffer.RingBuffer = sut(ring_buffer.RingBuffer)
        target.clear()
        assert target.size == 0
        assert target.is_empty

    def inner_snapshot_items(self) -> List[Any]:
        target: ring_buffer.RingBuffer = sut(ring_buffer.RingBuffer)
        items = target.snapshot_items()
        assert target.size == len(items)
        return items


# ==============================================================================
# 2. Hypothesis Stateful Fuzzing on Real Implementation
# ==============================================================================

impl_proto = RingBufferImplPseudoStateMachine()


def make_sut() -> ring_buffer.RingBuffer:
    """Constructs the concrete ring buffer under test within a fresh lifecycle scope."""
    registry = LifecycleRegistry()
    registry.register_singleton(
        ring_buffer_impl.RingBuffer,
        keys=[ring_buffer_impl.RingBuffer, ring_buffer.RingBuffer],
    )
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(ring_buffer_impl.RingBuffer)


RingBufferFuzzTest = compile_hypothesis_test_case(
    proto=impl_proto,
    sut_factory=make_sut,
    initial_state_factory=impl_proto.make_initial_state,
    name="RingBufferFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Real Implementation (Coverage Feedback)
# ==============================================================================

class TestRingBufferImplReal(LifecycleTestCase):
    """Fixed scenarios covering saturated eviction and empty-pop contract errors."""

    target = ring_buffer_impl.RingBuffer

    def setUp(self) -> None:
        super().setUp()
        self.real: ring_buffer.RingBuffer = self.sut
        self.sm = RingBufferImplPseudoStateMachine(
            singletons={ring_buffer.RingBuffer: self.real}
        )
        self.checked = self.sm.as_checked(ring_buffer.RingBuffer, self.real)

    def test_push_evicts_oldest_when_saturated(self) -> None:
        """Deterministically fills to capacity and exercises overwrite eviction."""
        capacity = self.checked.capacity
        for index in range(capacity):
            self.checked.push(index)
        self.checked.push(capacity)

    def test_pop_empty_buffer_violates_contract(self) -> None:
        """Verifies the contracted BufferEmptyError on an empty pop."""
        self.checked.violating(ring_buffer.BufferEmptyError).pop()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T17:58:04Z
# LAST_CHANGED: 2026-11-14T17:57:42Z
# CHANGE: Resolve pretense_coverage feedback by adding TestRingBufferImplReal fixed scenarios: test_push_evicts_oldest_when_saturated deterministically fills to capacity then pushes once more to exercise ring_buffer.push.overwrite_eviction; test_pop_empty_buffer_violates_contract uses terminal checked.violating(BufferEmptyError).pop() to exercise the ring_buffer.pop.empty_buffer error transition. Both drive the concrete SUT through RingBufferImplPseudoStateMachine bound via LifecycleTestCase (target = ring_buffer_impl.RingBuffer, as_checked proxy).
# PRETENSE_COVERAGE_AUDIT: 2026-11-14T17:58:04Z
# PRETENSE_QA_AUDIT: 2026-11-14T17:57:51Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_pretense.py ===
from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import Any, List, Optional

from pretense import (
    StateMachine,
    require,
    require_arg,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from ring_buffer_deepseek_flash_1.parts.ring_buffer.lib.ring_buffer import RingBuffer


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions)
# ==============================================================================

@dataclass
class RingBufferState:
    """Canonical model state for a bounded FIFO circular buffer."""
    capacity: int = 10
    items: list[Any] = field(default_factory=list)


class RingBufferStateMachine(StateMachine[RingBufferState]):
    """Pretense state machine modeling RingBuffer transitions 1:1."""

    def __init__(
        self,
        state: Optional[RingBufferState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> RingBufferState:
        """Constructs an empty buffer initialized to the default capacity."""
        return RingBufferState()

    @transition.seeding
    def seed_capacity(self) -> None:
        """Seeds the configured buffer capacity without storing any items."""
        self.state.capacity = self.make_initial_state().capacity

    @transition(name="capacity")
    def capacity(self) -> int:
        """Reads the maximum number of items the buffer can hold."""
        ret = self.inner_capacity()
        assert ret == self.state.capacity
        return ret

    def inner_capacity(self) -> int:
        return self.state.capacity

    @transition(name="size")
    def size(self) -> int:
        """Reads the current number of stored items."""
        ret = self.inner_size()
        assert ret == len(self.state.items)
        return ret

    def inner_size(self) -> int:
        return len(self.state.items)

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        """Indicates whether the buffer currently holds zero items."""
        ret = self.inner_is_empty()
        assert ret == (len(self.state.items) == 0)
        return ret

    def inner_is_empty(self) -> bool:
        return len(self.state.items) == 0

    @transition(name="is_full")
    def is_full(self) -> bool:
        """Indicates whether the buffer has reached its capacity."""
        ret = self.inner_is_full()
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret

    def inner_is_full(self) -> bool:
        return len(self.state.items) >= self.state.capacity

    @transition(RingBuffer.push)
    def push(self, item: Any) -> Optional[Any]:
        """Appends an item, evicting and returning the oldest when full."""
        require_arg(item, int)
        was_full = len(self.state.items) == self.state.capacity
        evicted = self.state.items[0] if was_full else None
        ret = self.inner_push(item)
        if was_full:
            self.state.items.pop(0)
            self.state.items.append(item)
            assert ret == evicted
        else:
            self.state.items.append(item)
            assert ret is None
        return ret

    def inner_push(self, item: Any) -> Optional[Any]:
        if len(self.state.items) >= self.state.capacity:
            return self.state.items[0]
        return None

    @transition(RingBuffer.pop)
    def pop(self) -> Any:
        """Removes and returns the oldest item from a non-empty buffer."""
        require(len(self.state.items) > 0)
        ret = self.inner_pop()
        expected = self.state.items[0]
        self.state.items.pop(0)
        assert ret == expected
        return ret

    def inner_pop(self) -> Any:
        return self.state.items[0]

    @transition(RingBuffer.clear)
    def clear(self) -> None:
        """Removes every stored item from the buffer."""
        ret = self.inner_clear()
        self.state.items.clear()
        assert ret is None
        return ret

    def inner_clear(self) -> None:
        return None

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(self) -> List[Any]:
        """Returns a non-destructive FIFO snapshot of the stored items."""
        ret = self.inner_snapshot_items()
        assert ret == list(self.state.items)
        return ret

    def inner_snapshot_items(self) -> List[Any]:
        return list(self.state.items)


proto = RingBufferStateMachine()


# ==============================================================================
# 2. Synthesized Fake (Interface Components)
# ==============================================================================

FakeRingBuffer = synthesize_fake(RingBufferStateMachine)


def make_ring_buffer_fake(state: Optional[RingBufferState] = None) -> RingBuffer:
    """Synthesizes a fake ring buffer backed by model state."""
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
    """Fixed fake test covering the synthesized fake factory and eviction."""

    def test_fake_factory_evicts_oldest_when_full(self) -> None:
        fake = make_ring_buffer_fake()
        capacity = fake.capacity
        for index in range(capacity):
            fake.push(index)
        evicted = fake.push(capacity)
        assert evicted == 0
        assert fake.size == capacity
        assert fake.snapshot_items() == list(range(1, capacity + 1))

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T17:55:29Z
# LAST_CHANGED: 2026-11-14T17:55:29Z
# CHANGE: Implement RingBuffer interface state machine: RingBufferState model, 1:1 transitions for capacity/size/is_empty/is_full/push/pop/clear/snapshot_items with FIFO eviction invariants and empty-pop precondition, synthesized FakeRingBuffer with factory, 100% covered Fixed fake test, and FakeRingBufferFuzzTest property fuzzing.
# --- END AUTOFAB METADATA ---
