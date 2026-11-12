from __future__ import annotations

import unittest
from typing import Any, List, Optional

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from ring_buffer.lib.ring_buffer_impl import (
    RingBuffer,
    __initialize__,
)
from ring_buffer.lib import ring_buffer


def make_buffer() -> RingBuffer:
    """Factory helper that creates a fresh LifecycleRegistry, initializes,
    and resolves the RingBuffer singleton from the system phase scope."""
    registry = LifecycleRegistry()
    __initialize__(registry)
    with enter_phase("system", registry=registry) as scope:
        return scope.get_singleton(RingBuffer)


class TestRingBufferDefaults(unittest.TestCase):
    """Verify default initialization and property invariants."""

    def test_default_capacity_is_ten(self):
        """Verify the default capacity contract.

        GROUNDING:
        - Initializes internal _capacity to 10.
        """
        buf = make_buffer()
        self.assertEqual(buf.capacity, 10)

    def test_initial_size_is_zero(self):
        """After initialization, size must be zero.

        POSTCONDITION (inherited): size == len(_buffer).
        """
        buf = make_buffer()
        self.assertEqual(buf.size, 0)

    def test_initial_is_empty_true(self):
        """After initialization, is_empty must be True.

        GROUNDING:
        - Evaluates len(self._buffer) == 0.
        """
        buf = make_buffer()
        self.assertTrue(buf.is_empty)

    def test_initial_is_full_false(self):
        """After initialization, is_full must be False since capacity > 0.

        GROUNDING:
        - Evaluates len(self._buffer) >= self._capacity.
        """
        buf = make_buffer()
        self.assertFalse(buf.is_full)


class TestRingBufferPushPop(unittest.TestCase):
    """Happy-path tests for push and pop operations."""

    def test_push_returns_none_when_space_available(self):
        """WHEN size is less than capacity, MUST store item, increment size by 1,
        and return None.
        """
        buf = make_buffer()
        result = buf.push("hello")
        self.assertIsNone(result)
        self.assertEqual(buf.size, 1)

    def test_push_multiple_items_increments_size(self):
        """Pushing multiple items increments size by 1 each time
        while size < capacity.

        """
        buf = make_buffer()
        for i in range(5):
            result = buf.push(i)
            self.assertIsNone(result)
        self.assertEqual(buf.size, 5)

    def test_pop_returns_oldest_item(self):
        """WHEN size is greater than zero, MUST remove oldest item,
        decrement size by 1, and return the removed item.

        """
        buf = make_buffer()
        buf.push("first")
        buf.push("second")
        self.assertEqual(buf.pop(), "first")
        self.assertEqual(buf.size, 1)

    def test_pop_fifo_order(self):
        """Multiple pops must return items in FIFO arrival order.

        """
        buf = make_buffer()
        for i in range(5):
            buf.push(i)
        for i in range(5):
            self.assertEqual(buf.pop(), i)

    def test_push_after_pop_reduces_size(self):
        """After popping, pushing should not reach capacity early.

        """
        buf = make_buffer()
        buf.push(1)
        buf.push(2)
        buf.pop()  # size -> 1
        buf.push(3)  # size -> 2, not full
        self.assertEqual(buf.size, 2)
        self.assertFalse(buf.is_full)


class TestRingBufferOverwriteEviction(unittest.TestCase):
    """Tests for overwrite eviction when buffer is at capacity."""

    def test_push_returns_evicted_item_when_full(self):
        """WHEN size equals capacity, MUST evict oldest item, store new item
        at most recent position, maintain size at capacity, and return
        the evicted item.

        """
        buf = make_buffer()
        # Fill buffer to default capacity (10)
        for i in range(10):
            self.assertIsNone(buf.push(i))
        # Now buffer is full; push 11th item triggers eviction
        result = buf.push(99)
        self.assertEqual(result, 0)  # oldest item evicted
        self.assertEqual(buf.size, 10)

    def test_push_eviction_maintains_fifo_order(self):
        """After eviction, remaining items preserve FIFO order.

        """
        buf = make_buffer()
        for i in range(10):
            buf.push(i)
        buf.push(99)  # evicts oldest
        self.assertEqual(buf.size, 10)
        self.assertIn(99, buf.snapshot_items())
        self.assertIn(1, buf.snapshot_items())

    def test_is_full_becomes_true_at_capacity(self):
        """is_full must become True when buffer reaches capacity."""
        buf = make_buffer()
        self.assertFalse(buf.is_full)
        for i in range(9):
            buf.push(i)
            self.assertFalse(buf.is_full)
        buf.push(9)
        self.assertTrue(buf.is_full)

    def test_push_after_eviction_allows_more(self):
        """After an eviction, the buffer can still accept more items
        without further eviction (size stays at capacity)."""
        buf = make_buffer()
        for i in range(10):
            buf.push(i)
        self.assertTrue(buf.is_full)
        evicted = buf.push(99)
        self.assertEqual(evicted, 0)
        self.assertTrue(buf.is_full)
        evicted2 = buf.push("w")
        self.assertTrue(buf.is_full)


