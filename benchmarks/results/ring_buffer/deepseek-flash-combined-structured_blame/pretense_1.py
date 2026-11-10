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
from benchmark_1.parts.ring_buffer.pretense.ring_buffer_pretense import (RingBufferStateMachine, RingBufferState, FakeRingBuffer, make_ring_buffer_fake)
from benchmark_1.parts.ring_buffer.lib.ring_buffer import BufferEmptyError
from benchmark_1.parts.ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# REFERENCE PATTERNS:
#   # Implementation pseudo-state machine transition override with call_target:
#   @transition(TargetClass.method)
#   def method(self, *args) -> Any:
#       target: TargetClass = sut(TargetClass)
#       old_val = target.property
#       ret = call_target(target.method(*args))
#       assert target.property == old_val
#       return ret
#
#   # Real implementation scenario test driving self.checked (100% statement coverage):
#   class TestTargetImplReal(unittest.TestCase):
#       def setUp(self) -> None:
#           self.registry = LifecycleRegistry()
#           __initialize__(self.registry)
#           self.phase_scope = enter_phase(system, registry=self.registry)
#           self.phase_scope.__enter__()
#           self.real = get_singleton(TargetClass)
#           self.sm = TargetImplPseudoStateMachine(singletons={TargetClass: self.real})
#           self.checked = self.sm.as_checked(TargetClass, self.real)
#       def tearDown(self) -> None:
#           self.phase_scope.__exit__(None, None, None)
#       def test_real_conformance(self) -> None:
#           self.checked.method(*args)

