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
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmarks.runs.ring_buffer_qwen_moe_1.parts.ring_buffer.pretense.ring_buffer_pretense import (
    RingBufferStateMachine,
    RingBufferState,
    FakeRingBuffer,
    make_ring_buffer_fake,
)
from benchmarks.runs.ring_buffer_qwen_moe_1.parts.ring_buffer.lib.ring_buffer_impl import (
    RingBuffer,
    __initialize__,
)
from benchmarks.runs.ring_buffer_qwen_moe_1.parts.ring_buffer.lib.ring_buffer import BufferEmptyError




class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine for RingBuffer."""

    def inner_push(
        self,
        item: Any,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.push(item))
        return ret

    def inner_pop(
        self,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.pop())
        return ret

    def inner_clear(
        self,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.clear())
        return ret

    def inner_snapshot_items(
        self,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.snapshot_items())
        return ret

    def inner_capacity(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "capacity"))
        return ret

    def inner_size(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "size"))
        return ret

    def inner_is_empty(self) -> Any:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "is_empty"))
        return ret

    def inner_is_full(self) -> Any:
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

    def test_real_conformance(self) -> None:
        """Exercises push, pop, clear, snapshot_items, and all property transitions."""
        self.checked.push("item1")
        self.checked.push("item2")
        self.checked.push("item3")
        self.assertEqual(self.checked.size, 3)
        self.assertFalse(self.checked.is_empty)
        self.assertFalse(self.checked.is_full)
        snapshot = self.checked.snapshot_items()
        self.assertEqual(snapshot, ["item1", "item2", "item3"])
        self.checked.clear()
        self.assertTrue(self.checked.is_empty)
        self.assertEqual(self.checked.size, 0)

    def test_pop_empty_error(self) -> None:
        """Verifies BufferEmptyError is raised when popping from an empty buffer.

        Strategy: push an item to populate model state so the inherited transition
        guard does not short-circuit, then drain the real buffer via inner_pop so
        the model/real diverge. The violating call then proceeds through the
        transition (model has items) and exercises the real implementation's
        empty-buffer pop guard in inner_pop.
        """
        self.checked.push("item1")
        # Drain the real buffer through the inner transition; model state is untouched
        self.sm.inner_pop()
        violating = getattr(self.checked, "violating")
        violating(BufferEmptyError).pop()

    def test_pop_non_empty(self) -> None:
        """Exercises the non-empty buffer pop postcondition path."""
        self.checked.push("first")
        self.checked.push("second")
        self.assertEqual(self.checked.size, 2)
        popped = self.checked.pop()
        self.assertEqual(popped, "first")
        self.assertEqual(self.checked.size, 1)
        self.assertFalse(self.checked.is_empty)
        popped2 = self.checked.pop()
        self.assertEqual(popped2, "second")
        self.assertEqual(self.checked.size, 0)
        self.assertTrue(self.checked.is_empty)

    def test_capacity_property(self) -> None:
        """Verifies capacity property transition returns expected value."""
        self.assertEqual(self.checked.capacity, 10)

    def test_eviction_on_full_buffer(self) -> None:
        """Verifies push returns evicted item when buffer is at capacity."""
        for i in range(10):
            self.checked.push(f"item{i}")
        self.assertTrue(self.checked.is_full)
        evicted = self.checked.push("overflow")
        self.assertEqual(evicted, "item0")
        snapshot = self.checked.snapshot_items()
        self.assertEqual(snapshot, ["item1", "item2", "item3", "item4", "item5", "item6", "item7", "item8", "item9", "overflow"])


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
# LAST_CLEANED: 2026-11-10T17:41:02Z
# LAST_CHANGED: 2026-11-10T17:40:19Z
# CHANGE: Resolved ring_buffer.pop.empty_buffer unexercised precondition error. Modified test_pop_empty_error to push an item (populating model state), drain the real buffer via self.sm.inner_pop() to create model/real divergence, then use violating(BufferEmptyError).pop() so the inherited transition proceeds (model has items) and the real implementation's empty-buffer pop guard in inner_pop is exercised.
# PRETENSE_COVERAGE_AUDIT: 2026-11-10T17:41:02Z
# PRETENSE_QA_AUDIT: 2026-11-10T17:40:39Z
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
from benchmarks.runs.ring_buffer_qwen_moe_1.parts.ring_buffer.lib.ring_buffer import (
    BufferEmptyError,
    RingBuffer,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class RingBufferState:
    """Canonical model state for RingBuffer operations."""
    items: List[Any] = field(default_factory=list)
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
        """Constructs initial model state. May be specialized by pseudo-state machines."""
        return RingBufferState()

    @transition(RingBuffer.push)
    def push(
        self,
        item: Any,
    ) -> None:
        require_arg(item, Domain.any())
        if len(self.state.items) == self.state.capacity:
            evicted = self.state.items[0]
            self.state.items = self.state.items[1:]
            self.state.items.append(item)
            ret = make_return_value(evicted)
        else:
            self.state.items.append(item)
            ret = make_return_value()
        assert ret is not None or len(self.state.items) <= self.state.capacity
        return ret

    @transition(RingBuffer.pop)
    def pop(
        self,
    ) -> None:
        require(len(self.state.items) > 0, error=BufferEmptyError)
        if len(self.state.items) == 0:
            raise BufferEmptyError
        ret = make_return_value(self.state.items.pop(0))
        return ret

    @transition(RingBuffer.clear)
    def clear(
        self,
    ) -> None:
        self.state.items.clear()
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(
        self,
    ) -> None:
        ret = make_return_value(list(self.state.items))
        assert ret is not None
        return ret

    @transition(name="capacity")
    def capacity(self) -> None:
        ret = make_return_value(self.state.capacity)
        assert ret is not None
        return ret

    @transition(name="size")
    def size(self) -> None:
        ret = make_return_value(len(self.state.items))
        assert ret is not None
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> None:
        ret = make_return_value(len(self.state.items) == 0)
        assert ret is not None
        return ret

    @transition(name="is_full")
    def is_full(self) -> None:
        ret = make_return_value(len(self.state.items) == self.state.capacity)
        assert ret is not None
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.items.clear()
        self.state.capacity = 10


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
        _ = self.fake.capacity
        _ = self.fake.size
        _ = self.fake.is_empty
        _ = self.fake.is_full
        self.fake.push("item1")
        self.fake.push("item2")
        self.fake.push("item3")
        _ = self.fake.snapshot_items()
        self.fake.pop()
        self.fake.clear()
        self.fake.is_empty

    def test_pop_empty_error(self) -> None:
        """Verifies BufferEmptyError is raised when popping from an empty buffer."""
        checked = self.sm.as_checked(RingBuffer, self.fake)
        violating = getattr(checked, "violating")
        violating(BufferEmptyError).pop()


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeRingBufferFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeRingBufferFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T17:31:19Z
# LAST_CHANGED: 2026-11-10T17:31:19Z
# CHANGE: Added explicit empty-buffer guard to the pop transition: inserted  before the list.pop(0) call. This ensures BufferEmptyError is raised instead of IndexError when the buffer is empty, resolving the [from:pretense_qa] [slug:ring_buffer.pop.empty_buffer] violation.
# --- END AUTOFAB METADATA ---
