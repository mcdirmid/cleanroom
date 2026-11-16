# === File: ring_buffer_impl_pretense.py ===
from __future__ import annotations

from typing import Any, List, Optional

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, LifecycleTestCase, enter_phase, get_singleton, system

from ring_buffer_gemini_flash_2.parts.ring_buffer.lib.ring_buffer import (
    BufferEmptyError,
    RingBuffer,
)
from ring_buffer_gemini_flash_2.parts.ring_buffer.lib.ring_buffer_impl import (
    RingBuffer as RingBufferImpl,
)
from ring_buffer_gemini_flash_2.parts.ring_buffer.pretense.ring_buffer_pretense import (
    RingBufferStateMachine,
)


class RingBufferImplStateMachine(RingBufferStateMachine):
    """Implementation state machine binding for RingBuffer."""

    def inner_capacity(self) -> int:
        return sut(RingBuffer).capacity

    def inner_size(self) -> int:
        return sut(RingBuffer).size

    def inner_is_empty(self) -> bool:
        return sut(RingBuffer).is_empty

    def inner_is_full(self) -> bool:
        return sut(RingBuffer).is_full

    def inner_push(self, item: Any) -> Optional[Any]:
        return sut(RingBuffer).push(item)

    def inner_pop(self) -> Any:
        return sut(RingBuffer).pop()

    def inner_clear(self) -> None:
        sut(RingBuffer).clear()

    def inner_snapshot_items(self) -> List[Any]:
        return sut(RingBuffer).snapshot_items()


def make_sut() -> RingBuffer:
    """Instantiate and initialize the RingBuffer system singleton."""
    registry = LifecycleRegistry()
    registry.register_singleton(RingBufferImpl)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(RingBuffer)


RingBufferImplFuzzTest = compile_hypothesis_test_case(
    RingBufferImplStateMachine,
    sut_factory=make_sut,
    name="RingBufferImplFuzzTest",
)


class TestRingBufferReal(LifecycleTestCase):
    """Scenario tests for real RingBuffer implementation."""

    target = RingBufferImpl

    def setUp(self) -> None:
        super().setUp()
        self.sm = RingBufferImplStateMachine(singletons={RingBuffer: self.sut})
        self.checked = self.sm.as_checked(RingBuffer, self.sut)

    def test_initial_state(self) -> None:
        """Verify initial ring buffer state."""
        self.assertEqual(self.checked.capacity, 10)
        self.assertEqual(self.checked.size, 0)
        self.assertTrue(self.checked.is_empty)
        self.assertFalse(self.checked.is_full)
        self.assertEqual(self.checked.snapshot_items(), [])

    def test_push_and_pop(self) -> None:
        """Verify push, snapshot, and pop behavior."""
        res = self.checked.push("item_1")
        self.assertIsNone(res)
        self.assertEqual(self.checked.size, 1)
        self.assertFalse(self.checked.is_empty)
        self.assertEqual(self.checked.snapshot_items(), ["item_1"])
        popped = self.checked.pop()
        self.assertEqual(popped, "item_1")
        self.assertTrue(self.checked.is_empty)

    def test_overwrite_eviction(self) -> None:
        """Verify overwrite eviction on saturation."""
        for i in range(10):
            self.checked.push(f"val_{i}")
        self.assertTrue(self.checked.is_full)
        evicted = self.checked.push("val_10")
        self.assertEqual(evicted, "val_0")
        self.assertEqual(self.checked.size, 10)

    def test_clear(self) -> None:
        """Verify clearing ring buffer."""
        self.checked.push("val_x")
        self.checked.clear()
        self.assertTrue(self.checked.is_empty)
        self.assertEqual(self.checked.size, 0)

    def test_pop_empty_violating(self) -> None:
        """Verify BufferEmptyError when popping from empty buffer."""
        self.checked.violating(BufferEmptyError).pop()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-16T03:13:12Z
# LAST_CHANGED: 2026-11-16T03:12:02Z
# CHANGES:
# - [2026-11-16T03:12:02Z] [kind:new] [Lines: 3, 5, 9-18, 21-46, 49-55, 58-112] [Scope: RingBufferImplStateMachine,RingBufferImplFuzzTest,TestRingBufferReal] Delta: Implement RingBufferImplStateMachine, make_sut, RingBufferImplFuzzTest, and TestRingBufferReal | Why: Initial pretense implementation binding and verification test case
# PRETENSE_COVERAGE_AUDIT: 2026-11-16T03:13:12Z
# PRETENSE_QA_AUDIT: 2026-11-16T03:12:38Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional
import unittest

