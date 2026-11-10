"""Unit tests for ring_buffer_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Any
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from ring_buffer.lib.ring_buffer_impl import (
    RingBuffer,
    __initialize__,
)
from ring_buffer.lib.ring_buffer import BufferEmptyError


def _make_buffer(buf: RingBuffer, n: int = 5) -> None:
    """Helper that pushes n integer items onto the buffer."""
    for i in range(n):
        buf.push(i)


class RingBufferImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    # -- Lifecycle / initialization --

    def test_registry_initialized(self) -> None:
        """CUJ: Verify that initialization registers singletons into the registry."""
        with enter_phase("system", registry=self.registry) as scope:
            desc = self.registry.find_descriptor(RingBuffer)
            assert desc is not None
            self.assertEqual(desc.phase, "system")

    # -- Property tests: capacity --

    def test_capacity_default_is_10(self) -> None:
        """CUJ: Verify capacity property returns 10 for the default RingBuffer.

        Verifies: RingBuffer initializes with capacity 10.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            self.assertEqual(buf.capacity, 10)

    def test_capacity_is_positive_int(self) -> None:
        """CUJ: Verify capacity is a positive integer and does not change."""
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            buf.push(0)
            self.assertIsInstance(buf.capacity, int)
            self.assertGreater(buf.capacity, 0)
            self.assertEqual(buf.capacity, 10)

    # -- Property tests: size --

    def test_size_zero_when_empty(self) -> None:
        """CUJ: Verify size property returns 0 when buffer is empty.

        Verifies: size equals the number of items (0) initially.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            self.assertEqual(buf.size, 0)

    def test_size_increases_on_push(self) -> None:
        """CUJ: Verify size increments by 1 when pushing into empty buffer.

        Verifies: push adds one item to the buffer, increasing size by 1.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            buf.push("a")
            self.assertEqual(buf.size, 1)
            buf.push("b")
            self.assertEqual(buf.size, 2)

    def test_size_capped_at_capacity(self) -> None:
        """CUJ: Verify size never exceeds capacity when buffer is full.

        Verifies: push at capacity evicts oldest items while maintaining size at capacity.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            for i in range(15):
                buf.push(i)
            self.assertEqual(buf.size, 10)
            self.assertEqual(buf.size, buf.capacity)

    # -- Property tests: is_empty --

    def test_is_empty_true_initially(self) -> None:
        """CUJ: Verify is_empty is True when buffer is empty.

        Verifies: is_empty evaluates to true when buffer is empty.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            self.assertTrue(buf.is_empty)

    def test_is_empty_false_after_push(self) -> None:
        """CUJ: Verify is_empty is False after pushing items.

        Verifies: is_empty is False when buffer has items.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            buf.push("x")
            self.assertFalse(buf.is_empty)

    def test_is_empty_true_after_clear(self) -> None:
        """CUJ: Verify is_empty is True after clearing the buffer.

        Verifies: clear removes all items, restoring empty state.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            _make_buffer(buf, 5)
            self.assertFalse(buf.is_empty)
            buf.clear()
            self.assertTrue(buf.is_empty)

    # -- Property tests: is_full --

    def test_is_full_false_initially(self) -> None:
        """CUJ: Verify is_full is False when buffer is empty.

        Verifies: is_full evaluates to false when size is below capacity.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            self.assertFalse(buf.is_full)

    def test_is_full_true_after_fill(self) -> None:
        """CUJ: Verify is_full is True when buffer reaches capacity.

        Verifies: is_full evaluates to true when size reaches capacity.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            for i in range(10):
                buf.push(i)
            self.assertTrue(buf.is_full)
            self.assertEqual(buf.size, buf.capacity)

    def test_is_full_false_after_pop(self) -> None:
        """CUJ: Verify is_full becomes False after popping from a full buffer.

        Verifies: popping decreases size below capacity, so is_full is False.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            for i in range(10):
                buf.push(i)
            self.assertTrue(buf.is_full)
            buf.pop()
            self.assertFalse(buf.is_full)

    # -- Operation: push (happy-path, available capacity) --

    def test_push_returns_none_when_space_available(self) -> None:
        """CUJ: Verify push returns None when buffer has available capacity.

        Verifies: push stores item in buffer and returns None when space is available.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            result = buf.push("item1")
            self.assertIsNone(result)
            self.assertEqual(buf.size, 1)

    def test_push_stores_item_in_buffer(self) -> None:
        """CUJ: Verify push stores items retrievable via pop or snapshot.

        Verifies: push correctly places items into the buffer.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            buf.push("first")
            buf.push("second")
            items = buf.snapshot_items()
            self.assertEqual(items, ["first", "second"])

    # -- Operation: push (overwrite eviction at capacity) --

    def test_push_returns_evicted_item_when_full(self) -> None:
        """CUJ: Verify push returns the evicted oldest item when buffer is full.

        Verifies: push evicts the oldest item and returns it when buffer is at capacity.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            for i in range(10):
                buf.push(i)
            self.assertTrue(buf.is_full)
            evicted = buf.push(100)
            self.assertEqual(evicted, 0)
            self.assertEqual(buf.size, 10)

    def test_push_overwrite_eviction_fifo_order_preserved(self) -> None:
        """CUJ: Verify push overwrite eviction preserves FIFO order.

        Verifies: new items are placed after existing ones, maintaining FIFO order.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            for i in range(10):
                buf.push(i)
            buf.push(100)
            buf.push(101)
            items = buf.snapshot_items()
            self.assertEqual(items, [2, 3, 4, 5, 6, 7, 8, 9, 100, 101])

    def test_push_overwrite_eviction_size_maintained_at_capacity(self) -> None:
        """CUJ: Verify push overwrite eviction keeps size equal to capacity.

        Verifies: buffer size stays fixed at capacity after eviction.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            for i in range(10):
                buf.push(i)
            original_capacity = buf.capacity
            for _ in range(5):
                buf.push("overflow")
            self.assertEqual(buf.size, original_capacity)

    # -- Operation: pop (happy-path, non-empty) --

    def test_pop_returns_oldest_item(self) -> None:
        """CUJ: Verify pop returns the oldest (first pushed) item.

        Verifies: size decrements by 1 after pop on non-empty buffer.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            _make_buffer(buf, 3)
            oldest = buf.pop()
            self.assertEqual(oldest, 0)
            self.assertEqual(buf.size, 2)

    def test_pop_decrements_size(self) -> None:
        """CUJ: Verify pop decrements size by 1 when buffer is non-empty.

        Verifies: size decrements by 1 after pop on non-empty buffer.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            buf.push("a")
            buf.push("b")
            self.assertEqual(buf.size, 2)
            buf.pop()
            self.assertEqual(buf.size, 1)
            buf.pop()
            self.assertEqual(buf.size, 0)

    def test_pop_fifo_sequence(self) -> None:
        """CUJ: Verify pop returns items in FIFO order across multiple calls.

        Verifies: pop retrieves oldest items sequentially.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            _make_buffer(buf, 5)
            self.assertEqual(buf.pop(), 0)
            self.assertEqual(buf.pop(), 1)
            self.assertEqual(buf.pop(), 2)
            self.assertEqual(buf.size, 2)

    # -- Operation: pop (error, empty buffer) --

    def test_pop_raises_buffer_empty_error_when_empty(self) -> None:
        """CUJ: Verify pop raises BufferEmptyError when buffer is empty.

        Verifies: calling pop on empty buffer raises BufferEmptyError.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            with self.assertRaises(BufferEmptyError):
                buf.pop()

    def test_pop_raises_buffer_empty_error_after_clear(self) -> None:
        """CUJ: Verify pop raises BufferEmptyError after clearing.

        Verifies: clear resets size to zero, pop precondition checked.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            _make_buffer(buf, 3)
            buf.clear()
            with self.assertRaises(BufferEmptyError):
                buf.pop()

    # -- Operation: clear --

    def test_clear_resets_size_to_zero(self) -> None:
        """CUJ: Verify clear removes all items and resets size to zero.

        Verifies: clear empties the buffer and sets size to 0.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            _make_buffer(buf, 5)
            self.assertEqual(buf.size, 5)
            buf.clear()
            self.assertEqual(buf.size, 0)
            self.assertTrue(buf.is_empty)

    def test_clear_resets_full_buffer(self) -> None:
        """CUJ: Verify clear empties a full buffer.

        Verifies: clear removes all items regardless of state.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            for i in range(10):
                buf.push(i)
            self.assertTrue(buf.is_full)
            buf.clear()
            self.assertFalse(buf.is_full)
            self.assertTrue(buf.is_empty)
            self.assertEqual(buf.size, 0)

    def test_clear_is_idempotent(self) -> None:
        """CUJ: Verify calling clear on an empty buffer does not error.

        Verifies: clear is safe to call even when already empty.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            buf.clear()
            buf.clear()
            self.assertEqual(buf.size, 0)
            self.assertTrue(buf.is_empty)

    # -- Operation: snapshot_items (happy-path) --

    def test_snapshot_items_empty_buffer(self) -> None:
        """CUJ: Verify snapshot_items returns empty list for empty buffer.

        Verifies: snapshot returns empty list when no items stored.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            snapshot = buf.snapshot_items()
            self.assertEqual(snapshot, [])
            self.assertIsInstance(snapshot, list)

    def test_snapshot_items_fifo_order(self) -> None:
        """CUJ: Verify snapshot_items returns items in FIFO arrival order.

        Verifies: snapshot returns items ordered from oldest to newest.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            _make_buffer(buf, 5)
            snapshot = buf.snapshot_items()
            self.assertEqual(snapshot, [0, 1, 2, 3, 4])

    def test_snapshot_items_returns_shallow_copy(self) -> None:
        """CUJ: Verify snapshot_items returns a copy, not a reference.

        Verifies: snapshot does not affect buffer state when called.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            _make_buffer(buf, 3)
            snapshot = buf.snapshot_items()
            original_len = len(snapshot)
            buf.push(99)
            self.assertEqual(len(snapshot), original_len)
            self.assertEqual(buf.size, 4)

    # -- Operation: snapshot_items (non-mutating) --

    def test_snapshot_items_does_not_mutate_state(self) -> None:
        """CUJ: Verify snapshot_items does not change buffer state.

        Verifies: snapshot does not modify buffer contents, size, capacity, or state.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            _make_buffer(buf, 3)
            original_size = buf.size
            original_is_empty = buf.is_empty
            buf.snapshot_items()
            self.assertEqual(buf.size, original_size)
            self.assertEqual(buf.is_empty, original_is_empty)

    def test_snapshot_items_after_pop_preserves_remaining(self) -> None:
        """CUJ: Verify snapshot_items after pop reflects current buffer contents.

        Verifies: snapshot returns a live view of current items.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            _make_buffer(buf, 3)
            buf.pop()
            snapshot = buf.snapshot_items()
            self.assertEqual(snapshot, [1, 2])
            self.assertEqual(buf.size, 2)

    # -- Integration: push and pop round-trip --

    def test_push_pop_roundtrip_under_capacity(self) -> None:
        """CUJ: Verify push/pop round-trip when buffer never exceeds capacity.

        Verifies: push and pop operations work correctly end-to-end.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            buf.push("a")
            buf.push("b")
            self.assertEqual(buf.pop(), "a")
            self.assertEqual(buf.pop(), "b")
            self.assertTrue(buf.is_empty)

    def test_push_pop_cycle_with_partial_eviction(self) -> None:
        """CUJ: Verify push/pop cycle with full push then partial pop.

        Verifies: FIFO order and eviction postconditions coherently.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            for i in range(10):
                buf.push(i)
            self.assertEqual(buf.pop(), 0)
            self.assertEqual(buf.pop(), 1)
            evicted = buf.push(100)
            self.assertIsNone(evicted)
            items = buf.snapshot_items()
            self.assertEqual(items, [2, 3, 4, 5, 6, 7, 8, 9, 100])
            self.assertEqual(buf.size, 9)

    # -- Integration: mixed operations --

    def test_mixed_push_pop_clear_operations(self) -> None:
        """CUJ: Verify a realistic sequence of mixed buffer operations.

        Verifies: push, pop, clear, snapshot, and property invariants hold throughout.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            buf.push(1)
            buf.push(2)
            self.assertEqual(buf.size, 2)
            self.assertFalse(buf.is_empty)
            self.assertFalse(buf.is_full)

            buf.clear()
            self.assertEqual(buf.size, 0)
            self.assertTrue(buf.is_empty)

            for i in range(10):
                buf.push(i)
            self.assertTrue(buf.is_full)

            buf.pop()
            self.assertFalse(buf.is_full)
            self.assertEqual(buf.size, 9)

            snapshot = buf.snapshot_items()
            self.assertEqual(snapshot, [1, 2, 3, 4, 5, 6, 7, 8, 9])

    def test_capacity_invariant_preserved_after_operations(self) -> None:
        """CUJ: Verify capacity property never changes across operations.

        Verifies: INVARIANT — capacity is fixed at initialization value.
        """
        with enter_phase("system", registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            original = buf.capacity
            _make_buffer(buf, 10)
            buf.pop()
            buf.clear()
            buf.push("x")
            self.assertEqual(buf.capacity, original)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T05:44:15Z
# LAST_CHANGED: 2026-11-10T05:43:31Z
# CHANGE: Fixed incorrect assertion in test_snapshot_items_returns_shallow_copy: buf.size was asserted as 6 but actual buffer size after _make_buffer(buf, 3) + buf.push(99) is 4. Changed assertion to self.assertEqual(buf.size, 4) to match actual behavior.
# COVERAGE_AUDIT: 2026-11-10T05:44:15Z
# QA_AUDIT: 2026-11-10T05:43:53Z
# --- END AUTOFAB METADATA ---
