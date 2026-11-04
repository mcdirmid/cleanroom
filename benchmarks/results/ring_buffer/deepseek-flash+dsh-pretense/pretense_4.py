# === File: ring_buffer_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for RingBuffer.

The pseudo-state machine inherits ``RingBufferStateMachine`` and overrides the
transitions with ``call_target(...)`` invocations against the concrete
``RingBuffer`` singleton. ``TestRingBufferImplReal`` drives operational
scenarios through the checked adapter, and ``RingBufferFuzzTest`` fuzzes the
real SUT against the model.
"""

from __future__ import annotations

from typing import Any, List, Optional
import unittest

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
    RingBufferStateMachine,
    RingBufferState,
    FakeRingBuffer,
    make_ring_buffer_fake,
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
        ret = call_target(getattr(target, "capacity"))
        return ret

    @transition(name="size")
    def size(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "size"))
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "is_empty"))
        return ret

    @transition(name="is_full")
    def is_full(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "is_full"))
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

    def test_initial_state_is_empty(self) -> None:
        self.checked.clear()
        assert self.checked.capacity == 10
        assert self.checked.size == 0
        assert self.checked.is_empty is True
        assert self.checked.is_full is False
        assert self.checked.snapshot_items() == []

    def test_push_pop_preserves_fifo_order(self) -> None:
        self.checked.clear()
        assert self.checked.push("a") is None
        assert self.checked.push("b") is None
        assert self.checked.push("c") is None
        assert self.checked.size == 3
        assert self.checked.pop() == "a"
        assert self.checked.pop() == "b"
        assert self.checked.size == 1
        assert self.checked.snapshot_items() == ["c"]

    def test_push_evicts_oldest_when_full(self) -> None:
        self.checked.clear()
        for index in range(10):
            assert self.checked.push(index) is None
        assert self.checked.size == 10
        assert self.checked.is_full is True
        evicted = self.checked.push("newest")
        assert evicted == 0
        assert self.checked.size == 10
        assert self.checked.snapshot_items() == list(range(1, 10)) + ["newest"]

    def test_clear_removes_all_items(self) -> None:
        self.checked.clear()
        self.checked.push("a")
        self.checked.push("b")
        self.checked.clear()
        assert self.checked.size == 0
        assert self.checked.is_empty is True
        assert self.checked.is_full is False
        assert self.checked.snapshot_items() == []

    def test_snapshot_items_is_non_destructive(self) -> None:
        self.checked.clear()
        self.checked.push("x")
        self.checked.push("y")
        self.checked.push("z")
        first = self.checked.snapshot_items()
        second = self.checked.snapshot_items()
        assert first == ["x", "y", "z"]
        assert second == ["x", "y", "z"]
        assert self.checked.size == 3


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
# LAST_CLEANED: 2026-11-03T20:23:47Z
# LAST_CHANGED: 2026-11-03T20:21:55Z
# CHANGE: Implement RingBuffer impl pseudo-state machine (call_target push/pop/clear/snapshot_items and property accessors, no model state mutation) and TestRingBufferImplReal scenarios covering initial empty state, FIFO push/pop order, full-buffer eviction of the oldest item, clear reset, and non-destructive snapshot queries; compile RingBufferFuzzTest over the real SUT.
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T20:23:47Z
# PRETENSE_QA_AUDIT: 2026-11-03T20:23:34Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for RingBuffer.

Specification mapping (``low/ring_buffer.pyi``):

- ``RingBufferState`` models the bounded FIFO storage as ``capacity`` plus an
  ordered ``items`` list (oldest arrival first).
- ``RingBufferStateMachine`` models the four observable properties
  (``capacity``, ``size``, ``is_empty``, ``is_full``) and the four operations
  (``push``, ``pop``, ``clear``, ``snapshot_items``) 1:1 with
  ``@transition`` declarations.
- ``FakeRingBuffer`` is synthesized from the state machine and exercised by
  ``FakeRingBufferFuzzTest``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

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

DEFAULT_CAPACITY: int = 10


@dataclass
class RingBufferState:
    """Canonical model state for RingBuffer operations.

    ``items`` stores active elements in FIFO arrival order (index 0 is the
    oldest element), mirroring the contracted ``snapshot_items`` ordering.
    """

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
        """Store an item, evicting the oldest element when at capacity."""
        require(self.state.initialized)
        require_arg(item, Domain.any())
        was_full = len(self.state.items) >= self.state.capacity
        evicted: Optional[Any] = None
        if was_full:
            evicted = self.state.items.pop(0)
        self.state.items.append(item)
        ret: Optional[Any] = make_return_value(evicted)
        if was_full:
            assert len(self.state.items) == self.state.capacity
            assert ret == evicted
        else:
            assert ret is None
            assert len(self.state.items) <= self.state.capacity
        return ret

    @transition(RingBuffer.pop)
    def pop(
        self,
    ) -> Any:
        """Remove and return the oldest stored item."""
        require(self.state.initialized)
        require(len(self.state.items) > 0)
        oldest = self.state.items[0]
        ret: Any = make_return_value(self.state.items.pop(0))
        assert ret == oldest
        assert len(self.state.items) <= self.state.capacity
        return ret

    @transition(RingBuffer.clear)
    def clear(
        self,
    ) -> None:
        """Remove every stored item, resetting the size to zero."""
        require(self.state.initialized)
        self.state.items.clear()
        ret = make_return_value()
        assert ret is None
        assert len(self.state.items) == 0
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(
        self,
    ) -> List[Any]:
        """Return a non-destructive FIFO-ordered snapshot of active items."""
        require(self.state.initialized)
        expected = list(self.state.items)
        ret: List[Any] = make_return_value(list(self.state.items))
        assert ret == expected
        assert len(self.state.items) == len(expected)
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        """Maximum number of items permitted in the circular buffer."""
        require(self.state.initialized)
        ret: int = make_return_value(self.state.capacity)
        assert ret > 0
        return ret

    @transition(name="size")
    def size(self) -> int:
        """Current number of items stored in the circular buffer."""
        require(self.state.initialized)
        expected = len(self.state.items)
        ret: int = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        """Whether the circular buffer contains zero items."""
        require(self.state.initialized)
        expected = len(self.state.items) == 0
        ret: bool = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        """Whether the circular buffer has reached its capacity limit."""
        require(self.state.initialized)
        expected = len(self.state.items) >= self.state.capacity
        ret: bool = make_return_value(expected)
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
# 3. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeRingBufferFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=RingBufferState,
    name="FakeRingBufferFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T20:21:41Z
# LAST_CHANGED: 2026-11-03T20:21:41Z
# CHANGE: Implement RingBuffer model state machine: dataclass tracks capacity and FIFO items; 1:1 transitions for push (Domain.any item, full-eviction returning oldest), pop (gated by non-empty precondition), clear, snapshot_items, and capacity/size/is_empty/is_full properties with postcondition asserts; synthesize FakeRingBuffer and FakeRingBufferFuzzTest.
# --- END AUTOFAB METADATA ---
