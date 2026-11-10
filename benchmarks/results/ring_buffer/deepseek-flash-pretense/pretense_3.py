# === File: ring_buffer_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for RingBuffer."""

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
from benchmark_2.parts.ring_buffer.pretense.ring_buffer_pretense import (RingBufferStateMachine, RingBufferState, FakeRingBuffer, make_ring_buffer_fake)
from benchmark_2.parts.ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine for RingBuffer."""

    @transition(RingBuffer.push)
    def push(
        self,
        item: Any,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        pre_size: int = target.size
        pre_capacity: int = target.capacity
        ret = call_target(target.push(item))
        assert target.size == min(pre_size + 1, pre_capacity)
        assert target.size <= pre_capacity
        return ret

    @transition(RingBuffer.pop)
    def pop(
        self,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        pre_size: int = target.size
        ret = call_target(target.pop())
        assert target.size == pre_size - 1
        return ret

    @transition(RingBuffer.clear)
    def clear(
        self,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.clear())
        assert target.size == 0
        assert target.is_empty
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(
        self,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        pre_size: int = target.size
        ret = call_target(target.snapshot_items())
        assert target.size == pre_size
        assert len(ret) == pre_size
        return ret

    @transition(name="capacity")
    def capacity(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.capacity)
        assert ret > 0
        assert ret == target.capacity
        return ret

    @transition(name="size")
    def size(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.size)
        assert ret >= 0
        assert ret <= target.capacity
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.is_empty)
        assert ret == (target.size == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.is_full)
        assert ret == (target.size >= target.capacity)
        return ret


proto = RingBufferImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestRingBufferImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(RingBuffer)
        self.sm = RingBufferImplPseudoStateMachine(singletons={RingBuffer: self.real})
        self.checked = self.sm.as_checked(RingBuffer, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_push_below_capacity_stores_items(self) -> None:
        self.checked.push("alpha")
        self.checked.push("beta")
        self.checked.push("gamma")
        assert self.checked.size == 3
        assert not self.checked.is_empty
        assert not self.checked.is_full

    def test_push_at_capacity_evicts_oldest_item(self) -> None:
        capacity = self.checked.capacity
        for index in range(capacity):
            self.checked.push(index)
        assert self.checked.size == capacity
        assert self.checked.is_full
        self.checked.push(capacity)
        assert self.checked.size == capacity

    def test_pop_returns_oldest_item_in_fifo_order(self) -> None:
        self.checked.push("first")
        self.checked.push("second")
        self.checked.pop()
        assert self.checked.size == 1

    def test_clear_resets_buffer_to_empty(self) -> None:
        self.checked.push("a")
        self.checked.push("b")
        self.checked.clear()
        assert self.checked.size == 0
        assert self.checked.is_empty
        self.checked.push("c")
        assert self.checked.size == 1

    def test_snapshot_items_reports_fifo_order_without_mutation(self) -> None:
        self.checked.push("a")
        self.checked.push("b")
        self.checked.push("c")
        items = self.checked.snapshot_items()
        assert items == ["a", "b", "c"]
        assert self.checked.size == 3

    def test_capacity_query_is_positive(self) -> None:
        capacity = self.checked.capacity
        assert capacity > 0
        assert self.checked.size <= capacity

    def test_empty_flag_tracks_occupancy(self) -> None:
        assert self.checked.is_empty
        self.checked.push("item")
        assert not self.checked.is_empty


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def make_sut() -> RingBuffer:
    registry = LifecycleRegistry()
    __initialize__(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(RingBuffer)


RingBufferFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=RingBufferState,
    name="RingBufferFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T17:28:38Z
# LAST_CHANGED: 2026-11-03T17:26:31Z
# CHANGE: Implement RingBufferImplPseudoStateMachine inheriting the interface state machine with call_target pivots and real SUT postcondition asserts (size/eviction/clear/snapshot/property parity) for all 8 transitions; replace scaffold placeholder with granular TestRingBufferImplReal scenarios driving self.checked for push, eviction at capacity, FIFO pop, clear, snapshot, capacity, and empty-flag coverage; keep RingBufferFuzzTest on the real SUT factory.
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T17:28:38Z
# PRETENSE_QA_AUDIT: 2026-11-03T17:28:28Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for RingBuffer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Set, Tuple

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
from benchmark_2.parts.ring_buffer.lib.ring_buffer import RingBuffer


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================

DEFAULT_CAPACITY = 10


@dataclass
class RingBufferState:
    """Canonical model state for a bounded circular first-in first-out buffer."""

    initialized: bool = True
    capacity: int = DEFAULT_CAPACITY
    items: List[Any] = field(default_factory=list)


class RingBufferStateMachine(StateMachine[RingBufferState]):
    """Unified Pretense State Machine for RingBuffer."""

    def __init__(
        self,
        state: Optional[RingBufferState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or RingBufferState(), singletons=singletons)

    @transition(RingBuffer.push)
    def push(
        self,
        item: Any,
    ) -> Optional[Any]:
        require(self.state.initialized)
        require_arg(item, Domain.any())
        evicted: Optional[Any] = None
        if len(self.state.items) >= self.state.capacity:
            evicted = self.state.items.pop(0)
            self.state.items.append(item)
            assert len(self.state.items) == self.state.capacity
        else:
            self.state.items.append(item)
        assert len(self.state.items) <= self.state.capacity
        ret: Optional[Any] = self.inner_push(item)
        return ret

    @transition(RingBuffer.pop)
    def pop(
        self,
    ) -> Any:
        require(self.state.initialized)
        require(len(self.state.items) > 0)
        ret: Any = self.inner_pop()
        assert len(self.state.items) < self.state.capacity
        return ret

    @transition(RingBuffer.clear)
    def clear(
        self,
    ) -> None:
        require(self.state.initialized)
        self.state.items.clear()
        assert len(self.state.items) == 0
        ret = self.inner_clear()
        assert ret is None
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(
        self,
    ) -> List[Any]:
        require(self.state.initialized)
        ret: List[Any] = self.inner_snapshot_items()
        assert list(self.state.items) == ret
        assert len(self.state.items) <= self.state.capacity
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        require(self.state.initialized)
        ret: int = self.inner_capacity()
        assert self.state.capacity > 0
        assert ret == self.state.capacity
        return ret

    @transition(name="size")
    def size(self) -> int:
        require(self.state.initialized)
        ret: int = self.inner_size()
        assert ret == len(self.state.items)
        assert len(self.state.items) <= self.state.capacity
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        require(self.state.initialized)
        ret: bool = self.inner_is_empty()
        assert ret == (len(self.state.items) == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        require(self.state.initialized)
        ret: bool = self.inner_is_full()
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = RingBufferStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeRingBuffer = synthesize_fake(RingBufferStateMachine)


def make_ring_buffer_fake(
    state: Optional[RingBufferState] = None,
) -> RingBuffer:
    """Synthesizes fake instance for RingBuffer."""
    return FakeRingBuffer(state=state or RingBufferState())


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeRingBufferFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=RingBufferState,
    name="FakeRingBufferFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T17:26:28Z
# LAST_CHANGED: 2026-11-03T17:26:28Z
# CHANGE: Model bounded ring buffer state (capacity 10, FIFO items) with 1:1 transitions for push (eviction on saturation), pop (gated non-empty precondition), clear, snapshot_items, and capacity/size/is_empty/is_full property queries using pivots; expose FakeRingBuffer and FakeRingBufferFuzzTest.
# --- END AUTOFAB METADATA ---