from pretense import (
    StateMachine,
    require,
    require_arg,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from ring_buffer_gemini_flash_2.parts.ring_buffer.lib.ring_buffer import (
    BufferEmptyError,
    RingBuffer,
)


class RingBufferStateMachine(StateMachine[Any]):
    """Stateless behavioral contract for RingBuffer."""

    @transition(name="capacity")
    def capacity(self) -> int:
        """Maximum number of items permitted in the circular buffer."""
        ret = self.inner_capacity()
        assert ret > 0
        return ret

    @transition(name="size")
    def size(self) -> int:
        """Current number of items stored in the circular buffer."""
        ret = self.inner_size()
        assert ret >= 0
        assert ret <= self.inner_capacity()
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        """Indicates whether the circular buffer contains zero items."""
        ret = self.inner_is_empty()
        assert ret == (self.inner_size() == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        """Indicates whether the circular buffer has reached its capacity limit."""
        ret = self.inner_is_full()
        assert ret == (self.inner_size() >= self.inner_capacity())
        return ret

    @transition(RingBuffer.push)
    def push(self, item: Any) -> Optional[Any]:
        """Appends an item to the circular buffer with overwrite eviction on saturation."""
        require_arg(item, object)
        pre_full = self.inner_is_full()
        pre_size = self.inner_size()
        pre_items = list(self.inner_snapshot_items())
        ret = self.inner_push(item)
        if pre_full:
            assert ret == pre_items[0]
            assert self.inner_size() == len(pre_items)
            assert self.inner_snapshot_items() == pre_items[1:] + [item]
        else:
            assert ret is None
            assert self.inner_size() == pre_size + 1
            assert self.inner_snapshot_items() == pre_items + [item]
        return ret

    @transition(RingBuffer.pop)
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer."""
        require(not self.inner_is_empty(), error=BufferEmptyError)
        pre_size = self.inner_size()
        pre_items = list(self.inner_snapshot_items())
        ret = self.inner_pop()
        assert ret == pre_items[0]
        assert self.inner_size() == pre_size - 1
        assert self.inner_snapshot_items() == pre_items[1:]
        return ret

    @transition(RingBuffer.clear)
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero."""
        self.inner_clear()
        assert self.inner_size() == 0
        assert self.inner_is_empty()
        assert self.inner_snapshot_items() == []

    @transition(RingBuffer.snapshot_items)
    def snapshot_items(self) -> List[Any]:
        """Returns non-destructive snapshot of active items in circular FIFO arrival order."""
        pre_size = self.inner_size()
        ret = self.inner_snapshot_items()
        assert len(ret) == pre_size
        assert self.inner_size() == pre_size
        return ret

    def inner_capacity(self) -> int: ...
    def inner_size(self) -> int: ...
    def inner_is_empty(self) -> bool: ...
    def inner_is_full(self) -> bool: ...
    def inner_push(self, item: Any) -> Optional[Any]: ...
    def inner_pop(self) -> Any: ...
    def inner_clear(self) -> None: ...
    def inner_snapshot_items(self) -> List[Any]: ...


@dataclass
class RingBufferState:
    """State model for RingBufferFakeStateMachine."""

    capacity: int = 10
    items: list[Any] = field(default_factory=list)


class RingBufferFakeStateMachine(RingBufferStateMachine):
    """Stateful in-memory fake for RingBuffer."""

    def __init__(
        self,
        state: Optional[RingBufferState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> RingBufferState:
        return RingBufferState()

    @transition.seeding()
    def seed_empty(self) -> None:
        """Seed empty buffer state."""
        self.state.items = []

    @transition.seeding()
    def seed_full(self) -> None:
        """Seed full buffer state."""
        self.state.items = [f"item_{i}" for i in range(self.state.capacity)]

    @transition.seeding()
    def seed_partial(self) -> None:
        """Seed partial buffer state."""
        self.state.items = ["seed_a", "seed_b"]

    def inner_capacity(self) -> int:
        return self.state.capacity

    def inner_size(self) -> int:
        return len(self.state.items)

    def inner_is_empty(self) -> bool:
        return len(self.state.items) == 0

    def inner_is_full(self) -> bool:
        return len(self.state.items) >= self.state.capacity

    def inner_push(self, item: Any) -> Optional[Any]:
        if len(self.state.items) >= self.state.capacity:
            evicted = self.state.items.pop(0)
            self.state.items.append(item)
            return evicted
        self.state.items.append(item)
        return None

    def inner_pop(self) -> Any:
        return self.state.items.pop(0)

    def inner_clear(self) -> None:
        self.state.items.clear()

    def inner_snapshot_items(self) -> List[Any]:
        return list(self.state.items)


FakeRingBuffer = synthesize_fake(RingBufferFakeStateMachine)


def make_ring_buffer_fake(state: Optional[RingBufferState] = None) -> RingBuffer:
    """Create a synthesized fake RingBuffer instance."""
    return FakeRingBuffer(state=state or RingBufferFakeStateMachine().make_initial_state())


FakeRingBufferFuzzTest = compile_hypothesis_test_case(
    RingBufferFakeStateMachine,
    name="FakeRingBufferFuzzTest",
)


class TestRingBufferFake(unittest.TestCase):
    """Fixed fake tests for RingBuffer."""

    def setUp(self) -> None:
        self.fake: RingBuffer = make_ring_buffer_fake()

    def test_basic_flow(self) -> None:
        """Exercise basic flow through fake instance."""
        self.assertEqual(self.fake.capacity, 10)
        self.assertEqual(self.fake.size, 0)
        self.assertTrue(self.fake.is_empty)
        self.assertFalse(self.fake.is_full)
        self.assertIsNone(self.fake.push("first"))
        self.assertEqual(self.fake.size, 1)
        self.assertFalse(self.fake.is_empty)
        self.assertEqual(self.fake.snapshot_items(), ["first"])
        self.assertEqual(self.fake.pop(), "first")
        self.assertTrue(self.fake.is_empty)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-16T03:11:42Z
# LAST_CHANGED: 2026-11-16T03:11:42Z
# CHANGES:
# - [2026-11-16T03:11:42Z] [kind:new] [Lines: 4, 15-208, del@9, del@11, del@12] [Scope: RingBufferStateMachine] Delta: Implement RingBufferStateMachine and RingBufferFakeStateMachine | Why: Initial pretense interface realization
# --- END AUTOFAB METADATA ---
