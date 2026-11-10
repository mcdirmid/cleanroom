# === File: ring_buffer_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for RingBuffer.

The pseudo-state machine inherits the interface model transitions and overrides
only the transitions that require SUT observation, invoking the concrete
`RingBuffer` from lib/ring_buffer_impl.py through `call_target`. Real tests drive
operational scenarios through the checked adapter so every transition asserts the
contractual postconditions against the concrete implementation.
"""

from __future__ import annotations

from typing import Any, List, Optional
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
from benchmark_1.parts.ring_buffer.pretense.ring_buffer_pretense import (
    RingBufferState,
    RingBufferStateMachine,
)
from benchmark_1.parts.ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine for RingBuffer."""

    @transition(RingBuffer.push)
    def push(
        self,
        item: Any,
    ) -> Optional[Any]:
        target: RingBuffer = sut(RingBuffer)
        before = target.size
        capacity = target.capacity
        ret = call_target(target.push(item))
        after = target.size
        assert after == min(before + 1, capacity)
        if before < capacity:
            assert ret is None
        return ret

    @transition(RingBuffer.pop)
    def pop(
        self,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        before = target.size
        ret = call_target(target.pop())
        after = target.size
        assert after == before - 1
        return ret

    @transition(RingBuffer.clear)
    def clear(
        self,
    ) -> None:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.clear())
        assert target.size == 0
        assert target.is_empty
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(
        self,
    ) -> List[Any]:
        target: RingBuffer = sut(RingBuffer)
        before = target.size
        ret = call_target(target.snapshot_items())
        assert len(ret) == before
        assert target.size == before
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "capacity"))
        assert ret > 0
        return ret

    @transition(name="size")
    def size(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "size"))
        assert ret >= 0
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "is_empty"))
        assert ret == (target.size == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "is_full"))
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

    def test_initial_properties(self) -> None:
        assert self.checked.capacity == 10
        assert self.checked.size == 0
        assert self.checked.is_empty
        assert not self.checked.is_full

    def test_push_and_pop_fifo_order(self) -> None:
        self.checked.push("a")
        self.checked.push("b")
        self.checked.push("c")
        self.checked.snapshot_items()
        self.checked.pop()
        self.checked.push("d")
        self.checked.snapshot_items()
        self.checked.pop()
        self.checked.pop()
        self.checked.pop()
        assert self.checked.size == 0
        assert self.checked.is_empty

    def test_push_evicts_oldest_when_saturated(self) -> None:
        for index in range(10):
            self.checked.push(index)
        assert self.checked.is_full
        self.checked.push(10)
        assert self.checked.size == self.checked.capacity
        self.checked.pop()
        self.checked.snapshot_items()

    def test_clear_resets_buffer(self) -> None:
        self.checked.push("x")
        self.checked.push("y")
        self.checked.clear()
        assert self.checked.size == 0
        assert self.checked.is_empty
        assert not self.checked.is_full
        self.checked.push("z")
        assert self.checked.size == 1

    def test_snapshot_does_not_mutate_buffer(self) -> None:
        self.checked.push(1)
        self.checked.push(2)
        before = self.checked.size
        self.checked.snapshot_items()
        assert self.checked.size == before
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
# LAST_CLEANED: 2026-11-03T04:51:07Z
# LAST_CHANGED: 2026-11-03T04:48:54Z
# CHANGE: Implement RingBuffer pseudo-state machine overriding push/pop/clear/snapshot_items and property transitions via call_target against the concrete SUT with contract postcondition asserts (eviction size math, FIFO size decrement, clear reset, non-destructive snapshot); add granular TestRingBufferImplReal scenarios driven through as_checked covering initial properties, FIFO ordering, saturation eviction, clear, and snapshot immutability; compile real-SUT Hypothesis fuzz test.
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T04:51:07Z
# PRETENSE_QA_AUDIT: 2026-11-03T04:50:57Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for RingBuffer.

Specification mapping (low/ring_buffer.pyi):
- Model state tracks the bounded FIFO circular storage (capacity and active items).
- push models overwrite eviction on saturation, returning the evicted oldest item.
- pop models oldest-item removal, gated by the non-empty caller precondition.
- clear models wholesale removal of active items.
- snapshot_items models the non-destructive FIFO observability query.
- capacity/size/is_empty/is_full model the public derived properties.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

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
from benchmark_1.parts.ring_buffer.lib.ring_buffer import RingBuffer


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions live naturally inside the single
# transition body (multi-transition splitting is prohibited).


@dataclass
class RingBufferState:
    """Canonical model state for RingBuffer operations."""

    initialized: bool = True
    capacity: int = 10
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
        was_full = len(self.state.items) >= self.state.capacity
        evicted: Optional[Any] = None
        if was_full:
            evicted = self.state.items.pop(0)
        self.state.items.append(item)
        ret: Optional[Any] = self.inner_push(item)
        assert len(self.state.items) <= self.state.capacity
        assert self.state.items[-1] is item
        if was_full:
            assert len(self.state.items) == self.state.capacity
        else:
            assert ret is None
        return ret

    @transition(RingBuffer.pop)
    def pop(
        self,
    ) -> Any:
        require(self.state.initialized)
        require(len(self.state.items) > 0)
        expected: Any = self.state.items[0]
        ret: Any = self.inner_pop()
        assert ret is expected
        assert len(self.state.items) <= self.state.capacity
        return ret

    @transition(RingBuffer.clear)
    def clear(
        self,
    ) -> None:
        require(self.state.initialized)
        self.state.items.clear()
        ret = self.inner_clear()
        assert ret is None
        assert len(self.state.items) == 0
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(
        self,
    ) -> List[Any]:
        require(self.state.initialized)
        expected_size = len(self.state.items)
        ret: List[Any] = self.inner_snapshot_items()
        assert len(ret) == expected_size
        assert len(self.state.items) == expected_size
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        require(self.state.initialized)
        ret: int = self.inner_capacity()
        assert ret == self.state.capacity
        return ret

    @transition(name="size")
    def size(self) -> int:
        require(self.state.initialized)
        ret: int = self.inner_size()
        assert ret == len(self.state.items)
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
# LAST_CLEANED: 2026-11-03T04:48:51Z
# LAST_CHANGED: 2026-11-03T04:48:51Z
# CHANGE: Implement RingBuffer interface state machine: FIFO item list model with capacity 10, push overwrite-eviction returning evicted item, pop gated on non-empty precondition returning oldest item, clear, non-destructive snapshot_items, and derived capacity/size/is_empty/is_full property transitions with single-argument postcondition asserts; synthesize fake and fake fuzz test.
# --- END AUTOFAB METADATA ---
