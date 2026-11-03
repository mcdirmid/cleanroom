# === File: ring_buffer_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for RingBuffer.

Verifies the concrete ``RingBuffer`` realization from
``benchmark_3/parts/ring_buffer/lib/ring_buffer_impl.py`` against the interface
model in ``benchmark_3/parts/ring_buffer/pretense/ring_buffer_pretense.py``.
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
from benchmark_3.parts.ring_buffer.pretense.ring_buffer_pretense import (
    RingBufferState,
    RingBufferStateMachine,
)
from benchmark_3.parts.ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================


class RingBufferImplPseudoStateMachine(RingBufferStateMachine):
    """Implementation pseudo-state machine for RingBuffer.

    Overrides observe the real SUT; model state updates remain owned by the
    inherited interface transitions that delegate here through the AST pivot.
    """

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
    ) -> None:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.clear())
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(
        self,
    ) -> List[Any]:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(target.snapshot_items())
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "capacity"))
        return ret

    @transition(name="size")
    def size(self) -> int:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "size"))
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        target: RingBuffer = sut(RingBuffer)
        ret = call_target(getattr(target, "is_empty"))
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
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

    def test_empty_buffer_observers(self) -> None:
        self.checked.capacity
        self.checked.size
        self.checked.is_empty
        self.checked.is_full
        self.checked.snapshot_items()

    def test_push_appends_in_fifo_order(self) -> None:
        self.checked.push(1)
        self.checked.push(2)
        self.checked.push(3)
        self.checked.size
        self.checked.is_empty
        self.checked.is_full
        self.checked.snapshot_items()

    def test_push_evicts_oldest_when_saturated(self) -> None:
        for index in range(10):
            self.checked.push(index)
        self.checked.is_full
        self.checked.push(10)
        self.checked.size
        self.checked.snapshot_items()

    def test_pop_removes_oldest_item(self) -> None:
        self.checked.push("alpha")
        self.checked.push("beta")
        self.checked.pop()
        self.checked.size
        self.checked.snapshot_items()
        self.checked.pop()
        self.checked.is_empty
        self.checked.snapshot_items()

    def test_clear_resets_buffer(self) -> None:
        self.checked.push(1)
        self.checked.push(2)
        self.checked.clear()
        self.checked.is_empty
        self.checked.size
        self.checked.snapshot_items()


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
# LAST_CLEANED: 2026-11-03T04:50:52Z
# LAST_CHANGED: 2026-11-03T04:50:52Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 97830e72fd0a
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T04:50:52Z
# PRETENSE_QA_AUDIT: 2026-11-03T04:50:52Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for RingBuffer.

Models the bounded circular FIFO contract declared in
``benchmark_3/parts/ring_buffer/low/ring_buffer.pyi``: overwrite eviction on
saturation, oldest-first removal, reset on clear, and non-destructive snapshots.
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
from benchmark_3.parts.ring_buffer.lib.ring_buffer import RingBuffer


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions live naturally inside the single
# transition body (multi-transition splitting is prohibited).


@dataclass
class RingBufferState:
    """Canonical model state for RingBuffer operations."""

    items: List[Any] = field(default_factory=list)
    capacity: int = 10


class RingBufferStateMachine(StateMachine[RingBufferState]):
    """Model of the bounded circular first-in first-out buffer contract."""

    def __init__(
        self,
        state: Optional[RingBufferState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or RingBufferState(), singletons=singletons)

    @transition(RingBuffer.push)
    def push(self, item: Any) -> Optional[Any]:
        require_arg(item, Domain.any())
        # POSTCONDITIONS: WHEN size equals capacity, MUST evict oldest, store new item,
        # maintain size at capacity, and return the evicted item.
        if len(self.state.items) == self.state.capacity:
            evicted = self.state.items.pop(0)
            self.state.items.append(item)
            ret: Optional[Any] = make_return_value(evicted)
            assert ret == evicted
            return ret
        # POSTCONDITIONS: WHEN size is less than capacity, MUST store item,
        # increment size by 1, and return None.
        self.state.items.append(item)
        ret = make_return_value(None)
        assert ret is None
        return ret

    @transition(RingBuffer.pop)
    def pop(self) -> Any:
        # WHEN size equals zero, MUST raise BufferEmptyError; that precondition is
        # gated so conforming generated calls never violate it.
        require(len(self.state.items) > 0)
        # POSTCONDITIONS: WHEN size is greater than zero, MUST remove oldest item,
        # decrement size by 1, and return the removed item.
        removed = self.state.items.pop(0)
        ret: Any = make_return_value(removed)
        assert ret == removed
        return ret

    @transition(RingBuffer.clear)
    def clear(self) -> None:
        # POSTCONDITIONS: MUST remove all items from the buffer and reset size to zero.
        self.state.items.clear()
        ret = make_return_value()
        assert not self.state.items
        assert ret is None
        return ret

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(self) -> List[Any]:
        # POSTCONDITIONS: MUST return all stored items in FIFO arrival order without
        # modifying the buffer contents, size, capacity, or operational state.
        ret: List[Any] = make_return_value(list(self.state.items))
        assert ret == list(self.state.items)
        assert len(self.state.items) <= self.state.capacity
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        ret: int = make_return_value(self.state.capacity)
        assert ret == self.state.capacity
        return ret

    @transition(name="size")
    def size(self) -> int:
        ret: int = make_return_value(len(self.state.items))
        assert ret == len(self.state.items)
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        ret: bool = make_return_value(len(self.state.items) == 0)
        assert ret == (len(self.state.items) == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        ret: bool = make_return_value(len(self.state.items) >= self.state.capacity)
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret


proto = RingBufferStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeRingBuffer = synthesize_fake(RingBufferStateMachine)


def make_ring_buffer_fake(
    state: Optional[RingBufferState] = None,
) -> RingBuffer:
    """Synthesizes a fake instance for RingBuffer."""
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
# LAST_CLEANED: 2026-11-03T04:50:52Z
# LAST_CHANGED: 2026-11-03T04:50:52Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: fa2bfec2f38d
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T04:50:52Z
# PRETENSE_QA_AUDIT: 2026-11-03T04:50:52Z
# --- END AUTOFAB METADATA ---
