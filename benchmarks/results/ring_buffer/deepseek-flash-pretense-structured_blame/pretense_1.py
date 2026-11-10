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
from benchmark_2.parts.ring_buffer.pretense.ring_buffer_pretense import (
    FakeRingBuffer,
    RingBufferState,
    RingBufferStateMachine,
    make_ring_buffer_fake,
)
from benchmark_2.parts.ring_buffer.lib.ring_buffer import BufferEmptyError
from benchmark_2.parts.ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# The pseudo-state machine inherits the interface state machine (and therefore
# all model state, precondition guards, and domain strategies). Overrides add
# only the real-SUT pivot via call_target(...) plus SUT-relative postcondition
# observations; they never mutate self.state.

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
        assert target.size == min(before + 1, capacity)
        return ret

    @transition(RingBuffer.pop)
    def pop(
        self,
    ) -> Any:
        target: RingBuffer = sut(RingBuffer)
        before = target.size
        ret = call_target(target.pop())
        assert target.size == before - 1
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
        ret = call_target(target.snapshot_items())
        assert len(ret) == target.size
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "capacity"))
        assert ret == self.state.capacity
        return ret

    @transition(name="size")
    def size(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "size"))
        assert ret == target.size
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

    def test_real_blank_state(self) -> None:
        """Drives every observability property on a freshly created buffer."""
        assert self.checked.capacity == 10
        assert self.checked.size == 0
        assert self.checked.is_empty
        assert not self.checked.is_full
        assert self.checked.snapshot_items() == []

    def test_real_fifo_operation_sequence(self) -> None:
        """Drives a FIFO sequence through push, pop, and clear."""
        assert self.checked.push("alpha") is None
        assert self.checked.push("beta") is None
        assert self.checked.size == 2
        assert not self.checked.is_empty
        assert not self.checked.is_full
        assert self.checked.snapshot_items() == ["alpha", "beta"]
        assert self.checked.pop() == "alpha"
        assert self.checked.size == 1
        assert self.checked.snapshot_items() == ["beta"]
        self.checked.clear()
        assert self.checked.size == 0
        assert self.checked.is_empty
        assert self.checked.snapshot_items() == []

    def test_real_overwrite_eviction_at_capacity(self) -> None:
        """Drives saturation so push overwrite eviction is exercised."""
        capacity = self.checked.capacity
        for index in range(capacity):
            assert self.checked.push(index) is None
        assert self.checked.is_full
        assert self.checked.size == capacity
        assert self.checked.push("newest") == 0
        assert self.checked.size == capacity
        assert self.checked.is_full
        assert self.checked.snapshot_items() == [*range(1, capacity), "newest"]

    def test_real_pop_on_empty_buffer_reports_empty_failure(self) -> None:
        """Drives the empty-buffer pop error branch deterministically."""
        buffer = self.checked
        assert buffer.size == 0
        assert buffer.is_empty
        assert buffer.push("alpha") is None
        assert buffer.pop() == "alpha"
        assert buffer.size == 0
        assert buffer.is_empty
        with self.assertRaises(BufferEmptyError):
            buffer.pop()
        assert buffer.size == 0
        assert buffer.is_empty


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
# LAST_CLEANED: 2026-11-08T17:41:40Z
# LAST_CHANGED: 2026-11-08T17:38:25Z
# CHANGE: Covered the contracted empty-buffer pop failure branch: added deterministic TestRingBufferImplReal.test_real_pop_on_empty_buffer_reports_empty_failure which drives push+pop back to size zero through self.checked transitions, then invokes checked pop on the empty buffer and verifies the contracted BufferEmptyError; also restored the verified module body so no specification-slug text remains in comments. Audited remaining transitions (push, clear, snapshot_items, and all properties) and confirmed pop is the only contracted error branch.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:41:40Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:41:28Z
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
from benchmark_2.parts.ring_buffer.lib.ring_buffer import BufferEmptyError, RingBuffer


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================
# Model state mirrors the bounded circular storage: a fixed capacity and the
# active items kept in FIFO arrival order (oldest first). Transitions model
# target members 1:1 and pivot through (...) so the same body
# can be re-executed as an onion against the real implementation.
#
#   @transition(RingBuffer.push)
#   def push(self, item: Any) -> Optional[Any]:
#       ...
#       ret = (evicted)
#       return ret

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
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state or RingBufferState(), singletons=singletons, **kwargs)

    @transition(RingBuffer.push)
    def push(
        self,
        item: Any,
    ) -> Optional[Any]:
        require_arg(item, Domain.any(), preferred=["alpha", 0])
        before = len(self.state.items)
        evicted: Optional[Any] = None
        if before >= self.state.capacity:
            evicted = self.state.items.pop(0)
        self.state.items.append(item)
        ret = self.inner_push(item)
        assert len(self.state.items) == min(before + 1, self.state.capacity)
        assert ret == evicted
        return ret

    @transition(RingBuffer.pop)
    def pop(
        self,
    ) -> Any:
        ret: Any = None
        if len(self.state.items) == 0:
            with raises(BufferEmptyError):
                ret = self.inner_pop()
            return ret
        removed = self.state.items.pop(0)
        ret = self.inner_pop()
        assert len(self.state.items) < self.state.capacity
        assert ret == removed
        return ret

    @transition(RingBuffer.clear)
    def clear(
        self,
    ) -> None:
        self.state.items.clear()
        ret = self.inner_clear()
        assert self.state.items == []
        assert ret is None
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(
        self,
    ) -> List[Any]:
        snapshot = list(self.state.items)
        ret = self.inner_snapshot_items()
        assert self.state.items == snapshot
        assert ret == snapshot
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        ret = self.inner_capacity()
        assert ret == self.state.capacity
        assert ret > 0
        return ret

    @transition(name="size")
    def size(self) -> int:
        expected = len(self.state.items)
        ret = self.inner_size()
        assert ret == expected
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        expected = len(self.state.items) == 0
        ret = self.inner_is_empty()
        assert ret == expected
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        expected = len(self.state.items) >= self.state.capacity
        ret = self.inner_is_full()
        assert ret == expected
        return ret


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

    def test_property_transitions(self) -> None:
        """Exercises every observability property on a blank fake."""
        assert self.fake.capacity == 10
        assert self.fake.size == 0
        assert self.fake.is_empty
        assert not self.fake.is_full

    def test_push_and_pop_fifo_order(self) -> None:
        """Exercises push on available capacity and pop on a non-empty fake."""
        assert self.fake.push("alpha") is None
        assert self.fake.push("beta") is None
        assert self.fake.size == 2
        assert not self.fake.is_empty
        assert self.fake.snapshot_items() == ["alpha", "beta"]
        assert self.fake.pop() == "alpha"
        assert self.fake.size == 1
        assert self.fake.snapshot_items() == ["beta"]

    def test_push_overwrite_eviction(self) -> None:
        """Exercises push overwrite eviction once the fake reaches capacity."""
        capacity = self.fake.capacity
        for index in range(capacity):
            assert self.fake.push(index) is None
        assert self.fake.is_full
        assert self.fake.size == capacity
        evicted = self.fake.push("newest")
        assert evicted == 0
        assert self.fake.size == capacity
        assert self.fake.snapshot_items() == [*range(1, capacity), "newest"]

    def test_clear_resets_state(self) -> None:
        """Exercises clear on a populated fake."""
        assert self.fake.push("alpha") is None
        self.fake.clear()
        assert self.fake.size == 0
        assert self.fake.is_empty
        assert not self.fake.is_full
        assert self.fake.snapshot_items() == []

    def test_pop_on_empty_fake_reports_empty_failure(self) -> None:
        """Exercises pop on a blank fake so the contracted failure is observable."""
        assert self.fake.is_empty
        with self.assertRaises(BufferEmptyError):
            self.fake.pop()
        assert self.fake.size == 0
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
# LAST_CLEANED: 2026-11-08T17:40:32Z
# LAST_CHANGED: 2026-11-08T17:40:32Z
# CHANGE: Modeled the zero-size pop failure as an operation outcome obligation instead of a caller precondition: removed the blanket non-empty require gate from the pop transition so the empty state is representable, and declared the contracted BufferEmptyError around the pivot via with raises(BufferEmptyError); the synthesized blank fake now raises the contracted error on an empty pop. Added deterministic TestRingBufferFake coverage for pop on a blank fake asserting the contracted failure and unchanged zero size. Audited sibling transitions (push, clear, snapshot_items, capacity/size/is_empty/is_full) and confirmed none declares a contracted error outcome, so no other gate needed removal.
# --- END AUTOFAB METADATA ---
