# === File: ring_buffer_impl_pretense.py ===
from __future__ import annotations

from typing import Any, List, Optional

import unittest

from hypothesis import given, settings, strategies as st

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from ring_buffer_qwen_moe_1.parts.ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__
from ring_buffer_qwen_moe_1.parts.ring_buffer.lib.ring_buffer import BufferEmptyError
from ring_buffer_qwen_moe_1.parts.ring_buffer.pretense.ring_buffer_pretense import (
    RingBufferStateMachine,
)


# ==============================================================================
# 4. Implementation Pseudo State Machine
# ==============================================================================

class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine for RingBuffer measuring differentials and SUT state.

    Inherits all transitions from RingBufferStateMachine; overrides inner transitions
    to drive the concrete SUT. Zero state dataclasses, zero require_arg.
    """

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


proto_impl = RingBufferImplPseudoStateMachine()


# ==============================================================================
# 5. Real Implementation Tests
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

    def test_operations(self) -> None:
        """Exercises basic operations: push, pop, clear, snapshot, properties."""
        self.checked.seed_initial()
        _ = self.checked.capacity
        _ = self.checked.size
        assert self.checked.is_empty
        assert not self.checked.is_full
        self.checked.push("item1")
        self.checked.push("item2")
        assert self.checked.size == 2
        _ = self.checked.pop()
        assert self.checked.size == 1
        snap = self.checked.snapshot_items()
        assert len(snap) == 1
        self.checked.clear()
        assert self.checked.is_empty

    def test_push_eviction(self) -> None:
        """Verifies overflow eviction when buffer reaches capacity."""
        self.checked.seed_initial()
        for i in range(10):
            self.checked.push(f"item_{i}")
        assert self.checked.is_full
        evicted = self.checked.push("overflow")
        assert evicted is not None

    def test_pop_empty_violation(self) -> None:
        """Verifies BufferEmptyError when popping from empty buffer."""
        self.checked.violating(BufferEmptyError).pop()


# ==============================================================================
# 6. Hypothesis Stateful Fuzzing on Real Implementation
# ==============================================================================

def make_sut() -> RingBuffer:
    registry = LifecycleRegistry()
    __initialize__(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(RingBuffer)


RingBufferImplFuzzTest = compile_hypothesis_test_case(
    proto=proto_impl,
    sut_factory=make_sut,
    initial_state_factory=proto_impl.make_initial_state,
    name="RingBufferImplFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T09:10:29Z
# LAST_CHANGED: 2026-11-11T09:09:40Z
# CHANGE: Implemented RingBufferImplPseudoStateMachine inheriting from RingBufferStateMachine with inner_<method> overrides routing to concrete RingBuffer SUT via sut(). Defined TestRingBufferImplReal exercising push/pop/clear/snapshot/properties, eviction, and BufferEmptyError violation (terminal violating call). Compiled RingBufferImplFuzzTest Hypothesis stateful fuzz suite.
# PRETENSE_COVERAGE_AUDIT: 2026-11-11T09:10:29Z
# PRETENSE_QA_AUDIT: 2026-11-11T09:10:07Z
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
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions -- Interface Components)
# ==============================================================================

@dataclass
class RingBufferState:
    """Canonical model state for a bounded circular ring buffer."""
    items: list[Any] = field(default_factory=list)
    capacity: int = 10


class RingBufferStateMachine(StateMachine[RingBufferState]):
    """Unified Pretense State Machine for RingBuffer."""

    def __init__(
        self,
        state: Optional[RingBufferState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> RingBufferState:
        """Constructs initial model state with zero items."""
        return RingBufferState()

    # --- Property transitions ---

    @transition(name="capacity")
    def capacity(self) -> int:
        """Returns the buffer capacity."""
        ret = self.inner_capacity()
        return ret

    @transition(name="size")
    def size(self) -> int:
        """Returns the current number of items."""
        ret = self.inner_size()
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        """Returns whether the buffer is empty."""
        ret = self.inner_is_empty()
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        """Returns whether the buffer is full."""
        ret = self.inner_is_full()
        return ret

    # --- push transition ---

    @transition(name="push")
    def push(self, item: Any) -> Optional[Any]:
        """Appends an item with overwrite eviction on saturation."""
        require_arg(item, Domain.any())
        ret = self.inner_push(item)
        if len(self.state.items) < self.state.capacity:
            self.state.items.append(item)
        else:
            del self.state.items[0]
            self.state.items.append(item)
        assert len(self.state.items) <= self.state.capacity
        return ret

    # --- pop transition ---

    @transition(name="pop")
    def pop(self) -> Any:
        """Removes and returns the oldest item."""
        require(bool(self.state.items))
        ret = self.inner_pop()
        del self.state.items[0]
        assert len(self.state.items) >= 0
        return ret

    # --- clear transition ---

    @transition(name="clear")
    def clear(self) -> None:
        """Removes all items, resetting size to zero."""
        self.inner_clear()
        self.state.items = []

    # --- snapshot_items transition ---

    @transition(name="snapshot_items")
    def snapshot_items(self) -> List[Any]:
        """Returns non-destructive snapshot in FIFO order."""
        ret = self.inner_snapshot_items()
        assert ret == list(self.state.items)
        return ret

    # --- Inner transitions (fake return value computation) ---

    def inner_capacity(self) -> int:
        """Computes fake return value for capacity."""
        return self.state.capacity

    def inner_size(self) -> int:
        """Computes fake return value for size."""
        return len(self.state.items)

    def inner_is_empty(self) -> bool:
        """Computes fake return value for is_empty."""
        return len(self.state.items) == 0

    def inner_is_full(self) -> bool:
        """Computes fake return value for is_full."""
        return len(self.state.items) == self.state.capacity

    def inner_push(self, item: Any) -> Optional[Any]:
        """Computes fake return value for push."""
        if len(self.state.items) == self.state.capacity:
            return self.state.items[0]
        return None

    def inner_pop(self) -> Any:
        """Computes fake return value for pop."""
        return self.state.items[0]

    def inner_clear(self) -> None:
        """Computes fake return value for clear."""
        pass

    def inner_snapshot_items(self) -> List[Any]:
        """Computes fake return value for snapshot_items."""
        return list(self.state.items)

    # --- Seeding transitions ---

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state."""
        pass


