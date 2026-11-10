# === File: ring_buffer_impl_pretense.py ===
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
from benchmark_3.parts.ring_buffer.lib.ring_buffer import BufferEmptyError
from benchmark_3.parts.ring_buffer.pretense.ring_buffer_pretense import (
    FakeRingBuffer,
    RingBufferState,
    RingBufferStateMachine,
    make_ring_buffer_fake,
)
from benchmark_3.parts.ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine for RingBuffer."""

    @transition(RingBuffer.push)
    def push(self, item: Any) -> Optional[Any]:
        require(self.state.capacity >= 1)
        target: RingBuffer = sut(RingBuffer)
        was_full = len(self.state.items) >= self.state.capacity
        expected_evicted = self.state.items[0] if was_full else None
        ret = call_target(target.push(item))
        assert ret == expected_evicted
        if was_full:
            assert ret is not None
        else:
            assert ret is None
        return ret

    @transition(RingBuffer.pop)
    def pop(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        if not self.state.items:
            with raises(BufferEmptyError):
                call_target(target.pop())
            raise BufferEmptyError
        expected = self.state.items[0]
        ret = call_target(target.pop())
        assert ret == expected
        return ret

    @transition(RingBuffer.clear)
    def clear(self) -> None:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.clear())
        assert ret is None
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(self) -> List[Any]:
        target: RingBuffer = sut(RingBuffer)
        snapshot = list(self.state.items)
        ret = call_target(target.snapshot_items())
        assert ret == snapshot
        assert len(ret) == len(snapshot)
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        expected = self.state.capacity
        ret = call_target(target.capacity)
        assert ret == expected
        assert ret >= 1
        return ret

    @transition(name="size")
    def size(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        expected = len(self.state.items)
        ret = call_target(target.size)
        assert ret == expected
        assert 0 <= ret <= self.state.capacity
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        target: RingBuffer = sut(RingBuffer)
        expected = len(self.state.items) == 0
        ret = call_target(target.is_empty)
        assert ret == expected
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        target: RingBuffer = sut(RingBuffer)
        expected = len(self.state.items) >= self.state.capacity
        ret = call_target(target.is_full)
        assert ret == expected
        return ret


proto = RingBufferImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestRingBufferImplReal(unittest.TestCase):
    """Verifies that concrete library implementation satisfies contracts."""

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

    def test_push_and_pop(self) -> None:
        assert self.checked.is_empty
        assert not self.checked.is_full
        assert self.checked.size == 0
        assert self.checked.capacity == 10

        assert self.checked.push("a") is None
        assert self.checked.push("b") is None
        assert self.checked.size == 2
        assert self.checked.snapshot_items() == ["a", "b"]

        assert self.checked.pop() == "a"
        assert self.checked.size == 1

        self.checked.clear()
        assert self.checked.is_empty

    def test_eviction(self) -> None:
        for i in range(10):
            self.checked.push(i)
        assert self.checked.is_full
        evicted = self.checked.push(10)
        assert evicted == 0
        assert self.checked.snapshot_items() == list(range(1, 11))

    def test_pop_empty(self) -> None:
        assert self.checked.is_empty
        with self.assertRaises(BufferEmptyError):
            self.checked.pop()



# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real Implementation
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
# LAST_CLEANED: 2026-11-08T23:25:05Z
# LAST_CHANGED: 2026-11-08T23:24:38Z
# CHANGE: Added test_pop_empty to exercise pop on an empty ring buffer and cover line 56.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T23:25:05Z
# PRETENSE_QA_AUDIT: 2026-11-08T23:24:54Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    call_target,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_3.parts.ring_buffer.lib.ring_buffer import RingBuffer, BufferEmptyError

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

DEFAULT_CAPACITY = 10

@dataclass
class RingBufferState:
    """Canonical model state tracking abstract collections and values."""
    initialized: bool = True
    capacity: int = DEFAULT_CAPACITY
    items: list[Any] = field(default_factory=list)


class RingBufferStateMachine(StateMachine[RingBufferState]):
    """Unified Pretense State Machine for RingBuffer."""

    def __init__(
        self,
        state: Optional[RingBufferState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or RingBufferState(), singletons=singletons)

    @transition(RingBuffer.push)
    def push(self, item: Any) -> Optional[Any]:
        require(self.state.initialized)
        require_arg(item, Domain.any())
        was_full = len(self.state.items) >= self.state.capacity
        oldest = self.state.items[0] if self.state.items else None
        evicted = oldest if was_full else None
        ret = self.inner_push(item)
        if was_full:
            self.state.items.pop(0)
        self.state.items.append(item)
        assert len(self.state.items) <= self.state.capacity
        if was_full:
            assert ret == oldest
        else:
            assert ret is None
        return ret

    @transition(RingBuffer.pop)
    def pop(self) -> Any:
        require(self.state.initialized)
        if not self.state.items:
            with raises(BufferEmptyError):
                self.inner_pop()
            raise BufferEmptyError
        oldest = self.state.items[0]
        ret = self.inner_pop()
        self.state.items.pop(0)
        assert ret == oldest
        return ret

    @transition(RingBuffer.clear)
    def clear(self) -> None:
        require(self.state.initialized)
        ret = self.inner_clear()
        self.state.items.clear()
        assert ret is None
        assert len(self.state.items) == 0
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(self) -> List[Any]:
        require(self.state.initialized)
        snapshot = list(self.state.items)
        ret = self.inner_snapshot_items()
        assert ret == snapshot
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        require(self.state.initialized)
        ret = self.inner_capacity()
        assert ret == self.state.capacity
        return ret

    @transition(name="size")
    def size(self) -> int:
        require(self.state.initialized)
        ret = self.inner_size()
        assert ret == len(self.state.items)
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        require(self.state.initialized)
        expected = len(self.state.items) == 0
        ret = self.inner_is_empty()
        assert ret == expected
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        require(self.state.initialized)
        expected = len(self.state.items) >= self.state.capacity
        ret = self.inner_is_full()
        assert ret == expected
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.initialized = True


proto = RingBufferStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeRingBuffer = synthesize_fake(RingBufferStateMachine)

def make_ring_buffer_fake(state: Optional[RingBufferState] = None) -> RingBuffer:
    """Synthesizes fake instance for RingBuffer."""
    return FakeRingBuffer(state=state or RingBufferState())

FakeRingBufferFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=RingBufferState,
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
        assert self.fake.capacity == 10
        assert self.fake.size == 0
        assert self.fake.is_empty
        assert not self.fake.is_full
        assert self.fake.snapshot_items() == []
        self.fake.push("a")
        self.fake.push("b")
        assert self.fake.pop() == "a"
        self.fake.clear()
        with self.assertRaises(BufferEmptyError):
            self.fake.pop()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T23:17:52Z
# LAST_CHANGED: 2026-11-08T23:17:52Z
# CHANGE: Implement ring_buffer_pretense state machine, fake synthesis, and test suite
# --- END AUTOFAB METADATA ---
