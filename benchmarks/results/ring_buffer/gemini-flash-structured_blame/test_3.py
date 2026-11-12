from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleTestCase
from ring_buffer.lib import ring_buffer_impl
from ring_buffer.lib.ring_buffer import BufferEmptyError, BufferError


class RingBufferImplTest(LifecycleTestCase):
    """Unit tests for bounded circular ring buffer realization."""

    target = ring_buffer_impl.RingBuffer

    def test_initial_state(self) -> None:
        """Verify ring buffer initializes with capacity 10 and empty state."""
        self.assertEqual(self.sut.capacity, 10)
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), [])

    def test_push_with_available_capacity(self) -> None:
        """Verify pushing items with available capacity increments size and returns None."""
        result = self.sut.push("item_1")
        self.assertIsNone(result)
        self.assertEqual(self.sut.size, 1)
        self.assertFalse(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)

        result_2 = self.sut.push("item_2")
        self.assertIsNone(result_2)
        self.assertEqual(self.sut.size, 2)
        self.assertEqual(self.sut.snapshot_items(), ["item_1", "item_2"])

    def test_push_reaches_full_capacity(self) -> None:
        """Verify pushing until capacity saturation sets is_full to True."""
        for i in range(10):
            res = self.sut.push(f"val_{i}")
            self.assertIsNone(res)

        self.assertEqual(self.sut.size, 10)
        self.assertEqual(self.sut.capacity, 10)
        self.assertTrue(self.sut.is_full)
        self.assertFalse(self.sut.is_empty)
        expected = [f"val_{i}" for i in range(10)]
        self.assertEqual(self.sut.snapshot_items(), expected)

    def test_push_when_full_causes_overwrite_eviction(self) -> None:
        """Verify pushing when capacity is full evicts the oldest item and returns it."""
        for i in range(10):
            self.sut.push(f"val_{i}")

        evicted = self.sut.push("overflow_val")
        self.assertEqual(evicted, "val_0")
        self.assertEqual(self.sut.size, 10)
        self.assertTrue(self.sut.is_full)

        expected = [f"val_{i}" for i in range(1, 10)] + ["overflow_val"]
        self.assertEqual(self.sut.snapshot_items(), expected)

    def test_push_multiple_overwrite_evictions(self) -> None:
        """Verify multiple overwrite evictions maintain buffer capacity and evict in FIFO order."""
        for i in range(10):
            self.sut.push(i)

        evicted_1 = self.sut.push(10)
        evicted_2 = self.sut.push(11)
        evicted_3 = self.sut.push(12)

        self.assertEqual(evicted_1, 0)
        self.assertEqual(evicted_2, 1)
        self.assertEqual(evicted_3, 2)
        self.assertEqual(self.sut.size, 10)
        self.assertEqual(self.sut.snapshot_items(), list(range(3, 13)))

    def test_pop_empty_buffer_raises_buffer_empty_error(self) -> None:
        """Verify popping from an empty ring buffer raises BufferEmptyError."""
        self.assertEqual(self.sut.size, 0)
        with self.assertRaises(BufferEmptyError):
            self.sut.pop()
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)

    def test_pop_non_empty_buffer_returns_oldest_item(self) -> None:
        """Verify popping from a non-empty buffer removes and returns the oldest item."""
        self.sut.push("alpha")
        self.sut.push("beta")
        self.sut.push("gamma")

        item_1 = self.sut.pop()
        self.assertEqual(item_1, "alpha")
        self.assertEqual(self.sut.size, 2)

        item_2 = self.sut.pop()
        self.assertEqual(item_2, "beta")
        self.assertEqual(self.sut.size, 1)

        item_3 = self.sut.pop()
        self.assertEqual(item_3, "gamma")
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)

        with self.assertRaises(BufferEmptyError):
            self.sut.pop()

    def test_pop_after_overwrite_eviction(self) -> None:
        """Verify popping after overwrite eviction returns the oldest remaining item."""
        for i in range(11):
            self.sut.push(i)

        oldest = self.sut.pop()
        self.assertEqual(oldest, 1)
        self.assertEqual(self.sut.size, 9)
        self.assertFalse(self.sut.is_full)

    def test_clear_resets_buffer_to_empty(self) -> None:
        """Verify clear removes all stored items and resets size to zero."""
        for i in range(5):
            self.sut.push(f"data_{i}")

        self.assertEqual(self.sut.size, 5)
        self.assertFalse(self.sut.is_empty)

        self.sut.clear()
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), [])

        with self.assertRaises(BufferEmptyError):
            self.sut.pop()

    def test_clear_on_already_empty_buffer(self) -> None:
        """Verify clear on an already empty buffer preserves empty state."""
        self.assertEqual(self.sut.size, 0)
        self.sut.clear()
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        self.assertEqual(self.sut.snapshot_items(), [])

    def test_snapshot_items_fifo_order_and_non_mutating(self) -> None:
        """Verify snapshot_items returns items in FIFO order without mutating state."""
        self.sut.push("first")
        self.sut.push("second")
        self.sut.push("third")

        snapshot = self.sut.snapshot_items()
        self.assertEqual(snapshot, ["first", "second", "third"])
        self.assertEqual(self.sut.size, 3)
        self.assertEqual(self.sut.capacity, 10)
        self.assertFalse(self.sut.is_empty)

        snapshot.append("external_mutation")
        self.assertEqual(self.sut.snapshot_items(), ["first", "second", "third"])

    def test_interleaved_push_and_pop_operations(self) -> None:
        """Verify interleaved push and pop operations preserve correct FIFO ordering."""
        self.sut.push(100)
        self.sut.push(200)
        self.assertEqual(self.sut.pop(), 100)

        self.sut.push(300)
        self.sut.push(400)
        self.assertEqual(self.sut.pop(), 200)

        self.assertEqual(self.sut.snapshot_items(), [300, 400])
        self.assertEqual(self.sut.size, 2)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T03:47:01Z
# LAST_CHANGED: 2026-11-12T03:33:35Z
# CHANGE: Implement unit tests for RingBuffer bounded circular FIFO buffer and overwrite eviction
# COVERAGE_AUDIT: 2026-11-12T03:47:01Z
# QA_AUDIT: 2026-11-12T03:46:28Z
# --- END AUTOFAB METADATA ---