class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine for RingBuffer."""

    @transition(RingBuffer.push)
    def push(
        self,
        item: Any,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.push(item))
        return ret

    @transition(RingBuffer.pop)
    def pop(
        self,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.pop())
        return ret

    @transition(RingBuffer.clear)
    def clear(
        self,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.clear())
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(
        self,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.snapshot_items())
        return ret

    @transition(name="capacity")
    def capacity(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.capacity)
        return ret

    @transition(name="size")
    def size(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.size)
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.is_empty)
        return ret

    @transition(name="is_full")
    def is_full(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.is_full)
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
        """Drives operational scenarios through the checked wrapper."""
        self.checked.clear()
        assert self.checked.capacity == 10
        assert self.checked.size == 0
        assert self.checked.is_empty
        assert not self.checked.is_full
        for index in range(10):
            assert self.checked.push(index) is None
        assert self.checked.is_full
        assert self.checked.size == 10
        assert self.checked.push(10) == 0
        assert self.checked.size == 10
        assert self.checked.snapshot_items() == list(range(1, 11))
        assert self.checked.pop() == 1
        assert self.checked.size == 9
        assert not self.checked.is_full
        self.checked.clear()
        assert self.checked.is_empty
        assert self.checked.size == 0

    def test_pop_empty_buffer_error(self) -> None:
        """Exercises the contracted error observed when popping a drained buffer."""
        self.checked.clear()
        assert self.checked.is_empty
        with self.assertRaises(BufferEmptyError):
            self.checked.pop()


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
# LAST_CLEANED: 2026-11-08T17:43:55Z
# LAST_CHANGED: 2026-11-08T17:38:57Z
# CHANGE: Resolved unreached contracted error scenario for empty-buffer pop: TestRingBufferImplReal gains test_pop_empty_buffer_error, which drains the buffer through the checked wrapper and asserts the declared BufferEmptyError via self.assertRaises, so the real SUT's contracted precondition error path is now empirically exercised; the declared error class is imported from the interface spec. Existing conformance and fuzz suites unchanged.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:43:55Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:43:33Z
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
from benchmark_1.parts.ring_buffer.lib.ring_buffer import BufferEmptyError, RingBuffer


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions (with raises(ExpectedException): make_return_value())
# live naturally inside the single transition body (multi-transition splitting is prohibited).
# require_arg defines the caller precondition contract (checked at runtime on real calls).
# Use Domain.type(T) or open domain; use preferred=[...] to cluster/bias fuzz inputs without restricting the contract.
#
# REFERENCE PATTERNS:
#   # 1:1 Transition Pattern with Domain strategies and make_return_value pivot:
#   @transition(TargetClass.method)
#   def method(self, arg1: str, count: int) -> ReturnType:
#       require(self.state.initialized)
#       require_arg(arg1, Domain.type(str), preferred=["sample"])
#       require_arg(count, Domain.range(1, 100), preferred=[10])
#       fake_ret = ReturnType(...)  # or None / value
#       ret = make_return_value(fake_ret)
#       self.state.items.append(ret)
#       assert ret == fake_ret
#       return ret
#
#   # Seeding Transition (sets up state dynamically outside default __init__):
#   @transition.seeding
#   def seed_initial(self) -> None:
#       self.state.initialized = True
#
#   # Single service fake factory:
#   FakeTarget = synthesize_fake(TargetStateMachine)
#   def make_target_fake(state: Optional[TargetState] = None) -> TargetClass:
#       return FakeTarget(state=state or TargetState())
#
#   # Fixed fake test suite covering 100% of transitions and seeding transitions:
#   class TestTargetFake(unittest.TestCase):
#       def setUp(self) -> None:
#           self.fake = make_target_fake()
#           self.sm = TargetStateMachine()
#       def test_transitions_coverage(self) -> None:
#           self.sm.seed_initial()
#           self.fake.method("sample", 10)


@dataclass
class RingBufferState:
    """Canonical model state for a bounded circular ring buffer.

    The active contents are tracked in FIFO arrival order (oldest first), while
    ``capacity`` mirrors the implementation's default bounded capacity of 10.
    """

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
        require_arg(item, Domain.any(), preferred=["alpha", "beta", 0, 1])
        was_full = len(self.state.items) >= self.state.capacity
        evicted: Optional[Any] = self.state.items[0] if was_full else None
        ret = make_return_value(evicted)
        if was_full:
            self.state.items.pop(0)
        self.state.items.append(item)
        assert ret == evicted
        return ret

    @transition(RingBuffer.pop)
    def pop(
        self,
    ) -> Any:
        require(self.state.initialized)
        if len(self.state.items) == 0:
            with raises(BufferEmptyError):
                make_return_value()
            return None
        oldest = self.state.items[0]
        ret = make_return_value(oldest)
        self.state.items.pop(0)
        assert ret == oldest
        return ret

    @transition(RingBuffer.clear)
    def clear(
        self,
    ) -> None:
        require(self.state.initialized)
        ret = make_return_value()
        self.state.items.clear()
        assert ret is None
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(
        self,
    ) -> List[Any]:
        require(self.state.initialized)
        expected = list(self.state.items)
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        require(self.state.initialized)
        expected = self.state.capacity
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(name="size")
    def size(self) -> int:
        require(self.state.initialized)
        expected = len(self.state.items)
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        require(self.state.initialized)
        expected = len(self.state.items) == 0
        ret = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        require(self.state.initialized)
        expected = len(self.state.items) >= self.state.capacity
        ret = make_return_value(expected)
        assert ret == expected
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
        for index in range(10):
            assert self.fake.push(index) is None
        assert self.fake.is_full
        assert self.fake.size == 10
        assert self.fake.push(10) == 0
        assert self.fake.size == 10
        assert self.fake.snapshot_items() == list(range(1, 11))
        assert self.fake.pop() == 1
        assert self.fake.size == 9
        assert not self.fake.is_full
        self.fake.clear()
        assert self.fake.is_empty
        assert self.fake.size == 0
        with self.assertRaises(BufferEmptyError):
            self.fake.pop()


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeRingBufferFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=RingBufferState,
    name="FakeRingBufferFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:42:39Z
# LAST_CHANGED: 2026-11-08T17:42:39Z
# CHANGE: Modeled both contracted branches of pop directly in the single transition body instead of gating the empty case out with a non-empty require: size zero now executes with raises(BufferEmptyError) around the return pivot and performs no model mutation, while size greater than zero still removes and returns the oldest item and decrements the modeled item list. The fixed fake suite now also observes the declared BufferEmptyError on a drained buffer via self.assertRaises; push eviction/available-capacity branching and all other transitions audited unchanged.
# --- END AUTOFAB METADATA ---