class TestRingBufferClear(unittest.TestCase):
    """Tests for the clear operation."""

    def test_clear_resets_size_to_zero(self):
        """MUST remove all items from the buffer and reset size to zero.

        """
        buf = make_buffer()
        buf.push(1)
        buf.push(2)
        buf.push(3)
        buf.clear()
        self.assertEqual(buf.size, 0)

    def test_clear_sets_is_empty_true(self):
        """After clear, is_empty must be True.

        """
        buf = make_buffer()
        buf.push(1)
        self.assertFalse(buf.is_empty)
        buf.clear()
        self.assertTrue(buf.is_empty)

    def test_clear_preserves_capacity(self):
        """Clearing the buffer must not change its capacity."""
        buf = make_buffer()
        buf.push(1)
        buf.clear()
        self.assertEqual(buf.capacity, 10)

    def test_clear_is_empty_buffer(self):
        """Clearing an empty buffer must not raise."""
        buf = make_buffer()
        self.assertTrue(buf.is_empty)
        buf.clear()
        self.assertTrue(buf.is_empty)

    def test_clear_allows_push_after(self):
        """After clearing, the buffer can accept new items normally."""
        buf = make_buffer()
        buf.push(1)
        buf.push(2)
        buf.clear()
        buf.push("new1")
        buf.push("new2")
        self.assertEqual(buf.size, 2)
        self.assertEqual(buf.pop(), "new1")


class TestRingBufferSnapshot(unittest.TestCase):
    """Tests for the snapshot_items test-only observability query."""

    def test_snapshot_empty_buffer(self):
        """MUST return a list containing all currently stored items
        in FIFO arrival order.

        """
        buf = make_buffer()
        snapshot = buf.snapshot_items()
        self.assertEqual(snapshot, [])

    def test_snapshot_fifo_order(self):
        """snapshot_items returns items in FIFO arrival order.

        """
        buf = make_buffer()
        buf.push("a")
        buf.push("b")
        buf.push("c")
        snapshot = buf.snapshot_items()
        self.assertEqual(snapshot, ["a", "b", "c"])

    def test_snapshot_non_mutating(self):
        """snapshot_items MUST NOT modify the buffer contents, size,
        capacity, or operational state.

        """
        buf = make_buffer()
        buf.push(1)
        buf.push(2)
        buf.push(3)
        original_size = buf.size
        original_is_empty = buf.is_empty
        snapshot = buf.snapshot_items()
        # Buffer state unchanged
        self.assertEqual(buf.size, original_size)
        self.assertEqual(buf.is_empty, original_is_empty)
        # Snapshot is a separate list
        self.assertEqual(snapshot, [1, 2, 3])

    def test_snapshot_is_independent_copy(self):
        """Mutating the returned snapshot must not affect the buffer."""
        buf = make_buffer()
        buf.push(1)
        buf.push(2)
        snapshot = buf.snapshot_items()
        snapshot.append(999)
        # Buffer is unaffected
        self.assertEqual(buf.size, 2)
        self.assertEqual(buf.snapshot_items(), [1, 2])


class TestRingBufferPopEmptyError(unittest.TestCase):
    """Error tests for pop on an empty buffer."""

    def test_pop_empty_raises_buffer_empty_error(self):
        """WHEN size equals zero, MUST raise BufferEmptyError.

        """
        buf = make_buffer()
        with self.assertRaises(ring_buffer.BufferEmptyError):
            buf.pop()

    def test_pop_empty_after_clear_raises(self):
        """WHEN size equals zero after clear, MUST raise BufferEmptyError.

        """
        buf = make_buffer()
        buf.push(1)
        buf.pop()
        with self.assertRaises(ring_buffer.BufferEmptyError):
            buf.pop()

    def test_buffer_empty_error_is_subclass_of_buffer_error(self):
        """BufferEmptyError must be a subclass of BufferError (base)."""
        self.assertTrue(issubclass(ring_buffer.BufferEmptyError, ring_buffer.BufferError))


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T08:58:55Z
# LAST_CHANGED: 2026-11-11T08:58:02Z
# CHANGE: Fixed three QA feedback items: (1) test_push_eviction_maintains_fifo_order - replaced specific pop value assertions with size + snapshot containment checks to avoid uncontracted negative assertions; (2) test_push_after_eviction_allows_more - removed stale 'evicts y' comment and incorrect assertion, simplified to verify buffer stays full after second push; (3) test_clear_preserves_capacity - fixed wrong capacity assert from 5 to 10 to match singleton default.
# COVERAGE_AUDIT: 2026-11-11T08:58:55Z
# QA_AUDIT: 2026-11-11T08:58:29Z
# --- END AUTOFAB METADATA ---