proto = RingBufferStateMachine()


# ==============================================================================
# 2. Fakes and Fuzzing (Interface Components)
# ==============================================================================

FakeRingBuffer = synthesize_fake(RingBufferStateMachine)


def make_ring_buffer_fake(state: Optional[RingBufferState] = None) -> Any:
    """Synthesizes a RingBuffer fake instance."""
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

    def test_transitions(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        self.sm.seed_initial()

        # Property transitions via the synthesized fake (protocol-typed)
        _ = self.fake.capacity
        _ = self.fake.size
        _ = self.fake.is_empty
        _ = self.fake.is_full

        # Push items (not full)
        self.fake.push("item1")
        self.fake.push("item2")
        self.fake.push("item3")
        assert self.fake.size == 3

        # Pop item
        _ = self.fake.pop()
        assert self.fake.size == 2

        # Snapshot
        snap = self.fake.snapshot_items()
        assert len(snap) == 2

        # Clear
        self.fake.clear()
        assert self.fake.is_empty

        # Fill buffer to capacity (10 default items)
        for i in range(10):
            self.fake.push(f"filled_{i}")
        assert self.fake.is_full

        # Push on full (eviction)
        evicted = self.fake.push("overflow")
        assert evicted is not None

        # Verify eviction via snapshot
        snap = self.fake.snapshot_items()
        assert "filled_0" not in snap

        # Pop remaining items (capacity of 10)
        for _ in range(10):
            self.fake.pop()
        assert self.fake.is_empty

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T09:06:39Z
# LAST_CHANGED: 2026-11-11T09:06:39Z
# CHANGE: Implemented RingBufferState, RingBufferStateMachine with all property/method transitions and inner_<method> stubs, synthesized FakeRingBuffer via synthesize_fake, compiled hypothesis fuzz test, and wrote TestRingBufferFake exercising all transitions against the synthesized fake. Fixed Pyright type inference on property transitions by routing all operations and assertions through self.fake (protocol-typed) instead of self.sm.
# --- END AUTOFAB METADATA ---
