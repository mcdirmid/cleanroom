from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleTestCase
from ring_buffer.lib.ring_buffer import BufferEmptyError
from ring_buffer.lib.ring_buffer_impl import RingBuffer


class RingBufferImplTest(LifecycleTestCase):
    """Unit tests for bounded circular ring buffer implementation."""

    target = RingBuffer
    sut: RingBuffer

    def test_initial_state(self) -> None:
        """Verify initial buffer state has default capacity, zero size, is empty, and is not full."""
        self.assertEqual(self.sut.capacity, 10)
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), [])

    def test_push_with_available_capacity(self) -> None:
        """Verify pushing when size is less than capacity stores the item, increments size, and returns None."""
        result = self.sut.push("item_1")
        self.assertIsNone(result)
        self.assertEqual(self.sut.size, 1)
        self.assertFalse(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), ["item_1"])

    def test_push_multiple_items_fifo_order(self) -> None:
        """Verify pushing multiple items preserves FIFO arrival order in snapshots and size increments."""
        for i in range(5):
            res = self.sut.push(f"val_{i}")
            self.assertIsNone(res)
        self.assertEqual(self.sut.size, 5)
        self.assertFalse(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), [f"val_{i}" for i in range(5)])

    def test_push_until_full(self) -> None:
        """Verify filling buffer to capacity transitions is_full to True."""
        for i in range(self.sut.capacity):
            res = self.sut.push(i)
            self.assertIsNone(res)
        self.assertEqual(self.sut.size, self.sut.capacity)
        self.assertTrue(self.sut.is_full)
        self.assertFalse(self.sut.is_empty)

    def test_push_overwrite_eviction_when_full(self) -> None:
        """Verify pushing when buffer is full evicts the oldest item, stores the new item, and returns the evicted item."""
        for i in range(10):
            self.sut.push(i)
        self.assertTrue(self.sut.is_full)

        evicted = self.sut.push(10)
        self.assertEqual(evicted, 0)
        self.assertEqual(self.sut.size, 10)
        self.assertTrue(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), list(range(1, 11)))

        evicted_2 = self.sut.push(11)
        self.assertEqual(evicted_2, 1)
        self.assertEqual(self.sut.size, 10)
        self.assertEqual(self.sut.snapshot_items(), list(range(2, 12)))

    def test_pop_empty_buffer_raises_error(self) -> None:
        """Verify popping from an empty buffer raises BufferEmptyError."""
        self.assertTrue(self.sut.is_empty)
        with self.assertRaises(BufferEmptyError):
            self.sut.pop()

    def test_pop_non_empty_buffer(self) -> None:
        """Verify popping removes and returns the oldest item and decrements size."""
        self.sut.push("alpha")
        self.sut.push("beta")
        self.assertEqual(self.sut.size, 2)

        popped = self.sut.pop()
        self.assertEqual(popped, "alpha")
        self.assertEqual(self.sut.size, 1)
        self.assertEqual(self.sut.snapshot_items(), ["beta"])

    def test_pop_all_items_until_empty(self) -> None:
        """Verify popping all items retrieves them in FIFO order and leaves the buffer empty."""
        items = ["first", "second", "third"]
        for item in items:
            self.sut.push(item)

        results: list[str] = []
        while not self.sut.is_empty:
            results.append(self.sut.pop())

        self.assertEqual(results, items)
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        with self.assertRaises(BufferEmptyError):
            self.sut.pop()

    def test_clear_resets_buffer_and_size(self) -> None:
        """Verify clearing removes all items and resets size to zero."""
        for i in range(5):
            self.sut.push(i)
        self.assertEqual(self.sut.size, 5)

        self.sut.clear()
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), [])
        with self.assertRaises(BufferEmptyError):
            self.sut.pop()

    def test_clear_empty_buffer(self) -> None:
        """Verify clearing an already empty buffer maintains empty state."""
        self.sut.clear()
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        self.assertEqual(self.sut.snapshot_items(), [])

    def test_snapshot_items_fifo_order(self) -> None:
        """Verify snapshot returns items in FIFO order from oldest to newest."""
        self.sut.push("a")
        self.sut.push("b")
        self.sut.push("c")
        self.assertEqual(self.sut.snapshot_items(), ["a", "b", "c"])

    def test_snapshot_items_non_mutating(self) -> None:
        """Verify snapshot does not modify buffer contents, size, capacity, or operational state."""
        self.sut.push("x")
        self.sut.push("y")
        snapshot_1 = self.sut.snapshot_items()
        snapshot_1.append("mutated")
        self.assertEqual(self.sut.size, 2)
        self.assertEqual(self.sut.snapshot_items(), ["x", "y"])

    def test_overwrite_eviction_followed_by_pop(self) -> None:
        """Verify popping after overwrite evictions returns the remaining items in correct chronological order."""
        for i in range(12):
            self.sut.push(i)
        self.assertEqual(self.sut.size, 10)
        self.assertEqual(self.sut.pop(), 2)
        self.assertEqual(self.sut.pop(), 3)
        self.assertEqual(self.sut.size, 8)
        self.assertEqual(self.sut.snapshot_items(), list(range(4, 12)))


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T06:53:28Z
# LAST_CHANGED: 2026-11-12T06:51:54Z
# CHANGE: Implement unit tests for RingBuffer
# COVERAGE_AUDIT: 2026-11-12T06:53:28Z
# QA_AUDIT: 2026-11-12T06:52:56Z
# --- END AUTOFAB METADATA ---
