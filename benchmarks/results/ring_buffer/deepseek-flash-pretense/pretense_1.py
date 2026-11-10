# === File: ring_buffer_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for RingBuffer.

The pseudo-state machine inherits the interface model state and argument
domains, overriding transitions to invoke the concrete deque-backed SUT at the
`call_target` pivot and assert the contracted return/postconditions against
model state captured before delegation. Overrides are observation-only: they
never mutate `self.state`, because model bookkeeping is performed by the
inherited interface transition that delegates into these overrides through
`inner_transition` under the checked adapter. The real suite drives the
concrete ring buffer through the checked adapter, covering the push-with-space,
push-with-eviction, pop, clear, snapshot, and empty-pop error branches.
"""

from __future__ import annotations

import unittest
from typing import Any, List, Optional

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
from benchmark_1.parts.ring_buffer.lib.ring_buffer import BufferEmptyError
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

class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine for RingBuffer."""

    @transition(RingBuffer.push)
    def push(self, item: Any) -> Optional[Any]:
        require(self.state.capacity >= 1)
        target: RingBuffer = sut(RingBuffer)
        was_full: bool = len(self.state.items) >= self.state.capacity
        expected_evicted: Optional[Any] = self.state.items[0] if was_full else None
        ret: Optional[Any] = call_target(target.push(item))
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
        expected: Any = self.state.items[0]
        ret: Any = call_target(target.pop())
        assert ret == expected
        return ret

    @transition(RingBuffer.clear)
    def clear(self) -> None:
        target: RingBuffer = sut(RingBuffer)
        ret: None = call_target(target.clear())
        assert ret is None
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(self) -> List[Any]:
        target: RingBuffer = sut(RingBuffer)
        snapshot: List[Any] = list(self.state.items)
        ret: List[Any] = call_target(target.snapshot_items())
        assert ret == snapshot
        assert len(ret) == len(snapshot)
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        expected_capacity: int = self.state.capacity
        ret: int = call_target(target.capacity)
        assert ret == expected_capacity
        assert ret >= 1
        return ret

    @transition(name="size")
    def size(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        expected_size: int = len(self.state.items)
        ret: int = call_target(target.size)
        assert ret == expected_size
        assert 0 <= ret <= self.state.capacity
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        target: RingBuffer = sut(RingBuffer)
        expected_empty: bool = len(self.state.items) == 0
        ret: bool = call_target(target.is_empty)
        assert ret == expected_empty
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        target: RingBuffer = sut(RingBuffer)
        expected_full: bool = len(self.state.items) >= self.state.capacity
        ret: bool = call_target(target.is_full)
        assert ret == expected_full
        return ret


proto = RingBufferImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestRingBufferImplReal(unittest.TestCase):
    """Verifies that the concrete RingBuffer satisfies its contracts."""

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

    def test_initial_state_observes_empty_buffer(self) -> None:
        _ = self.checked.capacity
        _ = self.checked.size
        _ = self.checked.is_empty
        _ = self.checked.is_full
        _ = self.checked.snapshot_items()

    def test_push_while_space_remains(self) -> None:
        self.checked.push("alpha")
        self.checked.push("beta")
        _ = self.checked.size
        _ = self.checked.is_full

    def test_pop_removes_items_in_fifo_order(self) -> None:
        self.checked.push("alpha")
        self.checked.push("beta")
        self.checked.push("gamma")
        self.checked.pop()
        self.checked.pop()
        _ = self.checked.size
        _ = self.checked.is_empty

    def test_push_evicts_oldest_item_at_capacity(self) -> None:
        for index in range(10):
            self.checked.push("item-" + str(index))
        _ = self.checked.is_full
        self.checked.push("overflow")
        _ = self.checked.size
        _ = self.checked.snapshot_items()

    def test_push_after_eviction_keeps_arrival_order(self) -> None:
        for index in range(10):
            self.checked.push("item-" + str(index))
        self.checked.push("overflow")
        self.checked.push("later")
        _ = self.checked.snapshot_items()
        self.checked.pop()
        _ = self.checked.snapshot_items()

    def test_pop_on_empty_buffer_raises(self) -> None:
        with self.assertRaises(BufferEmptyError):
            self.checked.pop()

    def test_clear_removes_all_items(self) -> None:
        self.checked.push("alpha")
        self.checked.push("beta")
        self.checked.clear()
        _ = self.checked.size
        _ = self.checked.is_empty
        _ = self.checked.snapshot_items()

    def test_pop_after_clear_raises(self) -> None:
        self.checked.push("alpha")
        self.checked.clear()
        with self.assertRaises(BufferEmptyError):
            self.checked.pop()

    def test_snapshot_items_is_non_destructive(self) -> None:
        self.checked.push("alpha")
        snapshot = self.checked.snapshot_items()
        snapshot.append("beta")
        _ = self.checked.snapshot_items()
        _ = self.checked.size


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
# LAST_CLEANED: 2026-11-02T23:33:54Z
# LAST_CHANGED: 2026-11-02T23:33:08Z
# CHANGE: Remove duplicate model bookkeeping from RingBufferImplPseudoStateMachine overrides: push/pop/clear no longer mutate self.state.items, so each checked call performs model bookkeeping exactly once (in the inherited interface transition that delegates through ). Overrides now only call_target the SUT and assert contracted returns/postconditions against model state captured before delegation (push evicted-vs-None, pop oldest item, clear void return, snapshot FIFO copy, capacity/size/is_empty/is_full observations). This fixes the reported size drift (size dropping by two) and restores the size/snapshot_items postconditions.
# PRETENSE_COVERAGE_AUDIT: 2026-11-02T23:33:54Z
# PRETENSE_QA_AUDIT: 2026-11-02T23:33:33Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for RingBuffer.

The model tracks a bounded FIFO of items with a fixed default capacity of ten,
mirroring the operational postconditions of ``low/ring_buffer.pyi``:
push appends and evicts the oldest item when saturated, pop removes the oldest
item or raises ``BufferEmptyError`` when empty, clear resets the buffer, and
snapshot_items observes FIFO arrival order without mutating state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

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
from benchmark_1.parts.ring_buffer.lib.ring_buffer import BufferEmptyError, RingBuffer


# ==============================================================================
# 1. Interface Model State & 1:1 Transitions
# ==============================================================================

@dataclass
class RingBufferState:
    """Canonical model state for RingBuffer: fixed capacity plus FIFO items."""

    capacity: int = 10
    items: List[Any] = field(default_factory=list)


class RingBufferStateMachine(StateMachine[RingBufferState]):
    """Pretense state machine modelling every public RingBuffer operation 1:1."""

    def __init__(
        self,
        state: Optional[RingBufferState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or RingBufferState(), singletons=singletons)

    @transition(RingBuffer.push)
    def push(self, item: Any) -> Optional[Any]:
        require(self.state.capacity >= 1)
        require_arg(
            item,
            Domain.type(str),
            preferred=["alpha", "beta", "gamma"],
        )
        was_full: bool = len(self.state.items) >= self.state.capacity
        oldest: Optional[Any] = self.state.items[0] if self.state.items else None
        evicted: Optional[Any] = oldest if was_full else None
        ret: Optional[Any] = self.inner_push(item)
        if was_full:
            self.state.items.pop(0)
        self.state.items.append(item)
        assert self.state.items[-1] == item
        assert len(self.state.items) <= self.state.capacity
        if was_full:
            assert ret == oldest
            assert len(self.state.items) == self.state.capacity
        else:
            assert ret is None
        return ret

    @transition(RingBuffer.pop)
    def pop(self) -> Any:
        if not self.state.items:
            with raises(BufferEmptyError):
                self.inner_pop()
            raise BufferEmptyError
        oldest: Any = self.state.items[0]
        before: int = len(self.state.items)
        ret: Any = self.inner_pop()
        self.state.items.pop(0)
        assert ret == oldest
        assert len(self.state.items) == before - 1
        assert len(self.state.items) <= self.state.capacity
        return ret

    @transition(RingBuffer.clear)
    def clear(self) -> None:
        ret = self.inner_clear()
        self.state.items.clear()
        assert ret is None
        assert len(self.state.items) == 0
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(self) -> List[Any]:
        snapshot: List[Any] = list(self.state.items)
        ret: List[Any] = self.inner_snapshot_items()
        assert ret == snapshot
        assert len(ret) == len(self.state.items)
        assert list(self.state.items) == snapshot
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        ret: int = self.inner_capacity()
        assert ret == self.state.capacity
        assert ret >= 1
        return ret

    @transition(name="size")
    def size(self) -> int:
        ret: int = self.inner_size()
        assert ret == len(self.state.items)
        assert 0 <= ret <= self.state.capacity
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        expected_empty: bool = len(self.state.items) == 0
        ret: bool = self.inner_is_empty()
        assert ret == expected_empty
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        expected_full: bool = len(self.state.items) >= self.state.capacity
        ret: bool = self.inner_is_full()
        assert ret == expected_full
        return ret


proto = RingBufferStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeRingBuffer = synthesize_fake(RingBufferStateMachine)


def make_ring_buffer_fake(
    state: Optional[RingBufferState] = None,
) -> RingBuffer:
    """Synthesizes a fake RingBuffer backed by model state."""
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
# LAST_CLEANED: 2026-11-02T23:33:12Z
# LAST_CHANGED: 2026-11-02T23:33:12Z
# CHANGE: Reorder RingBufferStateMachine.push so all model bookkeeping happens after the pivot: was_full/oldest/evicted are computed non-destructively before the pivot, and the eviction pop plus append occur afterwards. This keeps model pre-state pristine at the pivot so a delegating implementation override observes the true pre-call state (e.g. push to a full buffer correctly expects the oldest item as the evicted return), without changing fake transition semantics.
# --- END AUTOFAB METADATA ---
