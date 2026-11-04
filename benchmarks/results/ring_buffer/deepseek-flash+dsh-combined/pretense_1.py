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
from benchmark_1.parts.ring_buffer.pretense.ring_buffer_pretense import (
    FakeRingBuffer,
    RingBufferState,
    RingBufferStateMachine,
    make_ring_buffer_fake,
)
from benchmark_1.parts.ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# NOTE: Overrides observe/assert postconditions against the real SUT and never
# mutate self.state; the inherited interface transitions supply model state
# mutations and precondition guards automatically.

class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine for RingBuffer."""

    @transition(RingBuffer.push)
    def push(
        self,
        item: Any,
    ) -> Optional[Any]:
        target: RingBuffer = sut(RingBuffer)
        before = target.snapshot_items()
        capacity = target.capacity
        ret = call_target(target.push(item))
        assert target.size == min(len(before) + 1, capacity)
        assert target.snapshot_items()[-1] is item
        if len(before) < capacity:
            assert ret is None
        else:
            assert ret is before[0]
        return ret

    @transition(RingBuffer.pop)
    def pop(
        self,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        before = target.snapshot_items()
        ret = call_target(target.pop())
        assert ret is before[0]
        assert target.size == len(before) - 1
        return ret

    @transition(RingBuffer.clear)
    def clear(
        self,
    ) -> None:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.clear())
        assert target.size == 0
        assert target.is_empty
        assert len(target.snapshot_items()) == 0
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(
        self,
    ) -> List[Any]:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.snapshot_items())
        assert target.size == len(ret)
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.capacity)
        assert ret == 10
        return ret

    @transition(name="size")
    def size(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.size)
        assert ret == len(target.snapshot_items())
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.is_empty)
        assert ret == (target.size == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
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

    def test_real_conformance(self) -> None:
        assert self.checked.capacity == 10
        assert self.checked.size == 0
        assert self.checked.is_empty
        assert not self.checked.is_full
        for index in range(10):
            assert self.checked.push(index) is None
        assert self.checked.size == 10
        assert self.checked.is_full
        assert not self.checked.is_empty
        assert self.checked.push(10) == 0
        assert self.checked.size == 10
        assert self.checked.snapshot_items() == list(range(1, 11))
        assert self.checked.pop() == 1
        assert self.checked.size == 9
        assert not self.checked.is_full
        self.checked.clear()
        assert self.checked.is_empty
        assert self.checked.size == 0
        assert self.checked.snapshot_items() == []


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
# LAST_CLEANED: 2026-11-04T19:52:27Z
# LAST_CHANGED: 2026-11-04T19:50:30Z
# CHANGE: Implemented RingBuffer implementation pseudo-state machine inheriting the interface state machine with call_target pivots and real-SUT postcondition assertions for push (eviction identity/size), pop, clear, snapshot_items, and capacity/size/is_empty/is_full properties; replaced the self.fail placeholder with a full real conformance scenario driving all transitions via self.checked, and retained real hypothesis fuzz compilation.
# PRETENSE_COVERAGE_AUDIT: 2026-11-04T19:52:27Z
# PRETENSE_QA_AUDIT: 2026-11-04T19:52:15Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for RingBuffer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

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
from benchmark_1.parts.ring_buffer.lib.ring_buffer import RingBuffer


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions (with raises(ExpectedException): make_return_value())
# live naturally inside the single transition body (multi-transition splitting is prohibited).
# require_arg defines the caller precondition contract (checked at runtime on real calls).
# Use Domain.any() for open parameters and require(...) to gate model-state preconditions.

@dataclass
class RingBufferState:
    """Canonical model state for RingBuffer operations."""

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
        require(self.state.capacity > 0)
        require_arg(item, Domain.any())
        previous_size = len(self.state.items)
        evicted: Optional[Any] = None
        if previous_size < self.state.capacity:
            self.state.items.append(item)
        else:
            evicted = self.state.items.pop(0)
            self.state.items.append(item)
        ret: Optional[Any] = make_return_value(evicted)
        assert len(self.state.items) == min(previous_size + 1, self.state.capacity)
        assert self.state.items[-1] is item
        return ret

    @transition(RingBuffer.pop)
    def pop(
        self,
    ) -> Any:
        require(len(self.state.items) > 0)
        previous_size = len(self.state.items)
        item = self.state.items.pop(0)
        ret: Any = make_return_value(item)
        assert len(self.state.items) == previous_size - 1
        return ret

    @transition(RingBuffer.clear)
    def clear(
        self,
    ) -> None:
        self.state.items.clear()
        ret = make_return_value(None)
        assert len(self.state.items) == 0
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(
        self,
    ) -> List[Any]:
        snapshot = list(self.state.items)
        ret: List[Any] = make_return_value(snapshot)
        assert len(self.state.items) == len(ret)
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        ret: int = make_return_value(self.state.capacity)
        assert ret > 0
        return ret

    @transition(name="size")
    def size(self) -> int:
        ret: int = make_return_value(len(self.state.items))
        assert ret >= 0
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        ret: bool = make_return_value(len(self.state.items) == 0)
        assert ret == (len(self.state.items) == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        ret: bool = make_return_value(len(self.state.items) >= self.state.capacity)
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Transitions a blank model state into the canonical initial ring buffer configuration."""
        self.state.capacity = 10
        self.state.items.clear()


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
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestRingBufferFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_ring_buffer_fake()
        self.sm = RingBufferStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        assert self.fake.capacity == 10
        assert self.fake.size == 0
        assert self.fake.is_empty
        assert not self.fake.is_full
        assert self.fake.push(1) is None
        assert self.fake.size == 1
        assert not self.fake.is_empty
        assert self.fake.snapshot_items() == [1]
        assert self.fake.pop() == 1
        assert self.fake.size == 0
        assert self.fake.is_empty
        self.fake.push(2)
        self.fake.clear()
        assert self.fake.snapshot_items() == []
        assert self.fake.is_empty


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeRingBufferFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=RingBufferState,
    name="FakeRingBufferFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T19:50:15Z
# LAST_CHANGED: 2026-11-04T19:50:15Z
# CHANGE: Implemented RingBuffer interface state machine: model state with capacity and FIFO items, 1:1 transitions for push (overwrite eviction), pop (empty precondition via require), clear, snapshot_items, and capacity/size/is_empty/is_full properties using make_return_value pivots; added meaningful seeding transition, fixed fake coverage test, and fake hypothesis fuzz compilation.
# --- END AUTOFAB METADATA ---
