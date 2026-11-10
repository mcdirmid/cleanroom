# === File: ring_buffer_impl_pretense.py ===
from __future__ import annotations

from typing import Any, List, Optional
import unittest

from hypothesis import given, settings, strategies as st

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from benchmark_3.parts.ring_buffer.lib.ring_buffer import (
    BufferEmptyError,
    BufferError,
    RingBuffer,
)
from benchmark_3.parts.ring_buffer.lib.ring_buffer_impl import (
    RingBuffer as RingBufferImpl,
    __initialize__,
)
from benchmark_3.parts.ring_buffer.pretense.ring_buffer_pretense import (
    RingBufferStateMachine,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine for RingBuffer measuring differentials and SUT state."""

    def inner_initial_capacity(self) -> int:
        """Specializes uncontracted open capacity parameter to concrete default of 10."""
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
        return target.push(item)

    def inner_pop(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        return target.pop()

    def inner_clear(self) -> None:
        target: RingBuffer = sut(RingBuffer)
        target.clear()

    def inner_snapshot_items(self) -> List[Any]:
        target: RingBuffer = sut(RingBuffer)
        return target.snapshot_items()


proto = RingBufferImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestRingBufferImplReal(unittest.TestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = self.phase_scope.get_singleton(RingBuffer)
        self.sm = RingBufferImplPseudoStateMachine(singletons={RingBuffer: self.real})
        self.checked: Any = self.sm.as_checked(RingBuffer, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_empty_state_and_pop_contract_error(self) -> None:
        """Verifies initial empty state and BufferEmptyError precondition violation."""
        _ = self.checked.capacity
        _ = self.checked.size
        _ = self.checked.is_empty
        _ = self.checked.is_full
        _ = self.checked.snapshot_items()
        self.checked.violating(BufferEmptyError).pop()

    def test_push_and_pop_operations(self) -> None:
        """Verifies normal FIFO storage, pop removal, and clear."""
        self.checked.push(10)
        self.checked.push(20)
        self.checked.push(30)
        _ = self.checked.size
        _ = self.checked.is_empty
        _ = self.checked.is_full
        _ = self.checked.snapshot_items()
        self.checked.pop()
        _ = self.checked.size
        _ = self.checked.snapshot_items()
        self.checked.clear()
        _ = self.checked.size
        _ = self.checked.is_empty
        _ = self.checked.snapshot_items()

    def test_full_capacity_and_overwrite_eviction(self) -> None:
        """Verifies saturation behavior and overwrite eviction when capacity is reached."""
        for i in range(10):
            self.checked.push(i)
        _ = self.checked.is_full
        _ = self.checked.size
        # Push 11th item: triggers overwrite eviction of oldest item (0)
        self.checked.push(100)
        _ = self.checked.is_full
        _ = self.checked.size
        _ = self.checked.snapshot_items()
        # Drain all remaining 10 items
        for _ in range(10):
            self.checked.pop()
        _ = self.checked.is_empty
        _ = self.checked.size


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================

def make_sut() -> RingBuffer:
    registry = LifecycleRegistry()
    __initialize__(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return scope.get_singleton(RingBuffer)


RingBufferFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="RingBufferFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T06:59:37Z
# LAST_CHANGED: 2026-11-10T06:53:17Z
# CHANGE: Initial implementation of RingBuffer implementation pretense module with inner transitions, real scenario tests, and fuzz testing
# PRETENSE_COVERAGE_AUDIT: 2026-11-10T06:59:37Z
# PRETENSE_QA_AUDIT: 2026-11-10T06:59:11Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional
import unittest

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
from benchmark_3.parts.ring_buffer.lib.ring_buffer import (
    BufferEmptyError,
    BufferError,
    RingBuffer,
)


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class RingBufferState:
    """Canonical model state tracking bounded circular ring buffer."""
    capacity: int = 5
    items: list[Any] = field(default_factory=list)
    initialized: bool = True


class RingBufferStateMachine(StateMachine[RingBufferState]):
    """Unified Pretense State Machine for RingBuffer."""

    def __init__(
        self,
        state: Optional[RingBufferState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    @property
    def initial_capacity(self) -> int:
        """Open parameter hook for default initial buffer capacity."""
        return self.inner_initial_capacity()

    def inner_initial_capacity(self) -> int:
        return 5

    def make_initial_state(self) -> RingBufferState:
        """Constructs initial model state. Open parameters may be specialized by pseudo-state machines."""
        return RingBufferState(capacity=self.initial_capacity)

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.initialized = True

    @transition(name="capacity")
    def capacity(self) -> int:
        ret = self.inner_capacity()
        assert ret == self.state.capacity
        return ret

    def inner_capacity(self) -> int:
        return self.state.capacity

    @transition(name="size")
    def size(self) -> int:
        ret = self.inner_size()
        assert ret == len(self.state.items)
        return ret

    def inner_size(self) -> int:
        return len(self.state.items)

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        ret = self.inner_is_empty()
        assert ret == (len(self.state.items) == 0)
        return ret

    def inner_is_empty(self) -> bool:
        return len(self.state.items) == 0

    @transition(name="is_full")
    def is_full(self) -> bool:
        ret = self.inner_is_full()
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret

    def inner_is_full(self) -> bool:
        return len(self.state.items) >= self.state.capacity

    @transition(RingBuffer.push)
    def push(self, item: Any) -> Optional[Any]:
        require_arg(item, Domain.any(), preferred=[1, 2, 3])
        expected_evicted = self.state.items[0] if len(self.state.items) >= self.state.capacity else None
        ret = self.inner_push(item)
        assert ret == expected_evicted
        if len(self.state.items) >= self.state.capacity:
            self.state.items.pop(0)
        self.state.items.append(item)
        return ret

    def inner_push(self, item: Any) -> Optional[Any]:
        return self.state.items[0] if len(self.state.items) >= self.state.capacity else None

    @transition(RingBuffer.pop)
    def pop(self) -> Any:
        require(len(self.state.items) > 0, error=BufferEmptyError)
        ret = self.inner_pop()
        expected = self.state.items.pop(0)
        assert ret == expected
        return ret

    def inner_pop(self) -> Any:
        if not self.state.items:
            raise BufferEmptyError("Cannot pop from empty buffer")
        return self.state.items[0]

    @transition(RingBuffer.clear)
    def clear(self) -> None:
        self.inner_clear()
        self.state.items.clear()
        assert len(self.state.items) == 0

    def inner_clear(self) -> None:
        pass

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(self) -> List[Any]:
        ret = self.inner_snapshot_items()
        assert ret == list(self.state.items)
        return ret

    def inner_snapshot_items(self) -> List[Any]:
        return list(self.state.items)


proto = RingBufferStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeRingBuffer = synthesize_fake(RingBufferStateMachine)


def make_ring_buffer_fake(state: Optional[RingBufferState] = None) -> RingBuffer:
    """Synthesizes fake instance for RingBuffer."""
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
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_ring_buffer_fake()
        self.sm = RingBufferStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        self.fake.push(10)
        self.fake.push(20)
        _ = self.fake.capacity
        _ = self.fake.size
        _ = self.fake.is_empty
        _ = self.fake.is_full
        _ = self.fake.snapshot_items()
        _ = self.fake.pop()
        self.fake.clear()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T06:58:14Z
# LAST_CHANGED: 2026-11-10T06:58:14Z
# CHANGE: Fix pop transition to delegate to inner_pop before popping model items, avoiding IndexError when buffer is empty during BufferEmptyError verification
# --- END AUTOFAB METADATA ---
