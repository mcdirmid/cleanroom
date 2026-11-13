# === File: ring_buffer_impl_pretense.py ===
from __future__ import annotations

from typing import Any, List, Optional

from pretense import sut
from support.lib.lifecycle import LifecycleTestCase

from ring_buffer.lib.ring_buffer import BufferEmptyError, RingBuffer
from ring_buffer.lib.ring_buffer_impl import RingBuffer as RingBufferImpl
from ring_buffer.pretense.ring_buffer_pretense import RingBufferStateMachine


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine binding RingBuffer transitions to the SUT."""

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

    def inner_snapshot_items(self) -> List[Any]:
        target: RingBuffer = sut(RingBuffer)
        return target.snapshot_items()

    def inner_push(self, item: Any) -> Optional[Any]:
        target: RingBuffer = sut(RingBuffer)
        return target.push(item)

    def inner_pop(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        return target.pop()

    def inner_clear(self) -> None:
        target: RingBuffer = sut(RingBuffer)
        target.clear()
        return None


# ==============================================================================
# 2. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestRingBufferImplReal(LifecycleTestCase):
    """Verifies that the concrete RingBuffer implementation satisfies its contracts."""

    def setUp(self) -> None:
        super().setUp()
        self.real: RingBufferImpl = self.sut
        self.sm = RingBufferImplPseudoStateMachine(singletons={RingBuffer: self.real})
        self.checked = self.sm.as_checked(RingBuffer, self.real)

    def test_initial_state_queries(self) -> None:
        capacity = self.checked.capacity
        size = self.checked.size
        is_empty = self.checked.is_empty
        is_full = self.checked.is_full
        items = self.checked.snapshot_items()
        self.assertEqual(capacity, 10)
        self.assertEqual(size, 0)
        self.assertTrue(is_empty)
        self.assertFalse(is_full)
        self.assertEqual(items, [])

    def test_push_pop_fifo(self) -> None:
        self.assertIsNone(self.checked.push("first"))
        self.assertIsNone(self.checked.push("second"))
        self.assertEqual(self.checked.size, 2)
        self.assertEqual(self.checked.pop(), "first")
        self.assertEqual(self.checked.snapshot_items(), ["second"])
        self.checked.clear()
        self.assertTrue(self.checked.is_empty)
        self.assertEqual(self.checked.size, 0)

    def test_overwrite_eviction(self) -> None:
        for index in range(10):
            self.checked.push(str(index))
        self.assertTrue(self.checked.is_full)
        self.assertEqual(self.checked.size, 10)
        self.assertEqual(self.checked.push("overflow"), "0")
        self.assertEqual(
            self.checked.snapshot_items(),
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "overflow"],
        )

    def test_pop_empty_violation(self) -> None:
        self.checked.violating(BufferEmptyError).pop()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T16:25:31Z
# LAST_CHANGED: 2026-11-12T16:25:04Z
# CHANGE: Implemented RingBuffer implementation pretense module: RingBufferImplPseudoStateMachine inherits the interface state machine and overrides only inner transitions to bind the concrete SUT via sut(RingBuffer) for all eight members; TestRingBufferImplReal LifecycleTestCase wires self.sut/singletons/as_checked and drives full statement coverage (queries, FIFO push/pop, overwrite eviction on the 11th push, clear) plus the terminal BufferEmptyError pop violation via self.checked.violating. Verified statically with bin/check_files.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T16:25:31Z
# PRETENSE_QA_AUDIT: 2026-11-12T16:25:17Z
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

from ring_buffer.lib.ring_buffer import BufferEmptyError, RingBuffer


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions)
# ==============================================================================

@dataclass
class RingBufferState:
    """Model state for a bounded circular FIFO buffer with overwrite eviction."""
    capacity: int = 10
    items: List[Any] = field(default_factory=list)


class RingBufferStateMachine(StateMachine[RingBufferState]):
    """Pretense model of RingBuffer; every public member is one 1:1 transition."""

    def __init__(
        self,
        state: Optional[RingBufferState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> RingBufferState:
        """Constructs a blank empty buffer using the open capacity parameter."""
        return RingBufferState(capacity=self.initial_capacity, items=[])

    @property
    def initial_capacity(self) -> int:
        """Open capacity parameter; implementation pseudo-state machines may specialize it."""
        return 10

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the blank initial buffer state for fake initialization."""
        self.state.capacity = self.initial_capacity
        self.state.items = []

    # -- Read-only observability queries --------------------------------------

    @transition(name="capacity")
    def capacity(self) -> int:
        """Maximum number of items the buffer can hold."""
        ret = self.inner_capacity()
        assert ret == self.state.capacity
        return ret

    def inner_capacity(self) -> int:
        """Computes the fake capacity from model state."""
        return self.state.capacity

    @transition(name="size")
    def size(self) -> int:
        """Current number of items stored in the buffer."""
        ret = self.inner_size()
        assert ret == len(self.state.items)
        return ret

    def inner_size(self) -> int:
        """Computes the fake size from model state."""
        return len(self.state.items)

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        """Whether the buffer currently contains zero items."""
        ret = self.inner_is_empty()
        assert ret == (len(self.state.items) == 0)
        return ret

    def inner_is_empty(self) -> bool:
        """Computes the fake emptiness flag from model state."""
        return len(self.state.items) == 0

    @transition(name="is_full")
    def is_full(self) -> bool:
        """Whether the buffer has reached its capacity limit."""
        ret = self.inner_is_full()
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret

    def inner_is_full(self) -> bool:
        """Computes the fake saturation flag from model state."""
        return len(self.state.items) >= self.state.capacity

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(self) -> List[Any]:
        """Non-destructive snapshot of active items in circular FIFO arrival order."""
        ret = self.inner_snapshot_items()
        assert ret == self.state.items
        assert sut(RingBuffer).size == len(self.state.items)
        return ret

    def inner_snapshot_items(self) -> List[Any]:
        """Computes the fake FIFO snapshot from model state."""
        return list(self.state.items)

    # -- Mutating operations ---------------------------------------------------

    @transition(RingBuffer.push)
    def push(self, item: Any) -> Optional[Any]:
        """Appends an item, evicting and returning the oldest item on saturation."""
        require_arg(item, Domain.type(str), preferred=["first", "second"])
        ret = self.inner_push(item)
        if len(self.state.items) < self.state.capacity:
            self.state.items.append(item)
            assert ret is None
        else:
            evicted = self.state.items.pop(0)
            self.state.items.append(item)
            assert ret == evicted
        assert len(self.state.items) <= self.state.capacity
        assert sut(RingBuffer).size == len(self.state.items)
        return ret

    def inner_push(self, item: Any) -> Optional[Any]:
        """Computes the fake eviction result from model state."""
        if len(self.state.items) < self.state.capacity:
            return None
        return self.state.items[0]

    @transition(RingBuffer.pop)
    def pop(self) -> Any:
        """Removes and returns the oldest item; empty buffers raise BufferEmptyError."""
        require(bool(self.state.items), BufferEmptyError)
        ret = self.inner_pop()
        removed = self.state.items.pop(0)
        assert ret == removed
        assert sut(RingBuffer).size == len(self.state.items)
        return ret

    def inner_pop(self) -> Any:
        """Computes the fake oldest item from model state."""
        return self.state.items[0]

    @transition(RingBuffer.clear)
    def clear(self) -> None:
        """Removes all items and resets the buffer to empty."""
        ret = self.inner_clear()
        self.state.items.clear()
        assert ret is None
        assert len(self.state.items) == 0
        assert sut(RingBuffer).size == 0
        return ret

    def inner_clear(self) -> None:
        """Computes the fake clear result (always None)."""
        return None


