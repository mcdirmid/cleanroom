# === File: ring_buffer_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for RingBuffer."""

from __future__ import annotations

from typing import Any, List, Optional
import unittest

from pretense import call_target, sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmarks.runs.ring_buffer_deepseek_flash_2.parts.ring_buffer.lib.ring_buffer import (
    BufferEmptyError,
)
from benchmarks.runs.ring_buffer_deepseek_flash_2.parts.ring_buffer.lib.ring_buffer_impl import (
    RingBuffer,
    __initialize__,
)
from benchmarks.runs.ring_buffer_deepseek_flash_2.parts.ring_buffer.pretense.ring_buffer_pretense import (
    RingBufferState,
    RingBufferStateMachine,
)


_DEFAULT_CAPACITY = 10


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine for the concrete RingBuffer singleton."""

    def make_initial_state(self) -> RingBufferState:
        """Specializes the uncontracted default capacity to the concrete implementation value."""
        return RingBufferState(items=[], capacity=_DEFAULT_CAPACITY)

    def inner_push(
        self,
        item: Any,
    ) -> Optional[Any]:
        target: RingBuffer = sut(RingBuffer)
        previous_size = target.size
        assert previous_size == len(self.state.items)
        ret = call_target(target.push(item))
        if previous_size >= self.state.capacity:
            assert ret is self.state.items[0]
            assert target.size == self.state.capacity
        else:
            assert ret is None
            assert target.size == previous_size + 1
        return ret

    def inner_pop(
        self,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        previous_size = target.size
        assert previous_size == len(self.state.items)
        ret = call_target(target.pop())
        assert ret is self.state.items[0]
        assert target.size == previous_size - 1
        return ret

    def inner_clear(
        self,
    ) -> None:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.clear())
        assert ret is None
        assert target.size == 0
        assert target.is_empty
        return None

    def inner_snapshot_items(
        self,
    ) -> List[Any]:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.snapshot_items())
        assert len(ret) == len(self.state.items)
        assert ret is not self.state.items
        assert all(actual is expected for actual, expected in zip(ret, self.state.items))
        return ret

    def inner_capacity(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "capacity"))
        assert ret == self.state.capacity
        return ret

    def inner_size(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "size"))
        assert ret == len(self.state.items)
        return ret

    def inner_is_empty(self) -> bool:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "is_empty"))
        assert ret == (len(self.state.items) == 0)
        return ret

    def inner_is_full(self) -> bool:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "is_full"))
        assert ret == (len(self.state.items) >= self.state.capacity)
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
        self.checked: Any = self.sm.as_checked(RingBuffer, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_blank_buffer_state(self) -> None:
        """Verifies the initial queries on an empty concrete buffer."""
        self.assertEqual(self.checked.capacity, _DEFAULT_CAPACITY)
        self.assertEqual(self.checked.size, 0)
        self.assertTrue(self.checked.is_empty)
        self.assertFalse(self.checked.is_full)
        self.assertEqual(self.checked.snapshot_items(), [])

    def test_push_and_pop_preserve_fifo_order(self) -> None:
        """Verifies available-capacity push and non-empty pop behavior."""
        self.assertIsNone(self.checked.push("alpha"))
        self.assertIsNone(self.checked.push("beta"))
        self.assertEqual(self.checked.size, 2)
        self.assertFalse(self.checked.is_empty)
        self.assertEqual(self.checked.snapshot_items(), ["alpha", "beta"])
        self.assertEqual(self.checked.pop(), "alpha")
        self.assertEqual(self.checked.pop(), "beta")
        self.assertTrue(self.checked.is_empty)
        self.assertEqual(self.checked.snapshot_items(), [])

    def test_push_evicts_oldest_when_full(self) -> None:
        """Verifies overwrite eviction on a saturated concrete buffer."""
        self.assertIsNone(self.checked.push(0))
        self.assertIsNone(self.checked.push(1))
        self.assertIsNone(self.checked.push(2))
        self.assertIsNone(self.checked.push(3))
        self.assertIsNone(self.checked.push(4))
        self.assertIsNone(self.checked.push(5))
        self.assertIsNone(self.checked.push(6))
        self.assertIsNone(self.checked.push(7))
        self.assertIsNone(self.checked.push(8))
        self.assertIsNone(self.checked.push(9))
        self.assertTrue(self.checked.is_full)
        self.assertEqual(self.checked.size, _DEFAULT_CAPACITY)
        self.assertEqual(self.checked.push(10), 0)
        self.assertEqual(self.checked.size, _DEFAULT_CAPACITY)
        self.assertEqual(
            self.checked.snapshot_items(),
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        )

    def test_clear_removes_all_items(self) -> None:
        """Verifies that clear resets the concrete buffer size to zero."""
        self.assertIsNone(self.checked.push("alpha"))
        self.assertIsNone(self.checked.push("beta"))
        self.assertFalse(self.checked.is_empty)
        self.checked.clear()
        self.assertEqual(self.checked.size, 0)
        self.assertTrue(self.checked.is_empty)
        self.assertFalse(self.checked.is_full)
        self.assertEqual(self.checked.snapshot_items(), [])

    def test_snapshot_items_is_non_mutating(self) -> None:
        """Verifies repeated snapshots leave buffer contents and size untouched."""
        self.assertIsNone(self.checked.push("alpha"))
        self.assertIsNone(self.checked.push("beta"))
        first = self.checked.snapshot_items()
        second = self.checked.snapshot_items()
        self.assertEqual(first, ["alpha", "beta"])
        self.assertEqual(second, ["alpha", "beta"])
        self.assertIsNot(first, second)
        self.assertEqual(self.checked.size, 2)
        self.assertFalse(self.checked.is_empty)

    def test_pop_from_empty_buffer_violates_contract(self) -> None:
        """Verifies the contracted BufferEmptyError on an empty concrete buffer."""
        self.checked.violating(BufferEmptyError).pop()


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
    initial_state_factory=proto.make_initial_state,
    name="RingBufferFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T19:34:34Z
# LAST_CHANGED: 2026-11-10T19:32:31Z
# CHANGE: Implemented RingBuffer implementation pseudo-state machine inheriting the interface state machine, specializing make_initial_state to the concrete default capacity 10, and overriding every inner transition to bind the concrete singleton via sut(RingBuffer)/call_target with parity assertions against model state; added TestRingBufferImplReal scenarios covering blank queries, FIFO push/pop, overwrite eviction, clear, non-mutating snapshots, and BufferEmptyError via checked.violating plus RingBufferFuzzTest.
# PRETENSE_COVERAGE_AUDIT: 2026-11-10T19:34:34Z
# PRETENSE_QA_AUDIT: 2026-11-10T19:32:48Z
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
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmarks.runs.ring_buffer_deepseek_flash_2.parts.ring_buffer.lib.ring_buffer import (
    BufferEmptyError,
    RingBuffer,
)


_DEFAULT_FAKE_CAPACITY = 4


@dataclass
class RingBufferState:
    """Canonical model state for RingBuffer operations."""

    items: List[Any] = field(default_factory=list)
    capacity: int = _DEFAULT_FAKE_CAPACITY


class RingBufferStateMachine(StateMachine[RingBufferState]):
    """Unified Pretense State Machine for RingBuffer."""

    def __init__(
        self,
        state: Optional[RingBufferState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def capacity_limit(self) -> int:
        """Overridable capacity specialization hook; the public interface omits the default."""
        return _DEFAULT_FAKE_CAPACITY

    def make_initial_state(self) -> RingBufferState:
        """Constructs a blank model state with an empty buffer for fake synthesis."""
        return RingBufferState(items=[], capacity=self.capacity_limit())

    @transition(RingBuffer.push)
    def push(
        self,
        item: Any,
    ) -> Optional[Any]:
        require_arg(item, Domain.any())
        ret: Optional[Any] = self.inner_push(item)
        if len(self.state.items) >= self.state.capacity:
            evicted = self.state.items.pop(0)
            assert ret is evicted
            self.state.items.append(item)
            assert len(self.state.items) == self.state.capacity
        else:
            assert ret is None
            previous_size = len(self.state.items)
            self.state.items.append(item)
            assert len(self.state.items) == previous_size + 1
        return ret

    def inner_push(
        self,
        item: Any,
    ) -> Optional[Any]:
        if len(self.state.items) >= self.state.capacity:
            return self.state.items[0]
        return None

    @transition(RingBuffer.pop)
    def pop(
        self,
    ) -> Any:
        require(bool(self.state.items), error=BufferEmptyError)
        ret: Any = self.inner_pop()
        removed = self.state.items.pop(0)
        assert ret is removed
        return ret

    def inner_pop(
        self,
    ) -> Any:
        return self.state.items[0]

    @transition(RingBuffer.clear)
    def clear(
        self,
    ) -> None:
        ret = self.inner_clear()
        assert ret is None
        self.state.items.clear()
        assert len(self.state.items) == 0
        return None

    def inner_clear(
        self,
    ) -> None:
        return None

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(
        self,
    ) -> List[Any]:
        ret: List[Any] = self.inner_snapshot_items()
        assert len(ret) == len(self.state.items)
        assert ret is not self.state.items
        return ret

    def inner_snapshot_items(
        self,
    ) -> List[Any]:
        return list(self.state.items)

    @transition(name="capacity")
    def capacity(self) -> int:
        ret: int = self.inner_capacity()
        assert ret == self.state.capacity
        return ret

    def inner_capacity(self) -> int:
        return self.state.capacity

    @transition(name="size")
    def size(self) -> int:
        ret: int = self.inner_size()
        assert ret == len(self.state.items)
        return ret

    def inner_size(self) -> int:
        return len(self.state.items)

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        ret: bool = self.inner_is_empty()
        assert ret == (len(self.state.items) == 0)
        return ret

    def inner_is_empty(self) -> bool:
        return len(self.state.items) == 0

    @transition(name="is_full")
    def is_full(self) -> bool:
        ret: bool = self.inner_is_full()
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret

    def inner_is_full(self) -> bool:
        return len(self.state.items) >= self.state.capacity


proto = RingBufferStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeRingBuffer = synthesize_fake(RingBufferStateMachine)

def make_ring_buffer_fake(
    state: Optional[RingBufferState] = None,
) -> RingBuffer:
    """Synthesizes fake instance for RingBuffer."""
    return FakeRingBuffer(state=state or proto.make_initial_state())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestRingBufferFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions."""

    def setUp(self) -> None:
        self.fake = make_ring_buffer_fake()

    def test_blank_buffer_queries(self) -> None:
        """Exercises capacity, size, is_empty, is_full, and snapshot on a blank fake."""
        self.assertEqual(self.fake.capacity, _DEFAULT_FAKE_CAPACITY)
        self.assertEqual(self.fake.size, 0)
        self.assertTrue(self.fake.is_empty)
        self.assertFalse(self.fake.is_full)
        self.assertEqual(self.fake.snapshot_items(), [])

    def test_push_and_pop_preserve_fifo_order(self) -> None:
        """Exercises push and pop on the available-capacity branch."""
        self.assertIsNone(self.fake.push("alpha"))
        self.assertIsNone(self.fake.push("beta"))
        self.assertEqual(self.fake.size, 2)
        self.assertFalse(self.fake.is_empty)
        self.assertEqual(self.fake.snapshot_items(), ["alpha", "beta"])
        self.assertEqual(self.fake.pop(), "alpha")
        self.assertEqual(self.fake.pop(), "beta")
        self.assertTrue(self.fake.is_empty)
        self.assertEqual(self.fake.snapshot_items(), [])

    def test_push_evicts_oldest_when_full(self) -> None:
        """Exercises push on the at-capacity overwrite eviction branch."""
        for value in range(_DEFAULT_FAKE_CAPACITY):
            self.assertIsNone(self.fake.push(value))
        self.assertTrue(self.fake.is_full)
        self.assertEqual(self.fake.size, _DEFAULT_FAKE_CAPACITY)
        self.assertEqual(self.fake.push("overflow"), 0)
        self.assertEqual(self.fake.size, _DEFAULT_FAKE_CAPACITY)
        expected = list(range(1, _DEFAULT_FAKE_CAPACITY)) + ["overflow"]
        self.assertEqual(self.fake.snapshot_items(), expected)

    def test_clear_resets_buffer(self) -> None:
        """Exercises clear and verifies the size reset postcondition."""
        self.assertIsNone(self.fake.push("alpha"))
        self.assertIsNone(self.fake.push("beta"))
        self.assertFalse(self.fake.is_empty)
        self.fake.clear()
        self.assertEqual(self.fake.size, 0)
        self.assertTrue(self.fake.is_empty)
        self.assertFalse(self.fake.is_full)
        self.assertEqual(self.fake.snapshot_items(), [])


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeRingBufferFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeRingBufferFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T19:32:25Z
# LAST_CHANGED: 2026-11-10T19:32:25Z
# CHANGE: Implemented RingBuffer pretense state machine: RingBufferState (items FIFO list + capacity) with 1:1 transitions for push (available-capacity and overwrite-eviction branches with inner delegation and postcondition assertions), pop (BufferEmptyError precondition gate plus non-empty postcondition), clear, snapshot_items (FIFO/non-mutating), and capacity/size/is_empty/is_full property transitions; synthesized FakeRingBuffer factory, TestRingBufferFake covering all transitions, and FakeRingBufferFuzzTest.
# --- END AUTOFAB METADATA ---
