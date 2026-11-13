from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleTestCase
from ring_buffer_deepseek_flash_1.parts.ring_buffer.lib import ring_buffer
from ring_buffer_deepseek_flash_1.parts.ring_buffer.lib import ring_buffer_impl


class RingBufferTest(LifecycleTestCase):
    """Unit tests for the bounded circular ring buffer with overwrite eviction."""

    target = ring_buffer_impl.RingBuffer

    def fill_buffer(self, count: int) -> list[str]:
        """Push distinct marker items into the buffer and return them in push order."""
        items: list[str] = [f"item-{index}" for index in range(count)]
        for item in items:
            self.sut.push(item)
        return items

    def test_default_capacity_and_empty_state(self) -> None:
        """Verify the buffer exposes capacity ten and reports empty, non-full state when cleared."""
        self.sut.clear()
        self.assertEqual(self.sut.capacity, 10)
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), [])

    def test_push_with_available_capacity_returns_none(self) -> None:
        """Verify pushing below capacity stores the item, grows size, and returns None."""
        self.sut.clear()
        self.assertIsNone(self.sut.push("first"))
        self.assertEqual(self.sut.size, 1)
        self.assertFalse(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), ["first"])

    def test_push_to_capacity_reports_full(self) -> None:
        """Verify filling to capacity retains all items and reports the buffer full."""
        self.sut.clear()
        items = self.fill_buffer(10)
        self.assertEqual(self.sut.size, 10)
        self.assertEqual(self.sut.size, self.sut.capacity)
        self.assertFalse(self.sut.is_empty)
        self.assertTrue(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), items)

    def test_push_when_full_evicts_oldest(self) -> None:
        """Verify pushing a full buffer evicts the oldest item and keeps size at capacity."""
        self.sut.clear()
        items = self.fill_buffer(10)
        evicted = self.sut.push("item-10")
        self.assertEqual(evicted, items[0])
        self.assertEqual(self.sut.size, self.sut.capacity)
        self.assertTrue(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), items[1:] + ["item-10"])

    def test_pop_when_non_empty_returns_oldest(self) -> None:
        """Verify popping a non-empty buffer removes and returns the oldest item."""
        self.sut.clear()
        self.fill_buffer(3)
        self.assertEqual(self.sut.pop(), "item-0")
        self.assertEqual(self.sut.size, 2)
        self.assertFalse(self.sut.is_empty)
        self.assertEqual(self.sut.snapshot_items(), ["item-1", "item-2"])

    def test_pop_when_empty_raises_buffer_empty_error(self) -> None:
        """Verify popping an empty buffer raises BufferEmptyError."""
        self.sut.clear()
        with self.assertRaises(ring_buffer.BufferEmptyError):
            self.sut.pop()

    def test_clear_removes_all_items(self) -> None:
        """Verify clearing drops every item and resets the buffer to empty state."""
        self.sut.clear()
        self.fill_buffer(4)
        self.sut.clear()
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.snapshot_items(), [])
        self.assertIsNone(self.sut.push("after-clear"))
        self.assertEqual(self.sut.snapshot_items(), ["after-clear"])

    def test_snapshot_items_preserves_buffer_state(self) -> None:
        """Verify snapshot queries do not mutate contents, size, capacity, or fullness."""
        self.sut.clear()
        self.fill_buffer(5)
        first = self.sut.snapshot_items()
        second = self.sut.snapshot_items()
        self.assertEqual(first, second)
        self.assertEqual(self.sut.size, 5)
        self.assertEqual(self.sut.capacity, 10)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.pop(), "item-0")

    def test_fifo_order_survives_multiple_evictions(self) -> None:
        """Verify FIFO arrival order is retained after repeated overwrite evictions."""
        self.sut.clear()
        self.fill_buffer(12)
        self.assertEqual(
            self.sut.snapshot_items(),
            [f"item-{index}" for index in range(2, 12)],
        )
        self.assertEqual(self.sut.pop(), "item-2")

    def test_push_pop_round_trip_restores_order(self) -> None:
        """Verify repeated push and pop operations preserve first-in first-out ordering."""
        self.sut.clear()
        self.sut.push("alpha")
        self.sut.push("beta")
        self.assertEqual(self.sut.pop(), "alpha")
        self.sut.push("gamma")
        self.assertEqual(self.sut.snapshot_items(), ["beta", "gamma"])
        self.assertEqual(self.sut.pop(), "beta")
        self.assertEqual(self.sut.pop(), "gamma")
        self.assertTrue(self.sut.is_empty)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T20:03:04Z
# LAST_CHANGED: 2026-11-12T20:02:25Z
# CHANGE: Author unit test suite for RingBuffer covering initial/empty and full capacity state, push with available capacity returning None, overwrite eviction of oldest item on saturation, pop returning oldest item and shrinking size, BufferEmptyError on empty pop, clear resetting contents, non-mutating FIFO snapshot_items, FIFO ordering across repeated evictions, and push/pop round-trip ordering.
# COVERAGE_AUDIT: 2026-11-12T20:03:04Z
# QA_AUDIT: 2026-11-12T20:02:50Z
# --- END AUTOFAB METADATA ---