proto = RingBufferStateMachine()


# ==============================================================================
# 2. Fake Synthesis (Interface Components)
# ==============================================================================

FakeRingBuffer = synthesize_fake(RingBufferStateMachine)


def make_ring_buffer_fake(state: Optional[RingBufferState] = None) -> RingBuffer:
    """Synthesizes a verified in-memory fake RingBuffer instance."""
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
    """Verifies that the synthesized fake satisfies every transition and seeding transition."""

    def setUp(self) -> None:
        self.fake = make_ring_buffer_fake()
        self.sm = RingBufferStateMachine(singletons={RingBuffer: self.fake})

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        capacity = self.fake.capacity
        self.assertEqual(capacity, 10)
        self.assertEqual(self.fake.size, 0)
        self.assertTrue(self.fake.is_empty)
        self.assertFalse(self.fake.is_full)
        self.assertEqual(self.fake.snapshot_items(), [])
        self.assertIsNone(self.fake.push("first"))
        self.assertEqual(self.fake.size, 1)
        self.assertFalse(self.fake.is_empty)
        self.assertEqual(self.fake.snapshot_items(), ["first"])
        self.assertIsNone(self.fake.push("second"))
        self.assertEqual(self.fake.snapshot_items(), ["first", "second"])
        self.assertEqual(self.fake.pop(), "first")
        self.assertEqual(self.fake.size, 1)
        self.fake.clear()
        self.assertTrue(self.fake.is_empty)
        self.assertEqual(self.fake.size, 0)
        self.assertEqual(self.fake.snapshot_items(), [])

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T16:24:58Z
# LAST_CHANGED: 2026-11-12T16:24:58Z
# CHANGE: Implemented RingBuffer interface pretense model: RingBufferState (capacity=10, items), RingBufferStateMachine with 1:1 transitions for capacity/size/is_empty/is_full (property transitions via @transition(name=...)) and push/pop/clear/snapshot_items (BufferEmptyError precondition on pop, overwrite eviction modeling), synthesized FakeRingBuffer fake, make_ring_buffer_fake factory, TestRingBufferFake fixed scenario tests covering all transitions/seeding, and FakeRingBufferFuzzTest Hypothesis fuzzing. Verified with bin/check_files (static + fake runtime).
# --- END AUTOFAB METADATA ---
