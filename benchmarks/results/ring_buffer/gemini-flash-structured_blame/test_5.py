from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleTestCase
from ring_buffer.lib.ring_buffer import BufferEmptyError, BufferError
from ring_buffer.lib.ring_buffer_impl import RingBuffer as RingBufferTarget


class RingBufferImplTest(LifecycleTestCase):
    """Unit tests for bounded circular ring buffer implementation."""

    target = RingBufferTarget

    def test_initial_state(self) -> None:
        """Verify initial ring buffer state is empty with default capacity."""
        self.assertEqual(self.sut.capacity, 10)
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), [])

    def test_push_within_capacity_stores_item_and_increments_size(self) -> None:
        """Verify pushing an item when space is available returns None and increments size."""
        result = self.sut.push("item_1")
        self.assertIsNone(result)
        self.assertEqual(self.sut.size, 1)
        self.assertFalse(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), ["item_1"])

    def test_push_multiple_items_within_capacity(self) -> None:
        """Verify pushing multiple items retains FIFO order and updates size."""
        for i in range(5):
            evicted = self.sut.push(f"val_{i}")
            self.assertIsNone(evicted)
            self.assertEqual(self.sut.size, i + 1)
        self.assertFalse(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), ["val_0", "val_1", "val_2", "val_3", "val_4"])

    def test_push_to_exact_capacity_marks_buffer_full(self) -> None:
        """Verify buffer transitions to full state when capacity items are pushed."""
        for i in range(10):
            evicted = self.sut.push(i)
            self.assertIsNone(evicted)
        self.assertEqual(self.sut.size, 10)
        self.assertFalse(self.sut.is_empty)
        self.assertTrue(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), list(range(10)))

    def test_push_when_full_evicts_oldest_item_and_maintains_capacity(self) -> None:
        """Verify pushing to a saturated buffer evicts the oldest item and returns it."""
        for i in range(10):
            self.sut.push(i)
        evicted = self.sut.push(10)
        self.assertEqual(evicted, 0)
        self.assertEqual(self.sut.size, 10)
        self.assertTrue(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

        second_evicted = self.sut.push(11)
        self.assertEqual(second_evicted, 1)
        self.assertEqual(self.sut.size, 10)
        self.assertEqual(self.sut.snapshot_items(), [2, 3, 4, 5, 6, 7, 8, 9, 10, 11])

    def test_push_and_evict_none_value(self) -> None:
        """Verify buffer can store None values and correctly evicts None when full."""
        evicted_initial = self.sut.push(None)
        self.assertIsNone(evicted_initial)
        self.assertEqual(self.sut.size, 1)
        for i in range(1, 10):
            self.sut.push(i)
        self.assertTrue(self.sut.is_full)
        evicted_none = self.sut.push("overflow")
        self.assertIsNone(evicted_none)
        self.assertEqual(self.sut.size, 10)

    def test_pop_empty_buffer_raises_buffer_empty_error(self) -> None:
        """Verify pop operation on an empty buffer raises BufferEmptyError."""
        with self.assertRaises(BufferEmptyError):
            self.sut.pop()

    def test_pop_removes_and_returns_oldest_item(self) -> None:
        """Verify pop removes and returns oldest item, decrementing size."""
        self.sut.push("first")
        self.sut.push("second")
        self.sut.push("third")

        first_popped = self.sut.pop()
        self.assertEqual(first_popped, "first")
        self.assertEqual(self.sut.size, 2)
        self.assertEqual(self.sut.snapshot_items(), ["second", "third"])

        second_popped = self.sut.pop()
        self.assertEqual(second_popped, "second")
        self.assertEqual(self.sut.size, 1)

        third_popped = self.sut.pop()
        self.assertEqual(third_popped, "third")
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)

        with self.assertRaises(BufferEmptyError):
            self.sut.pop()

    def test_clear_resets_buffer_contents_and_size(self) -> None:
        """Verify clear removes all items and resets size to zero."""
        for item in ["alpha", "beta", "gamma"]:
            self.sut.push(item)
        self.assertEqual(self.sut.size, 3)

        self.sut.clear()
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), [])

        with self.assertRaises(BufferEmptyError):
            self.sut.pop()

    def test_clear_on_empty_buffer(self) -> None:
        """Verify clearing an already empty buffer is a safe no-op."""
        self.sut.clear()
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)

    def test_snapshot_items_non_mutating(self) -> None:
        """Verify snapshot returns items in FIFO order and does not mutate buffer state."""
        self.sut.push("a")
        self.sut.push("b")
        snapshot = self.sut.snapshot_items()
        self.assertEqual(snapshot, ["a", "b"])

        snapshot.append("c")
        self.assertEqual(self.sut.size, 2)
        self.assertEqual(self.sut.snapshot_items(), ["a", "b"])

    def test_interleaved_push_and_pop_lifecycle(self) -> None:
        """Verify interleaved pushes and pops preserve FIFO arrival order."""
        self.sut.push(1)
        self.sut.push(2)
        self.assertEqual(self.sut.pop(), 1)
        self.sut.push(3)
        self.sut.push(4)
        self.assertEqual(self.sut.pop(), 2)
        self.assertEqual(self.sut.pop(), 3)
        self.assertEqual(self.sut.pop(), 4)
        self.assertTrue(self.sut.is_empty)

    def test_error_hierarchy(self) -> None:
        """Verify BufferEmptyError inherits from BufferError."""
        self.assertTrue(issubclass(BufferEmptyError, BufferError))
        self.assertTrue(issubclass(BufferError, Exception))


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-16T01:46:36Z
# LAST_CHANGED: 2026-11-16T01:45:38Z
# CHANGES:
# - [2026-11-16T01:45:38Z] [kind:new] [Lines: 4-6, 8-154] Delta: Implement complete unit test suite for RingBuffer covering capacity, size, push, pop, clear, and snapshot_items | Why: Verify ring buffer operations satisfy specifications and postconditions
# COVERAGE_AUDIT: 2026-11-16T01:46:36Z
# QA_AUDIT: 2026-11-16T01:46:07Z
# --- END AUTOFAB METADATA ---
